# evox-server/src/core/rag/code/index/designer.py

import json
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pydantic import BaseModel
from pathlib import Path
from src.utils import get_llm, Agent, get_dashscope_embedding
from src.base import DefaultConfig
from src.core.rag.code.index.designer.designer_prompt import DESIGNER_PROMPTS
from src.core.rag.code.query.retriever.retriever import Retriever
from src.core.rag.code.storage import GraphJsonManager
from src.core.rag.code.PATH import BASE_PATH
# evox-server\src\core\rag\code\query\retriever\retriever.py

# 图结构输出模型    
class Nodes(BaseModel):
    nodes: List[Dict[str, Any]]

class Designer:
    """面向对象设计器，支持基于SOLID原则的设计生成和图转换"""
    
    def __init__(self):
        """
        初始化设计器
        
        Args:
            config: 配置字典
        """
        # 参考 generator_agent.py 的实现方式
        self.agent = Agent(get_llm(model_name=DefaultConfig.agent_model))
        self.retriever = Retriever()  
        
        # 初始化embedding模型
        self.embedding_model = get_dashscope_embedding(
            model=DefaultConfig.embedding_model,
        )
        
        # 初始化图JSON管理器
        self.graph_manager = GraphJsonManager()

    def get_nodes_by_ids(self, reference_json_path: str, relevant_ids: List[str]) -> List[Dict[str, Any]]:
        nodes = self.graph_manager.load(reference_json_path).get('nodes')
        if not nodes:
            relevant_nodes = []
        else:
            relevant_nodes = [node for node in nodes if node['id'] in relevant_ids]
        return relevant_nodes

    def get_all_nodes_and_desciptions(self, reference_json_path: str) -> List[Dict[str, Any]]:
        nodes = self.graph_manager.load(reference_json_path).get('nodes')
        if not nodes:
            return []
        return [{'id': node['id'], 'description': node['description']} for node in nodes]
    
    def get_semantic_relevant_nodes(self, reference_json_path: str, description: str) -> List[Dict[str, Any]]:
        relevant_ids = self.retriever.retrieve(description, self.graph_manager.get_embed_path(reference_json_path))
        print("In get_semantic_relevant_nodes, relevant_ids:", relevant_ids)
        return self.get_nodes_by_ids(reference_json_path, relevant_ids)

    def read_file(self, file_path: str) -> str:
        with open(BASE_PATH / file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def interface_extraction(self, file_status_path, module_interface_path):
        file_status = self.graph_manager.load(file_status_path)
        interface_dict = {}
        for item in file_status:
            if not item['in_extraction_scope']:
                continue
            code = self.read_file(item['path'])
            name = Path(item['path']).stem
            header = None if not item['header'] else self.read_file(item['header'])
            prompt = DESIGNER_PROMPTS["interface_extraction"].format(
                        code=code,
                        header=header
                    )
            result = self.agent.invoke(prompt)
            if code and header:
                interface_dict[name] = result
        self.graph_manager.save(interface_dict, module_interface_path)

    def code_to_graph_simple(
        self, 
        code: str, 
        name: str,
        header: Optional[str] = None, 
        reference_interfaces: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        使用 one_round_prompt 进行代码重构
        
        Args:
            code: 源代码内容
            name: 模块名称
            header: 头文件内容（可选）
            reference_interfaces: 参考接口节点（可选）  
        """
        prompt = DESIGNER_PROMPTS["single_responsibility"].format(
            name=name,
            source=code,
            header=header,
            reference_interfaces='\n'.join([json.dumps(node) for node in reference_interfaces])
        )
        
        result = self.agent.invoke_with_structured_output(prompt, schema=Nodes)
        return result

    def code_to_graph(self, code: str, description:str, name: str, reference_json_path: Optional[str] = None, header: Optional[str] = None)-> Dict[str, Any]:
        """
        基于功能描述生成图结构
        
        Args:
            code: 源代码内容
            description: 功能描述
            name: 模块名称
            reference_json_path: 参考图JSON文件路径
            header: 头文件内容（可选）
        """

        new_graph = {
            'nodes': []
        }
        # 分析当前模块实际依赖了哪些参考类

        try:   
            #reference_nodes_and_descriptions = self.get_semantic_relevant_nodes(reference_json_path, description)
            reference_nodes_and_descriptions = self.get_interface_and_implementation_nodes(reference_json_path)
            if not reference_nodes_and_descriptions:
                dependencies_result = {"nodes": []}
            else:
                prompt = DESIGNER_PROMPTS["analyze_dependencies"].format( 
                    what=code,
                    reference_nodes_and_descriptions=reference_nodes_and_descriptions
                )
                dependencies_result = self.agent.invoke_with_structured_output(prompt, schema=Nodes)
        except Exception as e:
            print(f"分析当前模块实际依赖了哪些参考类失败: {e}")
            dependencies_result = {"nodes": []}

        # 将功能描述分解为多个功能模块
        # 根据依赖代码的id，获取代码的实现
        relevant_nodes = self.get_nodes_by_ids(reference_json_path, [node['id'] for node in dependencies_result["nodes"]])
        prompt = DESIGNER_PROMPTS["dependency_decouple"].format(
            what=code,
            reference_nodes_and_descriptions_and_implementation=relevant_nodes
        )
        decomposition_result = self.agent.invoke_with_structured_output(prompt, schema=Nodes)
        # 遍历节点，将其中id全部替换成以.h结尾
        for node in decomposition_result["nodes"]:
            node['id'] = node['id'] + '.h'
        new_graph['nodes'].extend(decomposition_result["nodes"])

        # 基于分解的模块以及依赖的模块重构当前模块
        # 传递 interface 类型+implementation 类型的节点
        interface_nodes = [node for node in decomposition_result["nodes"] if node.get('type') == 'interface']

        prompt = DESIGNER_PROMPTS["refactor_origin_code"].format(
            header=header,
            source=code,
            name=name,
            nodes='\n'.join([json.dumps(node) for node in interface_nodes])
        )
        refactor_result = self.agent.invoke_with_structured_output(prompt, schema=Nodes)
        new_graph['nodes'].extend(refactor_result["nodes"])
        # return new_graph
        # 基于功能分解的模块重构当前模块(暂时不使用)
        prompt = DESIGNER_PROMPTS["functionality_decompose"].format(
            refactored_node='\n'.join([json.dumps(node) for node in refactor_result["nodes"]])
        )
        functionality_result = self.agent.invoke_with_structured_output(prompt, schema=Nodes)
        new_graph['nodes'].extend(functionality_result["nodes"])
        return new_graph

        nodes = decomposition_result["nodes"]
        # 获取目标节点
        next_target_nodes = [node for node in nodes]
        print("next_target_nodes:", next_target_nodes)

        # 尝试复用其他的功能模块
        # 获取参考图的embedding路径
        reference_embed_path = self.graph_manager.get_embed_path(reference_json_path)

        # 先找到对应的节点
        # 对于找到的节点，继续寻找可以复用的节点，直到没有可以复用的节点为止
        while next_target_nodes:
            target_nodes = next_target_nodes
            next_target_nodes = []
            for node in target_nodes:
                node_info = node
                description = node.get('description')
                #relevant_ids = self.retriever.retrieve(description, reference_embed_path)
                relevant_ids = []
                print("relevant_ids:", relevant_ids)
                relevant_nodes = self.get_nodes_from_json(reference_json_path, relevant_ids)
                if not relevant_nodes:
                    continue
                # 将功能模块组合为图结构
                prompt = DESIGNER_PROMPTS["decomposition_to_graph"].format(
                    node_info=node_info,
                    reference_nodes='\n'.join([json.dumps(node) for node in relevant_nodes]),
                )
                response = self.agent.invoke_with_structured_output(prompt, schema=Nodes)
                next_target_nodes.extend(response["nodes"])
                # 构建新的节点  
                new_graph['nodes'].extend(response["nodes"])
        return new_graph

    def generate_embeddings_for_nodes(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        为节点生成embedding
        """
        emb_nodes = {}
        for node in nodes:
            description = node.get('description')
            if description:
                vec = self.embedding_model.embed_query(description)
                emb_nodes[node['id']] = vec
        return emb_nodes

    def update_graph(self, reference_json_path: str, new_graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 new_graph 合并到 reference_json_path 指向的参考图中
        节点去重

        Args:
            reference_json_path: 参考图 JSON 文件路径
            new_graph: 新的图结构（包含 'nodes'）

        Returns:
            包含新增节点的图结构字典: {"nodes": [...]}
        """
        # 使用 GraphJsonManager 更新图
        result = self.graph_manager.update(reference_json_path, new_graph)
        
        # 更新embedding sidecar 图        
        emb_graph = self.generate_embeddings_for_nodes(result['nodes'])
        self.graph_manager.update_embeddings_sidecar(reference_json_path, emb_graph)
        
        # 返回新增的节点和边
        return result

    def get_file_description(self, file_path: str) -> str:
        """
        根据文件路径从JSON文件中提取文件包含的 函数节点 的描述并合并；
        
        Args:
            file_path: 文件路径，例如 "main/application.cc"
            
        Returns:
            合并后的文件描述字符串
        """
        json_path = "evox-server/.rag/xiaozhi/full_code/functions_what_graph_concurrent.json"
        
        # 加载JSON数据
        data = self.graph_manager.load(json_path)
        if not data or 'nodes' not in data:
            return ""
        
        # 过滤出包含指定文件路径的节点
        relevant_nodes = []
        for node in data['nodes']:
            node_id = node.get('id', '')
            # 检查id是否以"func:"开头且包含指定的文件路径
            if node_id.startswith('func:') and file_path in node_id:
                relevant_nodes.append(node)
        
        # 提取并合并描述
        descriptions = []
        for node in relevant_nodes:
            description = node.get('description', '')
            if description:
                descriptions.append(description)
        
        # 合并所有描述
        merged_description = '\n\n'.join(descriptions)
        return merged_description

    def find_header_file(self, input_path: str, base_path: str) -> Optional[str]:
        """
        查找同名的 .h 头文件
        
        Args:
            input_path: 输入文件路径（例如 source.cc）
            base_path: 基础路径，用于递归搜索
            
        Returns:
            头文件内容，如果未找到则返回 None
        """
        # 首先尝试相同位置的头文件
        header_path = os.path.splitext(input_path)[0] + '.h'
        if os.path.exists(header_path):
            try:
                with open(header_path, 'r', encoding='utf-8') as f:
                    header_content = f.read()
                print(f"找到头文件（相同位置）: {header_path}")
                return header_content
            except Exception as e:
                print(f"读取头文件失败: {e}")
        
        # 如果相同位置未找到，在base_path下递归搜索
        module_name = os.path.splitext(os.path.basename(input_path))[0]
        header_filename = module_name + '.h'
        
        if os.path.exists(base_path):
            for root, dirs, files in os.walk(base_path):
                if header_filename in files:
                    found_header_path = os.path.join(root, header_filename)
                    try:
                        with open(found_header_path, 'r', encoding='utf-8') as f:
                            header_content = f.read()
                        print(f"找到头文件（递归搜索）: {found_header_path}")
                        return header_content
                    except Exception as e:
                        print(f"读取头文件失败: {e}")
                        continue
        
        print(f"未找到头文件: {header_filename}")
        return None

    def should_refactor_based_on_dependency(
        self,
        cur_graph: Dict[str, Any],
        dependent_graph: Dict[str, Any],
        current_file: str,
        dependent_file: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        基于当前文件与下游文件的图结果，判断下游文件是否需要重新重构。

        Returns:
            (need_refactor, graph)
        """
        prompt = DESIGNER_PROMPTS["dependency_propagation_decision"].format(
            current_file=current_file,
            dependent_file=dependent_file,
            current_graph=json.dumps(cur_graph, ensure_ascii=False, indent=2),
            dependent_graph=json.dumps(dependent_graph, ensure_ascii=False, indent=2),
        )

        decision = self.agent.invoke_with_structured_output(
            prompt, schema=PropagationDecision
        )

        if decision.need_refactor:
            if decision.updated_graph is None:
                raise ValueError(
                    f"Agent 返回需要重构，但缺失 updated_graph: {dependent_file}"
                )
            return True, decision.updated_graph

        return False, dependent_graph

if __name__ == "__main__":
    # file_list = ["file:main/application.cc"]
    file_list = ["file:main/settings.cc"]
    import time

    designer = Designer()
    file_status_path = "evox-server/.rag/xiaozhi/full_code/file_status.json"
    module_interface_path = "evox-server/.rag/xiaozhi/full_code/module_interface.json"
    designer.interface_extraction(file_status_path, module_interface_path)
    exit(0)
    base_path = "D:/Download/github/xiaozhi-esp32"
    #reference_json_path = "evox-server/.rag/xiaozhi/designer_11_07/test_design_3.json"
    output_dir = "evox-server/.rag/xiaozhi/designer_11_17_6/"
    start_time = time.time()
    processed_count = 0

    for file in file_list:
        input_path = os.path.join(base_path, file[5:])  
        with open(input_path, 'r', encoding='utf-8') as f:
            code = f.read()
        # Extract module name from file path
        module_name = os.path.splitext(os.path.basename(input_path))[0]
        print(f"module_name: {module_name}")
        # description = designer.get_file_description(module_name)
        # print(description)
        
        # # 尝试获取同名的 .h 文件（先在相同位置查找，如果未找到则在base_path下递归搜索）
        header_content = designer.find_header_file(input_path, base_path)
        
        graph_dict = designer.code_to_graph_simple(
            code=code, 
            name=module_name,
            header=header_content
            # 如果需要参考节点，可以添加：reference_json_path="path/to/reference.json"
        )
        output_path = os.path.join(output_dir, f"{module_name}.json")
        # new_nodes = designer.update_graph(output_path, graph_dict)
        designer.graph_manager.save(graph_dict, output_path)
        processed_count += 1

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Processed {processed_count} files in {elapsed_time:.2f} seconds.")
