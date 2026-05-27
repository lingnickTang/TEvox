import networkx as nx
import os
import json

linked_graph_path = "../../.output/linked_graph.json"

graph_list = []

with open(linked_graph_path, "r") as f:
    nodes = json.load(f)
    for node in nodes:
        graph_list.append(node)

G = graph_list[2]
G_json = json.dumps(G, indent=4)
G_dic = json.loads(G_json)
G_nodes = G_dic["nodes"]

id_content_list = []

for node in G_nodes:
    class_name = node.get("class_name")
    if class_name != "TextUnit":
        continue
    id_content = {}
    id_content['id'] = node.get("id")
    id_content['content'] = node.get("content")
    id_content_list.append(id_content)

id_content_list_json = json.dumps(id_content_list, indent=4)
with open("../../.output/id_content_list.jsonl", "w") as f:
    f.write(id_content_list_json)


# G = nx.readwrite.json_graph.node_link_graph(G)

# output_path = "../../.output/graph.graphml"
# nx.write_graphml(G, output_path)

# print(f"图已成功保存为GraphML格式: {output_path}")

# for node, data in G.nodes(data=True):
#     for key, value in data.items():
#         if isinstance(value, dict):
#             data[key] = str(value)  # 转为字符串

# for u, v, data in G.edges(data=True):
#     for key, value in data.items():
#         if isinstance(value, dict):
#             data[key] = str(value)

# # 3. 确保输出目录存在
# output_dir = "../../.output/"
# os.makedirs(output_dir, exist_ok=True)

# # 4. 保存为 GraphML 格式
# output_graphml_path = os.path.join(output_dir, "linked_graph.graphml")
# nx.write_graphml(G, output_graphml_path)

# print(f"Graph saved to {output_graphml_path}")