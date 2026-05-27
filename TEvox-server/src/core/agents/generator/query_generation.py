import sys
from src.core.agents.generator.graph_builder import graph
from src.core.agents.generator.document_extractor import generate_causal_hypothesis

def auto_generate_queries(graph):
    """
    遍历所有节点，调用 generate_causal_hypothesis，为每个节点生成高质量 query。
    返回所有节点及其生成的 query 字典。
    """
    all_queries = {}
    for node in graph.nodes:
        # 获取当前节点已存在的问题，避免重复
        current_question_list = [item.question for item in graph.nodes[node].get("knowledge_blocks", [])]
        queries = generate_causal_hypothesis(node, current_question_list)
        if queries:
            all_queries[node] = queries
    return all_queries

def user_select_query(all_queries):
    """
    命令行交互，用户选择一个 query。
    返回 (node, query) 元组。
    """
    print("\n=== 自动生成的 Query 列表 ===")
    idx_map = []
    idx = 1
    for node, queries in all_queries.items():
        for q in queries:
            print(f"[{idx}] 节点: {node}\n    {q}")
            idx_map.append((node, q))
            idx += 1
    if not idx_map:
        print("未生成任何 query。"); return None, None
    while True:
        try:
            sel = int(input(f"请选择要使用的 query（1-{len(idx_map)}，输入0退出）："))
            if sel == 0:
                return None, None
            if 1 <= sel <= len(idx_map):
                return idx_map[sel-1]
        except Exception:
            pass
        print("输入无效，请重新输入。")

if __name__ == "__main__":
    all_queries = auto_generate_queries(graph)
    node, query = user_select_query(all_queries)
    if node and query:
        print(f"\n你选择的节点: {node}\n你选择的 query: {query}")
    else:
        print("未选择 query，程序结束。") 