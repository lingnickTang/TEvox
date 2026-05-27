"""
打印知识图谱的各类节点数量，以及每层节点与下层节点的边的数量。
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

    # ---------- 各类节点数量 ----------
    n_file = sum(1 for n in G.nodes() if node_type(n) == "file")
    n_submodule = sum(1 for n in G.nodes() if node_type(n) == "submodule")
    n_function = sum(1 for n in G.nodes() if node_type(n) == "function")
    n_flow = sum(1 for n in G.nodes() if node_type(n) == "flow")
    n_other = G.node_count() - (n_file + n_submodule + n_function + n_flow)

    # ---------- 每层与下层的边（contains） ----------
    file_to_submodule = 0   # file -> submodule [contains]
    submodule_to_function = 0  # submodule -> function [contains]
    function_to_flow = 0    # function -> flow [contains]
    for u, v in G.edges():
        et = edge_type(u, v)
        if et != "contains":
            continue
        tu, tv = node_type(u), node_type(v)
        if tu == "file" and tv == "submodule":
            file_to_submodule += 1
        elif tu == "submodule" and tv == "function":
            submodule_to_function += 1
        elif tu == "function" and tv == "flow":
            function_to_flow += 1

    # ---------- 打印 ----------
    print("=" * 60)
    print("知识图谱节点数量（按类型）")
    print("=" * 60)
    print("  file:      %d" % n_file)
    print("  submodule: %d" % n_submodule)
    print("  function:  %d" % n_function)
    print("  flow:      %d" % n_flow)
    if n_other:
        print("  其他:      %d" % n_other)
    print("  合计:      %d" % G.node_count())
    print()

    print("=" * 60)
    print("每层与下层节点的边数量（contains）")
    print("=" * 60)
    print("  file      -> submodule:  %d" % file_to_submodule)
    print("  submodule -> function:   %d" % submodule_to_function)
    print("  function  -> flow:       %d" % function_to_flow)
    print("  合计（层级 contains）:   %d" % (file_to_submodule + submodule_to_function + function_to_flow))
    print()

    # depends_on 边（可选：同层/跨层）
    depends_on_ff = sum(
        1 for u, v in G.edges()
        if edge_type(u, v) == "depends_on" and node_type(u) == "function" and node_type(v) == "function"
    )
    depends_on_flow_to_func = sum(
        1 for u, v in G.edges()
        if edge_type(u, v) == "depends_on" and node_type(u) == "flow" and node_type(v) == "function"
    )
    total_depends_on = sum(1 for u, v in G.edges() if edge_type(u, v) == "depends_on")
    print("=" * 60)
    print("depends_on 边（调用/依赖）")
    print("=" * 60)
    print("  function -> function:   %d" % depends_on_ff)
    print("  flow     -> function:   %d" % depends_on_flow_to_func)
    print("  合计（depends_on）:      %d" % total_depends_on)
    print("=" * 60)


if __name__ == "__main__":
    main()
