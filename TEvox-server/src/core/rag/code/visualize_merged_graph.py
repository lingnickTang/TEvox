"""
将 merged_graph.json 用 NetworkX 绘制为 PNG 静态图，用于工作量呈现。

通过 --mode 参数选择：
  basic  仅 file 与 function 节点，边由 file -> submodule -> function 的 contains 推导
  full   完整知识图谱（所有节点与边）
  local_file_function  局部图1：仅 file 与 function 之间的关联
  local_four_layer     局部图2：file -> submodule -> function -> flow 四层关联
  all                 生成 basic、full 及两个局部图
"""
import argparse
import os
import sys
from collections import deque
from typing import Optional, Set, Tuple

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_evox_server_root = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
if _evox_server_root not in sys.path:
    sys.path.insert(0, _evox_server_root)

import networkx as nx

from src.core.rag.code.tools.graph import Graph


def _grapher_base() -> str:
    for base in (
        os.path.join(_evox_server_root, ".rag", "xiaozhi", "grapher"),
        os.path.normpath("evox-server/.rag/xiaozhi/grapher"),
        os.path.normpath(".rag/xiaozhi/grapher"),
    ):
        if os.path.isdir(base):
            return base
    return os.path.join(_evox_server_root, ".rag", "xiaozhi", "grapher")


def _node_type(G: Graph, nid: str) -> str:
    return (G.get_node(nid) or {}).get("type", "?")


def _edge_type(G: Graph, u: str, v: str) -> str:
    return (G.get_edge(u, v) or {}).get("edge_type", "?")


def build_basic_graph(G: Graph) -> nx.MultiDiGraph:
    """
    从完整图中抽取仅 file 与 function 的基础静态代码知识图谱。
    边包括：
    1) file -> function：由 file -> submodule -> function 的 contains 关系推导；
    2) function -> function：原图中两端均为 function 的边（如 depends_on 等）全部保留。
    """
    file_nodes = {n for n in G.nodes() if _node_type(G, n) == "file"}
    function_nodes = {n for n in G.nodes() if _node_type(G, n) == "function"}
    subgraph_nodes = file_nodes | function_nodes

    # submodule -> set(files that contain it), submodule -> set(functions it contains)
    submodule_to_files = {}
    submodule_to_functions = {}
    for u, v in G.edges():
        if _edge_type(G, u, v) != "contains":
            continue
        tu, tv = _node_type(G, u), _node_type(G, v)
        if tu == "file" and tv == "submodule":
            submodule_to_functions.setdefault(v, set())
            submodule_to_files.setdefault(v, set()).add(u)
        elif tu == "submodule" and tv == "function":
            submodule_to_files.setdefault(u, set())
            submodule_to_functions.setdefault(u, set()).add(v)

    # 1) file -> function：每条 submodule->function 对应每条 file->function
    file_to_function_edges = []
    for submodule, files in submodule_to_files.items():
        for func in submodule_to_functions.get(submodule, set()):
            for f in files:
                file_to_function_edges.append((f, func))

    # 2) function -> function：原图中两端均为 function 的边全部加入
    function_to_function_edges = []
    for u, v in G.edges():
        if u in function_nodes and v in function_nodes:
            edge_attrs = G.get_edge(u, v) or {}
            function_to_function_edges.append((u, v, edge_attrs))

    sub = nx.MultiDiGraph()
    for n in subgraph_nodes:
        attrs = G.get_node(n) or {}
        sub.add_node(n, **attrs)
    for u, v in file_to_function_edges:
        sub.add_edge(u, v, edge_type="contains")
    for u, v, attrs in function_to_function_edges:
        sub.add_edge(u, v, **attrs)
    return sub


def _resolve_file_id(G: Graph, file_id: str) -> str:
    """
    解析 file_id，兼容命令行转义导致的路径差异。
    - 优先精确匹配
    - 尝试 / 与 \\ 互换（Windows/Linux 路径）
    - 尝试按文件名后缀匹配（如 afe_wake_word.h）
    """
    if G.has_node(file_id):
        return file_id
    alt1 = file_id.replace("/", "\\")
    if alt1 != file_id and G.has_node(alt1):
        return alt1
    alt2 = file_id.replace("\\", "/")
    if alt2 != file_id and G.has_node(alt2):
        return alt2
    # 按 label 或 id 后缀匹配 file 节点
    base = os.path.basename(file_id.replace("\\", "/"))
    for n in G.nodes():
        if _node_type(G, n) != "file":
            continue
        node_label = (G.get_node(n) or {}).get("label", n)
        if n.endswith(base) or node_label.endswith(base) or base in n or base in str(node_label):
            return n
    raise ValueError(
        "文件节点不在图中: %r。提示：PowerShell 中 \\a 会被解析为特殊字符，"
        "可改用正斜杠如 -f \"main/audio/wake_words/afe_wake_word.h\"" % file_id
    )


def extract_local_subgraph(
    G: Graph,
    file_id: Optional[str] = None,
    seed_node: Optional[str] = None,
    depth: int = 4,
    max_nodes: int = 80,
) -> Tuple[Set[str], str]:
    """
    从完整图中抽取局部子图的节点集合（整图放大的一部分）。
    若指定 file_id：以该文件为根，沿 contains 链展开 file->submodule->function->flow。
    否则：从 seed_node（或第一个根节点）BFS，限制深度和节点数。

    Returns:
        (sub_nodes, description) 子图节点集合与描述
    """
    sub_nodes: Set[str] = set()

    if file_id is not None:
        resolved = _resolve_file_id(G, file_id)
        if _node_type(G, resolved) != "file":
            raise ValueError("指定节点不是 file 类型: %s (type=%s)" % (resolved, _node_type(G, resolved)))
        file_id = resolved
        sub_nodes.add(file_id)
        for s in G.successors(file_id):
            if _edge_type(G, file_id, s) == "contains" and _node_type(G, s) == "submodule":
                sub_nodes.add(s)
        for sm in [n for n in sub_nodes if _node_type(G, n) == "submodule"]:
            for s in G.successors(sm):
                if _edge_type(G, sm, s) == "contains" and _node_type(G, s) == "function":
                    sub_nodes.add(s)
        for fn in [n for n in sub_nodes if _node_type(G, n) == "function"]:
            for s in G.successors(fn):
                if _edge_type(G, fn, s) == "contains" and _node_type(G, s) == "flow":
                    sub_nodes.add(s)
        desc = "file=%s" % file_id
    else:
        seed = seed_node
        if seed is None:
            roots = G.roots()
            seed = roots[0] if roots else next(iter(G.nodes()))
        if not G.has_node(seed):
            raise ValueError("种子节点不在图中: %s" % seed)
        q = deque([(seed, 0)])
        while q and len(sub_nodes) < max_nodes:
            n, d = q.popleft()
            if n in sub_nodes or d > depth:
                continue
            sub_nodes.add(n)
            for succ in G.successors(n):
                if len(sub_nodes) >= max_nodes:
                    break
                if succ not in sub_nodes:
                    q.append((succ, d + 1))
        desc = "BFS from %s (depth=%d, max=%d)" % (seed[:40] + "..." if len(str(seed)) > 40 else seed, depth, max_nodes)

    return sub_nodes, desc


def build_local_subgraph(
    G: Graph,
    sub_nodes: Set[str],
    node_types: Optional[Set[str]] = None,
) -> nx.MultiDiGraph:
    """
    根据节点集合和可选类型过滤，构建 nx 子图。
    node_types: 若指定，仅保留这些类型的节点；否则保留 sub_nodes 中全部。
    """
    if node_types is not None:
        keep = {n for n in sub_nodes if _node_type(G, n) in node_types}
    else:
        keep = sub_nodes

    sub = nx.MultiDiGraph()
    for n in keep:
        attrs = G.get_node(n) or {}
        sub.add_node(n, **attrs)
    for u, v in G.edges():
        if u in keep and v in keep:
            edge_attrs = G.get_edge(u, v) or {}
            sub.add_edge(u, v, **edge_attrs)
    return sub


def build_local_file_function_graph(G: Graph, sub_nodes: Set[str]) -> nx.MultiDiGraph:
    """
    局部 file+function 图：file->function 边由 file->submodule->function 推导，
    function->function 边原样保留。仅包含 sub_nodes 中的 file 与 function。
    """
    file_nodes = {n for n in sub_nodes if _node_type(G, n) == "file"}
    function_nodes = {n for n in sub_nodes if _node_type(G, n) == "function"}
    keep = file_nodes | function_nodes
    if not keep:
        return nx.MultiDiGraph()

    submodule_to_files = {}
    submodule_to_functions = {}
    for u, v in G.edges():
        if _edge_type(G, u, v) != "contains":
            continue
        tu, tv = _node_type(G, u), _node_type(G, v)
        if tu == "file" and tv == "submodule":
            submodule_to_functions.setdefault(v, set())
            submodule_to_files.setdefault(v, set()).add(u)
        elif tu == "submodule" and tv == "function":
            submodule_to_files.setdefault(u, set())
            submodule_to_functions.setdefault(u, set()).add(v)

    sub = nx.MultiDiGraph()
    for n in keep:
        attrs = G.get_node(n) or {}
        sub.add_node(n, **attrs)
    for submodule, files in submodule_to_files.items():
        for func in submodule_to_functions.get(submodule, set()):
            for f in files:
                if f in file_nodes and func in function_nodes:
                    sub.add_edge(f, func, edge_type="contains")
    for u, v in G.edges():
        if u in function_nodes and v in function_nodes:
            edge_attrs = G.get_edge(u, v) or {}
            sub.add_edge(u, v, **edge_attrs)
    return sub


def build_file_function_local_graph(G: Graph) -> nx.MultiDiGraph:
    """
    局部图1：仅包含 file 与 function 之间关联的 subgraph。
    与 build_basic_graph 等价，保留 file->function（由 contains 推导）及 function->function 边。
    """
    return build_basic_graph(G)


def build_four_layer_local_graph(G: Graph) -> nx.MultiDiGraph:
    """
    局部图2：包含 file、submodule、function、flow 四层关联的 subgraph。
    保留四种节点类型及 contains、depends_on 边。
    """
    allowed_types = {"file", "submodule", "function", "flow"}
    subgraph_nodes = {n for n in G.nodes() if _node_type(G, n) in allowed_types}

    sub = nx.MultiDiGraph()
    for n in subgraph_nodes:
        attrs = G.get_node(n) or {}
        sub.add_node(n, **attrs)
    for u, v in G.edges():
        if u in subgraph_nodes and v in subgraph_nodes:
            edge_attrs = G.get_edge(u, v) or {}
            sub.add_edge(u, v, **edge_attrs)
    return sub


# 节点类型与边的配色，便于在图上体现类型和关系
_NODE_TYPE_COLORS = {
    "file": "#2ecc71",
    "submodule": "#e67e22",
    "function": "#3498db",
    "flow": "#9b59b6",
    "?": "#95a5a6",
}
_EDGE_TYPE_COLORS = {
    "contains": "#2c3e50",
    "depends_on": "#e74c3c",
    "?": "#bdc3c7",
}


def _draw_local_and_save(
    nx_g: nx.MultiDiGraph,
    G: Graph,
    out_basename: str,
    base: str,
    title_suffix: str,
) -> None:
    """
    绘制局部图，节点按 type 着色，边按 edge_type 着色，并显示图例。
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError as e:
        print("请安装 matplotlib 与 networkx: pip install matplotlib networkx")
        raise SystemExit(1) from e

    n_nodes = nx_g.number_of_nodes()
    n_edges = nx_g.number_of_edges()
    if n_nodes == 0:
        print("局部图无节点，跳过保存")
        return

    # 节点颜色与大小（局部图放大展示，节点更大）
    node_colors = []
    node_sizes = []
    for n in nx_g.nodes():
        t = (nx_g.nodes[n].get("type") or "?")
        node_colors.append(_NODE_TYPE_COLORS.get(t, _NODE_TYPE_COLORS["?"]))
        node_sizes.append(120 if t == "file" else (100 if t == "submodule" else (80 if t == "function" else 60)))

    # 边按类型着色：优先从 nx_g 获取（含推导边），否则从 G 获取
    edge_colors = []
    for u, v in nx_g.edges():
        ed = nx_g.get_edge_data(u, v)
        if ed:
            attrs = list(ed.values())[0] if isinstance(ed, dict) else ed
            et = attrs.get("edge_type", "?") if isinstance(attrs, dict) else "?"
        elif G and G.has_edge(u, v):
            et = _edge_type(G, u, v)
        else:
            et = "?"
        edge_colors.append(_EDGE_TYPE_COLORS.get(et, _EDGE_TYPE_COLORS["?"]))

    fig, ax = plt.subplots(figsize=(16, 14))
    pos = nx.spring_layout(nx_g, k=1.2, iterations=80, seed=42)

    nx.draw_networkx_edges(
        nx_g,
        pos,
        ax=ax,
        edge_color=edge_colors,
        alpha=0.7,
        arrows=True,
        arrowsize=12,
        connectionstyle="arc3,rad=0.1",
    )
    nx.draw_networkx_nodes(
        nx_g,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        alpha=0.9,
    )

    # 节点标签：简短显示，便于识别类型
    labels = {}
    for n in nx_g.nodes():
        node_data = nx_g.nodes[n]
        t = node_data.get("type", "?")
        lbl = node_data.get("label", "")
        if not lbl and "body" in node_data:
            body = str(node_data.get("body", ""))[:30]
            lbl = body + "..." if len(body) >= 30 else body
        if not lbl:
            lbl = n.split(":")[-1][:25] if ":" in n else n[:25]
        labels[n] = "[%s] %s" % (t[0].upper(), lbl[:28] + ".." if len(str(lbl)) > 28 else lbl)
    nx.draw_networkx_labels(
        nx_g,
        pos,
        labels,
        ax=ax,
        font_size=7,
        font_weight="bold",
    )

    # 图例：节点类型
    node_legend = [
        mpatches.Patch(color=c, label="%s" % t) for t, c in _NODE_TYPE_COLORS.items() if t != "?"
    ]
    node_legend.append(mpatches.Patch(color=_NODE_TYPE_COLORS["?"], label="other"))
    # 图例：边类型
    edge_legend = [
        mpatches.Patch(color=c, label="%s" % et) for et, c in _EDGE_TYPE_COLORS.items() if et != "?"
    ]
    ax.legend(
        handles=node_legend + edge_legend,
        loc="upper left",
        ncol=2,
        fontsize=9,
        title="节点类型 / 边关系",
    )
    ax.set_title("%s (nodes=%d, edges=%d)" % (title_suffix, n_nodes, n_edges), fontsize=12)
    ax.axis("off")
    plt.tight_layout()
    out_path = os.path.join(base, out_basename)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print("已保存: %s" % out_path)


def _draw_and_save(nx_g: nx.MultiDiGraph, out_basename: str, base: str, title_suffix: str) -> None:
    """通用绘图并保存 PNG。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        print("请安装 matplotlib 与 networkx: pip install matplotlib networkx")
        raise SystemExit(1) from e

    n_nodes = nx_g.number_of_nodes()
    n_edges = nx_g.number_of_edges()
    fig, ax = plt.subplots(figsize=(16, 16))
    pos = nx.spring_layout(nx_g, k=0.5, iterations=50, seed=42)
    nx.draw(
        nx_g,
        pos,
        ax=ax,
        node_size=8,
        node_color="steelblue",
        edge_color="gray",
        alpha=0.6,
        arrows=True,
        arrowsize=4,
        with_labels=False,
    )
    ax.set_title("%s (nodes=%d, edges=%d)" % (title_suffix, n_nodes, n_edges))
    out_path = os.path.join(base, out_basename)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print("已保存: %s" % out_path)


def main():
    parser = argparse.ArgumentParser(
        description="将 merged_graph.json 绘制为 PNG 静态图（支持 basic/full/局部图等模式）"
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["basic", "full", "local_file_function", "local_four_layer", "all"],
        default="full",
        help="basic: 仅 file 与 function; full: 完整图; local_file_function: 局部图1(file+function); "
             "local_four_layer: 局部图2(file+submodule+function+flow); all: 生成全部",
    )
    parser.add_argument(
        "--file-id",
        "-f",
        default=None,
        help="局部图模式：指定 file 节点 id，以该文件为根展开子图；未指定则 BFS 从根节点抽取",
    )
    parser.add_argument(
        "--max-nodes",
        default=80,
        type=int,
        help="局部图模式：BFS 时的最大节点数（--file-id 未指定时有效），默认 80",
    )
    args = parser.parse_args()

    base = _grapher_base()
    merged_path = os.path.join(base, "merged_graph.json")
    if not os.path.isfile(merged_path):
        print("未找到合并图: %s" % merged_path)
        return

    G = Graph.from_json(merged_path)

    def run_basic():
        nx_g = build_basic_graph(G)
        print("模式: basic, 节点: %d, 边: %d" % (nx_g.number_of_nodes(), nx_g.number_of_edges()))
        file_nodes = {n for n, d in nx_g.nodes(data=True) if d.get("type") == "file"}
        func_nodes = {n for n, d in nx_g.nodes(data=True) if d.get("type") == "function"}
        n_file_to_func = sum(1 for u, v in nx_g.edges() if u in file_nodes and v in func_nodes)
        n_func_to_func = sum(1 for u, v in nx_g.edges() if u in func_nodes and v in func_nodes)
        print("file->function: %d" % n_file_to_func)
        print("function->function: %d" % n_func_to_func)
        _draw_and_save(nx_g, "merged_graph_static_basic.png", base, "basic")

    def run_full():
        nx_g = G.nx_graph
        print("模式: full, 节点: %d, 边: %d" % (nx_g.number_of_nodes(), nx_g.number_of_edges()))
        _draw_and_save(nx_g, "merged_graph_static.png", base, "full")

    def run_local_file_function():
        sub_nodes, desc = extract_local_subgraph(
            G, file_id=args.file_id, max_nodes=args.max_nodes
        )
        nx_g = build_local_file_function_graph(G, sub_nodes)
        if nx_g.number_of_nodes() == 0:
            # 局部无 file/function 时回退为全图 basic 的缩小版（取前 max_nodes 个节点）
            full_basic = build_file_function_local_graph(G)
            nodes_list = list(full_basic.nodes())[: args.max_nodes]
            nx_g = build_local_file_function_graph(G, set(nodes_list))
            if nx_g.number_of_nodes() == 0:
                nx_g = full_basic
            desc = "fallback (basic sub)"
        print("模式: local_file_function (%s), 节点: %d, 边: %d" % (
            desc, nx_g.number_of_nodes(), nx_g.number_of_edges()))
        _draw_local_and_save(nx_g, G, "merged_graph_local_file_function.png", base, "local_file_function")

    def run_local_four_layer():
        sub_nodes, desc = extract_local_subgraph(
            G, file_id=args.file_id, max_nodes=args.max_nodes
        )
        nx_g = build_local_subgraph(G, sub_nodes, node_types={"file", "submodule", "function", "flow"})
        print("模式: local_four_layer (%s), 节点: %d, 边: %d" % (
            desc, nx_g.number_of_nodes(), nx_g.number_of_edges()))
        _draw_local_and_save(nx_g, G, "merged_graph_local_four_layer.png", base, "local_four_layer")

    if args.mode == "all":
        run_basic()
        run_full()
        run_local_file_function()
        run_local_four_layer()
    elif args.mode == "basic":
        run_basic()
    elif args.mode == "full":
        run_full()
    elif args.mode == "local_file_function":
        run_local_file_function()
    elif args.mode == "local_four_layer":
        run_local_four_layer()


if __name__ == "__main__":
    main()
