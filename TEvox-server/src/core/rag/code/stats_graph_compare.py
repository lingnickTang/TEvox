"""
统计对比：
1) 静态代码分析图谱（仅 file + function，file 包含 function、function 间调用）：多少调用、多少关联；
2) 当前知识图谱（含 file/submodule/function/flow）：多少调用、多少关联。
"""
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_evox_server_root = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
if _evox_server_root not in sys.path:
    sys.path.insert(0, _evox_server_root)

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


def main():
    base = _grapher_base()
    merged_path = os.path.join(base, "merged_graph.json")
    if not os.path.isfile(merged_path):
        print("未找到合并图: %s" % merged_path)
        return

    G = Graph.from_json(merged_path)

    def node_type(nid):
        return (G.get_node(nid) or {}).get("type", "?")

    def edge_type(u, v):
        return (G.get_edge(u, v) or {}).get("edge_type", "?")

    # ---------- 静态图谱：仅 file + function ----------
    # 图中 file 不直接连 function，而是 file -> submodule -> function，故“file 包含 function”按路径推导
    static_nodes = {n for n in G.nodes() if node_type(n) in ("file", "function")}
    file_contains_function = set()  # (file_id, function_id) 经 file->submodule->function 推导
    for fid in G.nodes():
        if node_type(fid) != "file":
            continue
        for sm in G.successors(fid):
            if node_type(sm) != "submodule" or edge_type(fid, sm) != "contains":
                continue
            for func in G.successors(sm):
                if node_type(func) == "function" and edge_type(sm, func) == "contains":
                    file_contains_function.add((fid, func))
    static_contains = len(file_contains_function)
    static_calls = 0
    for u, v in G.edges():
        if u not in static_nodes or v not in static_nodes:
            continue
        et = edge_type(u, v)
        if et == "depends_on" and node_type(u) == "function" and node_type(v) == "function":
            static_calls += 1
    static_edges = static_contains + static_calls
    static_nodes_file = sum(1 for n in static_nodes if node_type(n) == "file")
    static_nodes_func = sum(1 for n in static_nodes if node_type(n) == "function")

    # ---------- 当前知识图谱：全部节点与边 ----------
    full_contains = 0
    full_depends_on = 0
    for u, v in G.edges():
        et = edge_type(u, v)
        if et == "contains":
            full_contains += 1
        elif et == "depends_on":
            full_depends_on += 1
    full_edges = G.edge_count()
    full_nodes = G.node_count()

    # 调用 = depends_on 边；关联 = 全部边（contains + depends_on）
    print("=" * 60)
    print("静态代码分析图谱（仅 file + function）")
    print("=" * 60)
    print("  节点: file=%d, function=%d, 合计=%d" % (static_nodes_file, static_nodes_func, len(static_nodes)))
    print("  调用（function -> function depends_on）: %d" % static_calls)
    print("  关联（file 包含 function + function 调用 function）: %d" % static_edges)
    print("    - file 包含 function（经 file->submodule->function 推导）: %d" % static_contains)
    print("    - function 调用 function: %d" % static_calls)
    print()

    print("=" * 60)
    print("当前知识图谱（file + submodule + function + flow）")
    print("=" * 60)
    print("  节点总数: %d" % full_nodes)
    print("  边总数: %d" % full_edges)
    print("  调用（depends_on 边）: %d" % full_depends_on)
    print("  关联（全部边）: %d" % full_edges)
    print("    - contains: %d" % full_contains)
    print("    - depends_on: %d" % full_depends_on)
    print()

    print("=" * 60)
    print("对比")
    print("=" * 60)
    print("  调用: 静态 %d  vs  知识图谱 %d" % (static_calls, full_depends_on))
    print("  关联: 静态 %d  vs  知识图谱 %d" % (static_edges, full_edges))
    print("=" * 60)


if __name__ == "__main__":
    main()
