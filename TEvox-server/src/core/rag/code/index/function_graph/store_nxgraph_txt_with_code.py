import networkx as nx
import os
import sys
import json
from tqdm import tqdm
import math
from collections import defaultdict

# Add parent directory to sys.path to import config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import load_config

def get_dict_from_file(file_path):
    """
    从文件加载JSON数据
    
    :param file_path: JSON文件路径
    :return: 解析后的JSON数据
    """
    with open(file_path, 'r') as file:
        return json.load(file) 
    
def build_nx_graph_txt_with_code(topk_mathes_file_path, store_edges_file_path, top_k=10):
    """
    构建代码-文本关系图
    
    :param topk_mathes_file_path: top-k匹配结果文件路径
    :param store_edges_file_path: 图输出文件路径
    :param top_k: 每个函数保留的top-k匹配数量
    """
    G = nx.Graph() 
    all_functions_topk_matches = get_dict_from_file(topk_mathes_file_path) 
    all_functions_topk_matches_results = all_functions_topk_matches['results']
    
    print(f"Processing {len(all_functions_topk_matches_results)} functions...")
    for function_id, function_info in tqdm(all_functions_topk_matches_results.items()):
        top_k_matches = function_info['top_k_matches']
        for i in range(min(len(top_k_matches), top_k)):
            match = top_k_matches[i]
            text_unit_id = match['text_unit_id']
            rank = match['rank']
            text_unit_dict = {'text_unit_id': text_unit_id, 'type': 'text_unit'}
            function_dict = {'function_id': function_id, 'type': 'function'}

            G.add_edge(tuple(text_unit_dict.items()), tuple(function_dict.items()), relation=str(rank))

    # 确保输出目录存在
    os.makedirs(os.path.dirname(store_edges_file_path), exist_ok=True)
    
    # 保存图
    nx.write_graphml(G, store_edges_file_path)
    print(f"Graph saved to {store_edges_file_path}")
        
if __name__ == "__main__":
    # 加载配置
    config = load_config()
    
    # 获取路径
    topk_mathes_file_path = config['topKMatchesPath']
    store_edges_file_path = config['nxGraphPath']
    
    # 构建图
    build_nx_graph_txt_with_code(topk_mathes_file_path, store_edges_file_path)