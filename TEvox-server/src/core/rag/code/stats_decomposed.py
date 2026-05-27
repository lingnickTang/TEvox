"""
统计：1) 被拆解的文件数及拆解出的模块数；2) 被拆解的函数数及拆解出的 flow 数。
依赖：Graph.from_json，需在 evox-server 项目根下运行或设置 PYTHONPATH。
"""
import os
import sys

# 若在 evox-server 外运行，请把 evox-server 加入路径
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
    decomposed_path = os.path.join(base, "file_decomposed_graph_with_dependencies.json")
    flow_path = os.path.join(base, "function_flow_graph_full.json")

    if not os.path.isfile(decomposed_path):
        print("未找到文件分解图: %s" % decomposed_path)
        return
    if not os.path.isfile(flow_path):
        print("未找到函数流图: %s" % flow_path)
        return

    G_decomposed = Graph.from_json(decomposed_path)
    G_flow = Graph.from_json(flow_path)

    # ---------- 1) 文件拆解统计 ----------
    file_nodes = [n for n in G_decomposed.nodes() if (G_decomposed.get_node(n) or {}).get("type") == "file"]
    submodule_nodes = [n for n in G_decomposed.nodes() if (G_decomposed.get_node(n) or {}).get("type") == "submodule"]
    n_files = len(file_nodes)
    n_submodules = len(submodule_nodes)

    files_with_submodules = set()
    for u, v in G_decomposed.edges():
        edge_type = (G_decomposed.get_edge(u, v) or {}).get("edge_type", "")
        if edge_type == "contains":
            node_u = G_decomposed.get_node(u)
            if node_u and node_u.get("type") == "file":
                files_with_submodules.add(u)
    n_files_decomposed = len(files_with_submodules)

    print("=" * 60)
    print("1. 文件拆解统计")
    print("=" * 60)
    print("  图中文件节点数: %d" % n_files)
    print("  被拆解的文件数（至少包含 1 个子模块）: %d" % n_files_decomposed)
    print("  拆解出的子模块总数: %d" % n_submodules)
    if n_files_decomposed > 0:
        print("  平均每个被拆解文件含子模块数: %.2f" % (n_submodules / n_files_decomposed))
    print()

    # ---------- 2) 函数拆解统计 ----------
    # function_flow 图中：有 label 的为函数节点，无 label 的为 flow 节点
    function_nodes = []
    flow_nodes = []
    for n in G_flow.nodes():
        node = G_flow.get_node(n) or {}
        if node.get("label"):
            function_nodes.append(n)
        else:
            flow_nodes.append(n)
    n_functions = len(function_nodes)
    n_flows = len(flow_nodes)

    functions_with_flows = set()
    for u, v in G_flow.edges():
        edge_type = (G_flow.get_edge(u, v) or {}).get("edge_type", "")
        if edge_type == "contains":
            node_u = G_flow.get_node(u)
            if node_u and node_u.get("label"):
                functions_with_flows.add(u)
    n_functions_decomposed = len(functions_with_flows)

    print("=" * 60)
    print("2. 函数拆解统计")
    print("=" * 60)
    print("  图中函数节点数: %d" % n_functions)
    print("  被拆解的函数数（至少包含 1 个 flow）: %d" % n_functions_decomposed)
    print("  拆解出的 flow 总数: %d" % n_flows)
    if n_functions_decomposed > 0:
        print("  平均每个被拆解函数含 flow 数: %.2f" % (n_flows / n_functions_decomposed))
    print("=" * 60)


if __name__ == "__main__":
    main()
