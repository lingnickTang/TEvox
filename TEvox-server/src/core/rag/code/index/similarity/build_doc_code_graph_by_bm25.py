import networkx as nx
import matplotlib.pyplot as plt
from tqdm import tqdm

import json

import math
from collections import defaultdict

def get_dict_from_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file) 
    
def main():
    top_k = 10
    text_units_path = '../../.output/base_text_units.json'
    text_units = get_dict_from_file(text_units_path)
    # print(text_units)
    test_units_json = json.dumps(text_units , indent=4)
    with open('look.json', 'w') as file:
        file.write(test_units_json)

    print(type(text_units))
    print(type(text_units[0]))

    G = nx.Graph() 

    all_functions_topk_matches_path = '../../.output/all_functions_topk_matches.json'
    all_functions_topk_matches = get_dict_from_file(all_functions_topk_matches_path) 
    all_functions_topk_matches_results = all_functions_topk_matches['results']
    for function_id, function_info in tqdm(all_functions_topk_matches_results.items()):
        # print(function_id)
        top_k_matches = function_info['top_k_matches']
        for match in top_k_matches:
            text_unit_id = match['text_unit_id']
            rank = match['rank']
            text_unit_dict = {'text_unit_id': text_unit_id , 'type': 'text_unit'}
            function_dict = {'function_id': function_id, 'type': 'function'}

            G.add_edge(json.dumps(text_unit_dict), json.dumps(function_dict), relation=str(rank))


    # print(type(all_functions_topk_matches))
    # print(type(all_functions_topk_matches['metadata']))

    
    nx.write_graphml(G, "../../.optput/nxgraph_txt_with_code.graphml")
    
    # G_loaded = nx.read_graphml("graph.graphml")
    # G_loaded = nx.read_graphml("graph.graphml")
    # nx.draw(G_loaded, with_labels=True)
    # plt.show()

if __name__ == "__main__":
    main()