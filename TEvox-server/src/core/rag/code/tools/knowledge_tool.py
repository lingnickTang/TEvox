"""
代码检索和分析相关工具
"""
import json
import os
from typing import Optional

import numpy as np
import yaml

from src.base import DefaultConfig
from src.utils import get_dashscope_embedding
from src.utils.log import logger

# 知识图谱默认路径：绝对路径
_EVOX_SERVER_ROOT = "D:/Download/github/evox-ai/evox-server"
SRP_KG_DEFAULT_PATH = os.path.abspath(
    os.path.join(_EVOX_SERVER_ROOT, ".rag", "xiaozhi", "grapher", "SRP_KG.json")
)
KG_DEFAULT_PATH = os.path.abspath(
    os.path.join(_EVOX_SERVER_ROOT, ".rag", "xiaozhi", "grapher", "KG.json")
)
SRP_KG_EMBEDDING_DEFAULT_PATH = os.path.abspath(
    os.path.join(_EVOX_SERVER_ROOT, ".rag", "xiaozhi", "grapher", "SRP_KG_embedding.json")
)
KG_EMBEDDING_DEFAULT_PATH = os.path.abspath(
    os.path.join(_EVOX_SERVER_ROOT, ".rag", "xiaozhi", "grapher", "KG_embedding.json")
)
kg_type_to_path = {
    "SRP_KG": SRP_KG_DEFAULT_PATH,
    "KG": KG_DEFAULT_PATH,
}
kg_type_to_embedding_path = {
    "SRP_KG": SRP_KG_EMBEDDING_DEFAULT_PATH,
    "KG": KG_EMBEDDING_DEFAULT_PATH,
}
# 懒加载缓存：path -> { "nodes", "edges", "id_to_node" }；embedding_path -> { node_id -> vec }
_GRAPH_CACHE: dict = {}
_EMBEDDING_MODEL = None

def reset_graph_cache():
    """重置 graph和embedding 缓存"""
    global _GRAPH_CACHE
    _GRAPH_CACHE = {}

def _get_embedding_model():
    """懒加载 embedding 模型（仅用于 query 的嵌入）。"""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        _EMBEDDING_MODEL = get_dashscope_embedding(model=DefaultConfig.embedding_model)
    return _EMBEDDING_MODEL

def _load_graph_embeddings(kg_type: str, nodes: list, to_ignore_node_id: str = None) -> dict:
    """从 graph_embedding.json 加载 包含在nodes中的节点 id  -> embedding，带缓存。"""
    embedding_path = kg_type_to_embedding_path[kg_type]

    if embedding_path in _GRAPH_CACHE:
        return _GRAPH_CACHE[embedding_path]
    if not os.path.isfile(embedding_path):
        raise FileNotFoundError(f"图谱嵌入文件不存在: {embedding_path}")
    with open(embedding_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    node_embs = {}
    for node in nodes:
        node_id = node.get("id", "")
        if node_id == to_ignore_node_id:
            continue
        node_embs[node_id] = data.get(node_id, [])

    _GRAPH_CACHE[embedding_path] = node_embs
    return node_embs

def _cosine_similarity(vec1: list, vec2: list) -> float:
    try:
        v1, v2 = np.array(vec1, dtype=float), np.array(vec2, dtype=float)
        dot = np.dot(v1, v2)
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(dot / (n1 * n2))
    except Exception:
        return 0.0


def _load_graph(kg_type: str, to_ignore_node_id: str = None) -> dict:
    """加载 merged_graph_with_body.json 并构建 id->node 索引，带缓存。to_ignore_node_id为需要屏蔽的节点 id，如果为None则不屏蔽。"""
    # 屏蔽的标准为：node_id 自身节点及其 contains 的flow
    graph_path = kg_type_to_path[kg_type]

    if graph_path in _GRAPH_CACHE:
        return _GRAPH_CACHE[graph_path]
    if not os.path.isfile(graph_path):
        raise FileNotFoundError(f"知识图谱文件不存在: {graph_path}")
    with open(graph_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # 遍历 nodes 判断 to_ignore_node_id是否存在，若不存在记为 none
    if to_ignore_node_id not in [n["id"] for n in nodes]:
        to_ignore_node_id = None

    if to_ignore_node_id is not None:
        logger.info(f"to_ignore_node_id in _load_graph: {to_ignore_node_id}")
        # 获取ignore节点包含的flow
        ignored_flows = [e["v"] for e in edges if e["u"] == to_ignore_node_id and e["edge_type"] == "contains"]
        # 去除ignore节点作为源的边，包括 depends on 和 contains
        edges = [e for e in edges if e["u"] != to_ignore_node_id]
        # 去除ignore_flows节点
        nodes = [n for n in nodes if n["id"] not in ignored_flows]
        edges = [e for e in edges if e["u"] not in ignored_flows and e["v"] not in ignored_flows]
        # 去除ignore节点的body部分
        for node in nodes:
            if node["id"] == to_ignore_node_id:
                node.pop("body")
                break
    id_to_node = {n["id"]: n for n in nodes}
    _GRAPH_CACHE[graph_path] = {
        "nodes": nodes,
        "edges": edges,
        "id_to_node": id_to_node,
    }
    _load_graph_embeddings(kg_type, nodes, to_ignore_node_id)
    return _GRAPH_CACHE[graph_path]


def create_knowledge_graph_tool(
    kg_type: str = "SRP_KG",
    max_results: int = 5,
):
    """
    创建知识图谱检索工具的工厂函数。

    路径为绝对路径。语义检索时从 graph_embedding.json 加载预计算的 id->embedding。

    Args:
        kg_type: 知识图谱类型，可选值为 "SRP_KG" 或 "KG"。

    Returns:
        query_knowledge_graph(query=None, node_id=
        
        None, neighbors_only=False, use_semantic=True, max_results=5) -> str
    """
    # file_path和requirement是用来从知识图谱中屏蔽直接相关的代码内容的
    # 因此doc中并未提及这两个参数，因为LLM本质上不知道这两个参数
    def query_knowledge_graph(
        file_path: str,
        requirement: str,
        query: Optional[str] = None,
        node_id: Optional[str] = None,
        neighbors_only: bool = False,
        use_semantic: bool = True,
        node_type: Optional[str] = None,
        include_bodies: bool = False,
    ) -> str:
        """
        从SRP知识图谱中检索相关代码信息。

        Args:
            query: 请生成参考的包含注释的代码片段，用以检索代码知识图谱。use_semantic 为 True 时做语义相似检索，为 False 时做 id/label 子串匹配（大小写不敏感）。
            node_id: 节点 id（如 "afe_audio_processor.h:Start()"）。与 neighbors_only 一起使用时返回该节点的依赖/被依赖。
            neighbors_only: 为 True 且提供了 node_id 时，只返回该节点的入边、出边及邻接节点信息。
            use_semantic: 为 True 时对 query 做语义检索（embedding 相似度），为 False 时做关键词子串匹配。
            node_type: 仅保留该类 型的节点。若为SRP_KG 则为 "flow" / "submodule" / "function" / "file"，不传则不过滤。
            include_bodies: 与 neighbors_only 同用时，为 True 则返回邻居节点的 body。

        Returns:
            可读的自然段文字描述。
        """
        # 
        # 比如requirement = complete the function Run()() , file_path = main/application.cc
        # 提出 Run() 和 main\\application.h
        to_ignore_node_id = None
        try:
            # first_part获得文件名称
            first_part = os.path.basename(file_path).replace(".cc", ".h")
            last_part = requirement.split(" ")[-1][:-2] #还要去除末尾的()
            to_ignore_node_id = first_part + ":" + last_part
            logger.info(f"to_ignore_node_id: {to_ignore_node_id}")
        except Exception as e:
            logger.error(f"Error parsing file_path and requirement to get to_ignore_node_id: {e}")
        
        try:
            graph = _load_graph(kg_type, to_ignore_node_id)
        except FileNotFoundError as e:
            return str(e)

        nodes = graph["nodes"]
        edges = graph["edges"]
        id_to_node = graph["id_to_node"]

        # 1) 指定了 node_id 且 neighbors_only：返回邻居节点 dict 列表
        if node_id and neighbors_only:
            for full_id in id_to_node:
                if full_id.endswith(node_id):
                    node_id = full_id
                    break

            if node_id not in id_to_node:
                return f"""未找到节点: {node_id}。请检查 node_id 是否与图谱中的 id 一致"""
            out_edges = [(e["u"], e["v"], e.get("edge_type", "depends_on")) for e in edges if e["u"] == node_id]
            in_edges = [(e["u"], e["v"], e.get("edge_type", "depends_on")) for e in edges if e["v"] == node_id]
            neighbor_ids = [v for _, v, _ in out_edges] + [u for u, _, _ in in_edges]
            nodes_list = []
            for nid in neighbor_ids:
                if nid not in id_to_node:
                    continue
                n = id_to_node[nid]
                node_dict = {
                    "id": n.get("id", ""),
                    "label": n.get("label", n.get("id", "")),
                    "type": n.get("type", "function"),
                    "body": n.get("body", "") if include_bodies else "",
                }
                if n.get("involved_functions") is not None:
                    node_dict["involved_functions"] = n.get("involved_functions", [])
                nodes_list.append(node_dict)
            return {"nodes": nodes_list}

        # 2) 按 query 检索节点：语义检索或关键词匹配
        if query:
            q = query.strip()
            if use_semantic:
                try:
                    node_embs = _load_graph_embeddings(kg_type, nodes)
                    model = _get_embedding_model()
                    query_emb = model.embed_query(q)
                    scored = []
                    for nid, nemb in node_embs.items():
                        if nid not in id_to_node:
                            continue
                        n = id_to_node[nid]
                        if node_type and n.get("type") != node_type:
                            continue
                        sim = _cosine_similarity(query_emb, nemb)
                        scored.append((n, sim))
                    scored.sort(key=lambda x: x[1], reverse=True)
                    nodes = [n for n, _ in scored[:max_results]]
                except FileNotFoundError as e:
                    return str(e) + " 可尝试将 use_semantic 设为 False 使用关键词匹配。"
                except Exception as e:
                    return f"语义检索失败: {e}。可尝试将 use_semantic 设为 False 使用关键词匹配。"
            else:
                q_lower = q.lower()
                nodes = [
                    n
                    for n in nodes
                    if (q_lower in n.get("id", "").lower() or q_lower in n.get("label", "").lower())
                    and (not node_type or n.get("type") == node_type)
                ][:max_results]
        else:
            # 无 query：若指定了 node_id 则精确匹配该节点
            if node_id:
                if node_id in id_to_node:
                    nodes = [id_to_node[node_id]]
                else:
                    nodes = [n for n in nodes if n["id"] == node_id]
            else:
                nodes = []

        if not nodes:
            hint = f"检索条件「{query}」" if query else "当前条件"
            return f"未找到匹配的节点。请尝试放宽 {hint} 或使用 use_semantic=True 做语义检索。"

        # 3) 直接返回节点 dict 列表（submodule 带 involved_functions）
        nodes_list = []
        for n in nodes:
            node_dict = {
                "id": n.get("id", ""),
                "label": n.get("label", n.get("id", "")),
                "type": n.get("type", "function"),
                "body": n.get("body", ""),
            }
            if n.get("involved_functions") is not None:
                node_dict["involved_functions"] = n.get("involved_functions", [])
            nodes_list.append(node_dict)
        return {"nodes": nodes_list}

    return query_knowledge_graph


def create_get_system_design_tool(system_design_path: str):
    """创建 get_system_design 工具"""
    def get_system_design() -> str:
        """从 system_design.json 中获取系统设计信息"""
        file_path = system_design_path
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        modules = data.get("modules", [])
        # 获取system design中的name列表
        module_names = [m.get("name", "") for m in modules]
        return str(module_names)
    return get_system_design

def create_get_module_interface_tool(module_interface_path: str):
    """
    创建 get_module_interface 工具的工厂函数

    Args:
        module_interface_path (str): module_interface.yaml 文件的路径

    Returns:
        function: get_module_interface(keyword: str) -> str
            用于根据模块关键词查询模块接口信息的函数

    Example:
        get_module_interface = create_get_module_interface_tool('path/to/module_interface.yaml')
        interface = get_module_interface('sensor')

    """

    def get_module_interface(keyword: str) -> str:
        """
        根据关键词从 module_interface.yaml 中获取对应模块的接口信息。

        Args:
            keyword (str): 目标模块的关键词。

        Returns:
            str: 与关键词对应的模块接口内容。
        """
        file_path = module_interface_path
        with open(file_path, "r", encoding="utf-8") as f:
            module_interfaces = yaml.load(f, Loader=yaml.FullLoader)
        return module_interfaces.get(keyword, f"Module interface not found for keyword: {keyword}")

    return get_module_interface

def create_get_implementation_flow_tool(implementation_flow_path: str = None):
    """创建 get_implementation_flow 工具"""
    def get_implementation_flow(requirement: str) -> str:
        """根据需求描述从 implementation_flow.json 中获取对应的实现流程"""
        if implementation_flow_path is None:
            file_path = os.path.join(os.path.dirname(str(MODULE_INTERFACE_JSON_PATH)), "implementation_flow.json")
        else:
            file_path = implementation_flow_path
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.loads(f.read())
            if requirement in data:
                return data[requirement]
            return f"Implementation flow not found for requirement: {requirement}. Please run extract_implementation_flow first."
        except FileNotFoundError:
            return f"Implementation flow file not found at {file_path}. Please run extract_implementation_flow first."
        except Exception as e:
            return f"Error reading implementation flow from {file_path}: {str(e)}"
    return get_implementation_flow

if __name__ == "__main__":
    tool = create_knowledge_graph_tool()
    query = "application"

    print(tool(file_path="main/application.cc", requirement="complete the function SetDeviceState(DeviceState)()", query=query, node_id="main\\application.h:DeviceStateManager", neighbors_only=True, use_semantic=False, max_results=10))