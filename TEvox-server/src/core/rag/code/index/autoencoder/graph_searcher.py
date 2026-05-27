import json
import os
import sys
import networkx as nx
from typing import Dict, List, Set, Optional, Union, Any, Tuple
from datetime import datetime
from enum import Enum
from src.utils import logger, Agent
from src.base import DefaultConfig
from src.utils.llm import get_embedding

class NodeType(Enum):
    """图节点类型枚举"""
    FILE = "file"
    FUNCTION = "function"
    GLOBAL_VARIABLE = "global_variable"
    FOLDER = "folder"
    STRUCT = "struct"
    CLASS = "class"
    FIELD = "field"

class EdgeType(Enum):
    """图边类型枚举
````markdown
|            | 文件夹            | 文件              | 函数                                  | 全局变量                                     |
| :--------- | :---------------- | :---------------- | :------------------------------------ | :------------------------------------------- |
| **文件夹**   | FOLDER_CONTAINS   | FOLDER_CONTAINS   |                                       |                                              |
| **文件**     |                   | FILE_REFERENCES   | CONTAINS_FUNCTION                     | VARIABLE_REFERENCES<br>CONTAINS_VARIABLE     |
| **函数**     |                   |                   | FUNCTION_CALLS<br>FUNCTION_INCOMING   | FUNCTION_USES_VARIABLE                       |
| **全局变量** |                   |                   |                                       |                                              |
````
    """
    FILE_REFERENCES = "file_references" # 一个文件引用了另一个文件，包括一个文件引用了另一个文件的函数和全局变量
    FUNCTION_CALLS = "function_calls"
    VARIABLE_REFERENCES = "variable_references"
    CONTAINS_FUNCTION = "contains_function"
    CONTAINS_VARIABLE = "contains_variable"
    FOLDER_CONTAINS = "folder_contains"
    FUNCTION_USES_VARIABLE = "function_uses_variable"  # 函数使用变量
    FUNCTION_INCOMING = "function_incoming" # 
    CLASS_CONTAINS_METHOD = "class_contains_method"
    CLASS_CONTAINS_VARIABLE = "class_contains_variable"
    STRUCT_AND_INSTANCE = "struct_and_instance" # 结构体和它的实例的关系
    CLASS_AND_INSTANCE = "class_and_instance" # class和它的实例的关系


class GraphSearcher:
    """图搜索器类，用于图的索引、检索和查询操作"""
    
    def __init__(self, graph: nx.DiGraph = None):
        """
        初始化图搜索器
        
        Args:
            graph: NetworkX有向图实例，如果为None则创建空图
        """
        self.graph = graph if graph is not None else nx.DiGraph()
        self._init_embedding_model()
    
    def _init_embedding_model(self):
        """初始化Embedding模型"""
        try:
            self.embedding_model = get_embedding(
                openai_api_base=DefaultConfig.embedding_api_base,
                openai_api_key=DefaultConfig.embedding_api_key,
                model_name=DefaultConfig.embedding_model,
            )
            logger.info("Initialized embedding model in GraphSearcher")
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {str(e)}")
            self.embedding_model = None
    
    def set_graph(self, graph: nx.DiGraph):
        """设置要操作的图"""
        self.graph = graph
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """获取图的统计信息"""
        node_types = {}
        edge_types = {}
        
        # 统计节点类型
        for node_id, node_data in self.graph.nodes(data=True):
            node_type = node_data.get('node_type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        # 统计边类型
        for source, target, edge_data in self.graph.edges(data=True):
            edge_type = edge_data.get('edge_type', 'unknown')
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        # 计算特定类型的节点数量（用于测试脚本兼容性）
        files = node_types.get('file', 0)
        functions = node_types.get('function', 0)
        variables = node_types.get('global_variable', 0)
        folders = node_types.get('folder', 0)
        
        return {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'node_types': node_types,
            'edge_types': edge_types,
            'is_directed': self.graph.is_directed(),
            'density': nx.density(self.graph),
            'number_of_components': nx.number_weakly_connected_components(self.graph) if self.graph.is_directed() else nx.number_connected_components(self.graph),
            # 为测试脚本提供的特定统计
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges(),
            'files': files,
            'functions': functions,
            'variables': variables,
            'folders': folders
        }
    
    def find_nodes_by_type(self, node_type: NodeType) -> List[str]:
        """根据类型查找节点"""
        return [node_id for node_id, node_data in self.graph.nodes(data=True) 
                if node_data.get('node_type') == node_type.value]
    
    def find_nodes_by_file(self, file_path: str) -> List[str]:
        """查找属于特定文件的所有节点"""
        normalized_path = os.path.normpath(file_path)
        return [node_id for node_id, node_data in self.graph.nodes(data=True) 
                if node_data.get('file_path') and os.path.normpath(node_data['file_path']) == normalized_path]
    
    def find_nodes_by_name(self, name: str, node_type: NodeType = None) -> List[str]:
        """根据名称查找节点，可选择指定节点类型"""
        results = []
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('name') == name:
                if node_type is None or node_data.get('node_type') == node_type.value:
                    results.append(node_id)
        return results
    
    def find_nodes_by_name_pattern(self, pattern: str, node_type: NodeType = None) -> List[str]:
        """根据名称模式查找节点（支持通配符）"""
        import fnmatch
        results = []
        for node_id, node_data in self.graph.nodes(data=True):
            name = node_data.get('name', '')
            if fnmatch.fnmatch(name, pattern):
                if node_type is None or node_data.get('node_type') == node_type.value:
                    results.append(node_id)
        return results
    
    def get_node_details(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点的详细信息"""
        if node_id not in self.graph:
            return None
        
        node_data = self.graph.nodes[node_id]
        #print(node_data)
        return {
            'id': node_id,
            'type': node_data.get('node_type'),
            'name': node_data.get('name'),
            'file_path': node_data.get('file_path'),
            'metadata': node_data.get('metadata', {}),
            'encoding': node_data.get('encoding', {}),
            'degree': self.graph.degree(node_id),
            'in_degree': self.graph.in_degree(node_id),
            'out_degree': self.graph.out_degree(node_id)
        }
    
    def get_neighbors(self, node_id: str, direction: str = 'both') -> Dict[str, List[str]]:
        """
        获取节点的邻居
        
        Args:
            node_id: 节点ID
            direction: 方向，可选值：'in', 'out', 'both'
            
        Returns:
            包含邻居信息的字典
        """
        if node_id not in self.graph:
            return {'predecessors': [], 'successors': []}
        
        result = {}
        
        if direction in ['in', 'both']:
            result['predecessors'] = list(self.graph.predecessors(node_id))
        
        if direction in ['out', 'both']:
            result['successors'] = list(self.graph.successors(node_id))
        
        return result
    
    def get_function_call_chain(self, start_function_id: str, max_depth: int = 5) -> List[List[str]]:
        """获取函数调用链"""
        chains = []
        
        def dfs(current_id, path, depth):
            if depth > max_depth:
                return
            
            path.append(current_id)
            successors = [target for source, target, edge_data in self.graph.edges(current_id, data=True)
                         if edge_data.get('edge_type') == EdgeType.FUNCTION_CALLS.value]
            
            if not successors:
                chains.append(path.copy())
            else:
                for successor in successors:
                    if successor not in path:  # 避免循环
                        dfs(successor, path, depth + 1)
            
            path.pop()
        
        dfs(start_function_id, [], 0)
        return chains
    
    def get_function_call_tree(self, start_function_id: str, max_depth: int = 5) -> Dict[str, Any]:
        """获取函数调用树（树形结构）"""
        if start_function_id not in self.graph:
            return {}
        
        visited = set()
        
        def build_tree(current_id, depth):
            if depth > max_depth or current_id in visited:
                return {'id': current_id, 'children': [], 'truncated': True}
            
            visited.add(current_id)
            
            successors = [target for source, target, edge_data in self.graph.edges(current_id, data=True)
                         if edge_data.get('edge_type') == EdgeType.FUNCTION_CALLS.value]
            
            children = []
            for successor in successors:
                children.append(build_tree(successor, depth + 1))
            
            visited.remove(current_id)
            
            return {
                'id': current_id,
                'name': self.graph.nodes[current_id].get('name', ''),
                'file_path': self.graph.nodes[current_id].get('file_path', ''),
                'children': children,
                'truncated': False
            }
        
        return build_tree(start_function_id, 0)
    
    def find_cycles(self) -> List[List[str]]:
        """查找图中的循环依赖"""
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except nx.NetworkXError:
            return []
    
    def get_shortest_path(self, source: str, target: str) -> Optional[List[str]]:
        """获取两个节点间的最短路径"""
        try:
            return nx.shortest_path(self.graph, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def get_connected_components(self) -> List[List[str]]:
        """获取连通分量"""
        if self.graph.is_directed():
            return [list(component) for component in nx.weakly_connected_components(self.graph)]
        else:
            return [list(component) for component in nx.connected_components(self.graph)]
    
    def search_by_edge_type(self, edge_type: EdgeType, source_node: str = None, target_node: str = None) -> List[Dict[str, str]]:
        """
        根据边类型搜索边
        
        Args:
            edge_type: 边类型
            source_node: 源节点ID（可选）
            target_node: 目标节点ID（可选）
            
        Returns:
            匹配的边列表
        """
        edges = []
        
        for source, target, edge_data in self.graph.edges(data=True):
            if edge_data.get('edge_type') != edge_type.value:
                continue
                
            if source_node is not None and source != source_node:
                continue
                
            if target_node is not None and target != target_node:
                continue
            
            edges.append({
                'source': source,
                'target': target,
                'type': edge_data.get('edge_type'),
                'metadata': edge_data.get('metadata', {})
            })
        
        return edges
    
    def get_file_dependencies(self, file_path: str) -> Dict[str, List[str]]:
        """
        获取文件的依赖关系
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含依赖和被依赖文件的字典
        """
        # 标准化路径
        normalized_path = os.path.normpath(file_path)
        
        # 查找文件节点
        file_nodes = [node_id for node_id, node_data in self.graph.nodes(data=True)
                      if (node_data.get('node_type') == 'file' and 
                          node_data.get('file_path') and 
                          os.path.normpath(node_data['file_path']) == normalized_path)]
        
        if not file_nodes:
            return {'dependencies': [], 'dependents': []}
        
        file_node = file_nodes[0]
        dependencies = []
        dependents = []
        
        # 查找依赖的文件（该文件引用的其他文件）
        for source, target, edge_data in self.graph.edges(file_node, data=True):
            if edge_data.get('edge_type') == EdgeType.FILE_REFERENCES.value:
                target_data = self.graph.nodes.get(target, {})
                if target_data.get('node_type') == 'file':
                    dependencies.append(target_data.get('file_path', ''))
        
        # 查找依赖该文件的其他文件
        for source, target, edge_data in self.graph.edges(data=True):
            if (target == file_node and 
                edge_data.get('edge_type') == EdgeType.FILE_REFERENCES.value):
                source_data = self.graph.nodes.get(source, {})
                if source_data.get('node_type') == 'file':
                    dependents.append(source_data.get('file_path', ''))
        
        return {
            'dependencies': dependencies,
            'dependents': dependents
        }
    
    def search_functions_with_body(self, pattern: str = None) -> List[Dict[str, Any]]:
        """
        搜索包含函数体的函数节点
        
        Args:
            pattern: 可选的名称模式
            
        Returns:
            匹配的函数列表，包含函数体信息
        """
        import fnmatch
        
        functions = []
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('node_type') != 'function':
                continue
            
            name = node_data.get('name', '')
            if pattern and not fnmatch.fnmatch(name, pattern):
                continue
            
            body = node_data.get('metadata', {}).get('body')
            is_declaration_only = node_data.get('metadata', {}).get('is_declaration_only', False)
            
            if body and not is_declaration_only:
                functions.append({
                    'id': node_id,
                    'name': name,
                    'file_path': node_data.get('file_path', ''),
                    'body': body,
                    'body_length': len(body),
                    'is_declaration_only': is_declaration_only
                })
        
        return functions
    
    def search_excluded_function_declarations(self) -> List[Dict[str, Any]]:
        """
        搜索被排除的函数声明（用于调试和统计）
        
        Returns:
            被排除的函数声明信息列表
        """
        # 这个方法主要用于统计，因为被排除的声明不会被添加到图中
        # 实际使用时需要结合原始分析结果来获取完整信息
        declarations = []
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('node_type') != 'function':
                continue
            
            is_declaration_only = node_data.get('metadata', {}).get('is_declaration_only', False)
            if is_declaration_only:
                declarations.append({
                    'id': node_id,
                    'name': node_data.get('name', ''),
                    'file_path': node_data.get('file_path', ''),
                    'body': node_data.get('metadata', {}).get('body', ''),
                    'is_declaration_only': True
                })
        
        return declarations
    
    def get_function_statistics(self) -> Dict[str, Any]:
        """
        获取函数相关的统计信息
        
        Returns:
            包含函数统计信息的字典
        """
        stats = {
            'total_functions': 0,
            'functions_with_body': 0,
            'function_declarations': 0,
            'average_body_length': 0,
            'files_with_functions': set()
        }
        
        body_lengths = []
        
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('node_type') != 'function':
                continue
            
            stats['total_functions'] += 1
            file_path = node_data.get('file_path', '')
            if file_path:
                stats['files_with_functions'].add(file_path)
            
            body = node_data.get('metadata', {}).get('body')
            is_declaration_only = node_data.get('metadata', {}).get('is_declaration_only', False)
            
            if body and not is_declaration_only:
                stats['functions_with_body'] += 1
                body_lengths.append(len(body))
            elif is_declaration_only:
                stats['function_declarations'] += 1
        
        if body_lengths:
            stats['average_body_length'] = sum(body_lengths) // len(body_lengths)
        
        stats['files_with_functions'] = len(stats['files_with_functions'])
        
        return stats
    
    def export_subgraph(self, node_ids: List[str]) -> nx.DiGraph:
        """
        导出包含指定节点的子图
        
        Args:
            node_ids: 要包含的节点ID列表
            
        Returns:
            子图
        """
        return self.graph.subgraph(node_ids).copy()
    
    def save_graph_to_json(self, output_file: str, include_metadata: bool = True):
        """将图保存为JSON文件"""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 转换图为可序列化的格式
        graph_data = {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'nodes_count': self.graph.number_of_nodes(),
                'edges_count': self.graph.number_of_edges(),
                'graph_type': 'directed'
            },
            'nodes': [],
            'edges': []
        }
        
        # 添加节点数据
        for node_id, node_data in self.graph.nodes(data=True):
            node_info = {
                'id': node_id,
                'type': node_data.get('node_type'),
                'name': node_data.get('name'),
                'file_path': node_data.get('file_path'),
                'body': node_data.get('metadata', {}).get('body')
            }
            if include_metadata:
                # 从metadata中移除body，避免重复
                metadata = dict(node_data.get('metadata', {}))
                if 'body' in metadata:
                    del metadata['body']
                node_info['metadata'] = metadata
            
            # 添加encoding字段，确保始终包含
            encoding = node_data.get('encoding', {
                'what': None,
                'how': None,
                'embedding': None
            })
            node_info['encoding'] = encoding
                
            graph_data['nodes'].append(node_info)
        
        # 添加边数据
        for source, target, edge_data in self.graph.edges(data=True):
            edge_info = {
                'source': source,
                'target': target,
                'type': edge_data.get('edge_type')
            }
            if include_metadata:
                edge_info['metadata'] = edge_data.get('metadata', {})
            graph_data['edges'].append(edge_info)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        print(f"Graph saved to {output_file}")
        print(f"Nodes: {len(graph_data['nodes'])}, Edges: {len(graph_data['edges'])}")
    
    def load_graph_from_json(self, input_file: str) -> bool:
        """从JSON文件加载图"""
        if not os.path.exists(input_file):
            print(f"File not found: {input_file}")
            return False
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
            
            # 清空当前图
            self.graph.clear()
            
            # 添加节点
            for node_info in graph_data.get('nodes', []):
                metadata = node_info.get('metadata', {})
                # 将body字段添加到metadata中
                if 'body' in node_info:
                    metadata['body'] = node_info['body']
                
                # 获取encoding字段，如果不存在则使用默认值
                encoding = node_info.get('encoding', {
                    'what': None,
                    'how': None,
                    'embedding': None
                })
                
                self.graph.add_node(
                    node_info['id'],
                    node_type=node_info.get('type'),
                    name=node_info.get('name'),
                    file_path=node_info.get('file_path'),
                    metadata=metadata,
                    encoding=encoding
                )
            
            # 添加边
            for edge_info in graph_data.get('edges', []):
                self.graph.add_edge(
                    edge_info['source'],
                    edge_info['target'],
                    edge_type=edge_info.get('type'),
                    metadata=edge_info.get('metadata', {})
                )
            
            metadata = graph_data.get('metadata', {})
            print(f"Graph loaded from {input_file}")
            print(f"Created at: {metadata.get('created_at', 'Unknown')}")
            print(f"Nodes: {self.graph.number_of_nodes()}, Edges: {self.graph.number_of_edges()}")
            return True
            
        except Exception as e:
            print(f"Error loading graph from {input_file}: {e}")
            return False
    
    def export_to_networkx_format(self, output_file: str):
        """导出为NetworkX兼容的格式（用于其他工具分析）"""
        nx.write_gexf(self.graph, output_file)
        print(f"Graph exported to GEXF format: {output_file}")
    
    def find_potential_duplicate_functions(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        查找可能重复的函数节点（基于函数基本名称）
        
        Returns:
            包含可能重复函数的字典，键为函数基本名称，值为节点信息列表
        """
        function_groups = {}
        
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('node_type') != 'function':
                continue
            
            func_name = node_data.get('name', '')
            if not func_name:
                continue
            
            # 提取函数基础名称（去掉参数部分）
            base_name = func_name.split('(')[0] if '(' in func_name else func_name
            
            if base_name not in function_groups:
                function_groups[base_name] = []
            
            function_groups[base_name].append({
                'id': node_id,
                'full_name': func_name,
                'file_path': node_data.get('file_path', ''),
                'metadata': node_data.get('metadata', {})
            })
        
        # 只返回有多个节点的函数组（可能的重复）
        potential_duplicates = {
            base_name: nodes 
            for base_name, nodes in function_groups.items() 
            if len(nodes) > 1
        }
        
        return potential_duplicates
    
    def generate_duplicate_functions_report(self) -> str:
        """
        生成重复函数的报告
        
        Returns:
            格式化的报告字符串
        """
        duplicates = self.find_potential_duplicate_functions()
        
        if not duplicates:
            return "✅ 未发现潜在的重复函数节点"
        
        report = f"⚠️  发现 {len(duplicates)} 个可能重复的函数:\n"
        report += "=" * 60 + "\n\n"
        
        for base_name, nodes in duplicates.items():
            report += f"🔍 函数: {base_name} (发现 {len(nodes)} 个节点)\n"
            report += "-" * 40 + "\n"
            
            for i, node in enumerate(nodes, 1):
                report += f"  {i}. ID: {node['id']}\n"
                report += f"     完整名称: {node['full_name']}\n"
                report += f"     文件路径: {node['file_path']}\n"
                
                # 显示函数体信息（如果有）
                body = node['metadata'].get('body')
                if body:
                    body_preview = body[:100] + "..." if len(body) > 100 else body
                    report += f"     函数体预览: {body_preview.replace(chr(10), ' ')}\n"
                else:
                    report += f"     函数体: 无\n"
                
                is_declaration = node['metadata'].get('is_declaration_only', False)
                report += f"     仅声明: {'是' if is_declaration else '否'}\n"
                report += "\n"
            
            report += "\n"
        
        return report 
    
    def get_node_body(self, node_id: str) :
        """
        检查节点是否有body属性
        """
        node_details = self.graph.nodes[node_id]
        metadata = node_details.get('metadata', {})
        if metadata:
            body = metadata.get('body')
            if body is not None:
                return body
        return None

    def generate_embedding_for_query(self, query: str) -> Optional[List[float]]:
        """为查询文本生成embedding向量
        
        Args:
            query: 查询文本
            
        Returns:
            Optional[List[float]]: embedding向量，如果失败返回None
        """
        if not self.embedding_model:
            return None
        
        try:
            embedding = self.embedding_model.embed_query(query)
            return embedding
        except Exception as e:
            return None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度
        
        Args:
            vec1: 第一个向量
            vec2: 第二个向量
            
        Returns:
            float: 余弦相似度，范围[-1, 1]
        """
        import math
        
        if len(vec1) != len(vec2):
            return 0.0
        
        # 计算点积
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # 计算向量的模长
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        # 避免除零
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        
        return dot_product / (norm1 * norm2)

    def search_by_embedding(self, query: str, json_file_path: str = None, 
                          top_k: int = 10, min_similarity: float = 0.0) -> List[Dict[str, Any]]:
        """基于embedding相似度搜索节点
        
        Args:
            query: 查询文本
            json_file_path: JSON文件路径，如果为None则搜索内存中的图
            top_k: 返回的最相似节点数量
            min_similarity: 最小相似度阈值
            
        Returns:
            List[Dict[str, Any]]: 匹配的节点列表，按相似度降序排列
        """
        if not self.embedding_model:
            return []
        
        # 为查询生成embedding
        query_embedding = self.generate_embedding_for_query(query)
        if query_embedding is None:
            return []
        
        node_similarities = []
        
        if json_file_path:
            # 从JSON文件搜索
            if not os.path.exists(json_file_path):
                return []
            
            try:
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    graph_data = json.load(f)
                nodes_data = graph_data.get('nodes', [])
            except Exception as e:
                return []
        else:
            # 从内存图搜索
            nodes_data = [
                {
                    'id': node_id,
                    'type': node_data.get('node_type'),
                    'name': node_data.get('name'),
                    'file_path': node_data.get('file_path'),
                    'encoding': node_data.get('encoding', {}),
                    'metadata': node_data.get('metadata', {}),
                    'body': node_data.get('metadata', {}).get('body')
                }
                for node_id, node_data in self.graph.nodes(data=True)
            ]
        
        # 遍历节点计算相似度
        for node in nodes_data:
            encoding = node.get('encoding', {})
            node_embedding = encoding.get('embedding')
            
            if node_embedding is None:
                continue
            similarity = self._cosine_similarity(query_embedding, node_embedding)
            
            if similarity >= min_similarity:
                node_info = {
                    'id': node.get('id'),
                    'type': node.get('type'),
                    'name': node.get('name'),
                    'file_path': node.get('file_path'),
                    'similarity_score': similarity,
                    'what': encoding.get('what'),
                    'how': encoding.get('how'),
                    'metadata': node.get('metadata', {}),
                    'body': node.get('body')
                }
                node_similarities.append(node_info)
        
        # 按相似度降序排序并返回top_k结果
        node_similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
        print(f"node_similarities: {node_similarities[:top_k]}")
        return node_similarities[:top_k]

    def embedding_search_with_neighbors(self, json_file_path: str, query: str, 
                                             top_k: int = 1, min_similarity: float = 0.0, hop: int = 1) -> Dict[str, Any]:
        """搜索最相似节点并获取其多层邻居节点信息
        
        Args:
            json_file_path: JSON文件路径
            query: 查询文本
            top_k: 返回的最相似节点数量（默认为1，即最相似的节点）
            min_similarity: 最小相似度阈值
            hop: 搜索邻居的层数，默认为1（直接邻居）
            
        Returns:
            Dict[str, Any]: 搜索结果，包含最相似节点和其多层邻居节点信息
        """
        # 步骤1：读取JSON文件并转换为nx图结构
        print(f"📁 正在加载JSON文件: {json_file_path}")
        if not self.load_graph_from_json(json_file_path):
            return {"error": f"Failed to load graph from {json_file_path}"}
        
        print(f"✅ 图加载成功: {self.graph.number_of_nodes()} 个节点, {self.graph.number_of_edges()} 条边")
        
        # 步骤2：为查询生成embedding并获取最相似的节点
        print(f"🔍 正在搜索与查询最相似的节点...")
        print(f"查询内容: {query}")
        
        most_similar_nodes = self.search_by_embedding(
            query=query, 
            json_file_path=json_file_path,  # 使用内存中的图
            top_k=top_k, 
            min_similarity=min_similarity
        )
        
        if not most_similar_nodes:
            return {"error": "No similar nodes found", "query": query}
        
        # 为所有相似节点获取多层邻居节点信息
        all_similar_nodes_results = []
        
        for node_idx, similar_node in enumerate(most_similar_nodes):
            node_id = similar_node['id']
            
            print(f"🎯 处理第 {node_idx + 1} 个相似节点:")
            print(f"  ID: {node_id}")
            print(f"  名称: {similar_node.get('name', 'N/A')}")
            print(f"  类型: {similar_node.get('type', 'N/A')}")
            print(f"  相似度分数: {similar_node['similarity_score']:.4f}")
            
            # 获取当前节点的多层邻居节点及其encoding信息
            print(f"🔗 正在获取节点 {node_id} 的 {hop} 层邻居节点...")
            
            # 使用BFS搜索多层邻居
            neighbor_details = []
            visited = set()
            current_layer = {node_id}  # 从当前相似节点开始
            visited.add(node_id)  # 标记起始节点为已访问，避免包含自己
            
            for current_hop in range(1, hop + 1):
                next_layer = set()
                layer_neighbors = []
                
                print(f"  🔍 正在搜索第 {current_hop} 层邻居...")
                
                for current_node in current_layer:
                    # 获取当前节点的直接邻居
                    neighbors_info = self.get_neighbors(current_node, direction='both')
                    predecessors = neighbors_info.get('predecessors', [])
                    successors = neighbors_info.get('successors', [])
                    
                    # 处理前驱节点
                    for pred_id in predecessors:
                        if pred_id not in visited:
                            visited.add(pred_id)
                            next_layer.add(pred_id)
                            
                            pred_details = self.get_node_details(pred_id)
                            if pred_details:
                                encoding = pred_details.get('encoding', {})
                                layer_neighbors.append({
                                    'id': pred_id,
                                    'name': pred_details.get('name', 'N/A'),
                                    'type': pred_details.get('type', 'N/A'),
                                    'file_path': pred_details.get('file_path', 'N/A'),
                                    'relation': 'predecessor',
                                    'hop_level': current_hop,
                                    'parent_node': current_node,
                                    'what': encoding.get('what', None),
                                    'how': encoding.get('how', None)
                                })
                    
                    # 处理后继节点
                    for succ_id in successors:
                        if succ_id not in visited:
                            visited.add(succ_id)
                            next_layer.add(succ_id)
                            
                            succ_details = self.get_node_details(succ_id)
                            if succ_details:
                                encoding = succ_details.get('encoding', {})
                                layer_neighbors.append({
                                    'id': succ_id,
                                    'name': succ_details.get('name', 'N/A'),
                                    'type': succ_details.get('type', 'N/A'),
                                    'file_path': succ_details.get('file_path', 'N/A'),
                                    'relation': 'successor',
                                    'hop_level': current_hop,
                                    'parent_node': current_node,
                                    'what': encoding.get('what', None),
                                    'how': encoding.get('how', None)
                                })
                
                # 添加当前层的邻居到总结果中
                neighbor_details.extend(layer_neighbors)
                print(f"    ✅ 第 {current_hop} 层找到 {len(layer_neighbors)} 个邻居节点")
                
                # 如果没有更多邻居，提前结束
                if not next_layer:
                    print(f"    ⚠️  第 {current_hop} 层后没有更多邻居节点，搜索结束")
                    break
                
                # 准备下一层搜索
                current_layer = next_layer
            
            # 按层级分组统计
            neighbors_by_hop = {}
            for neighbor in neighbor_details:
                hop_level = neighbor['hop_level']
                if hop_level not in neighbors_by_hop:
                    neighbors_by_hop[hop_level] = []
                neighbors_by_hop[hop_level].append(neighbor)
            
            print(f"👥 节点 {node_id} 总共找到 {len(neighbor_details)} 个邻居节点（{hop} 层内）:")
            for hop_level in sorted(neighbors_by_hop.keys()):
                level_neighbors = neighbors_by_hop[hop_level]
                print(f"  第 {hop_level} 层: {len(level_neighbors)} 个节点")
                
                for i, neighbor in enumerate(level_neighbors, 1):
                    print(f"    {i}. ID: {neighbor['id']} ({neighbor['relation']} -> {neighbor['parent_node']})")
                    print(f"       名称: {neighbor['name']}")
                    print(f"       类型: {neighbor['type']}")
                    if neighbor['what']:
                        what_preview = neighbor['what'][:50] + "..." if len(neighbor['what']) > 50 else neighbor['what']
                        print(f"       What: {what_preview}")
                    if neighbor['how']:
                        how_preview = neighbor['how'][:50] + "..." if len(neighbor['how']) > 50 else neighbor['how']
                        print(f"       How: {how_preview}")
                    print()
            
            # 构建当前节点的结果
            node_result = {
                "node_index": node_idx + 1,
                "similar_node": {
                    "id": similar_node['id'],
                    "name": similar_node.get('name'),
                    "type": similar_node.get('type'),
                    "file_path": similar_node.get('file_path'),
                    "similarity_score": similar_node['similarity_score'],
                    "what": similar_node.get('what'),
                    "how": similar_node.get('how')
                },
                "neighbors": neighbor_details,
                "neighbors_by_hop": neighbors_by_hop,
                "neighbors_count": {
                    "total": len(neighbor_details),
                    "by_hop": {str(hop_level): len(neighbors) for hop_level, neighbors in neighbors_by_hop.items()}
                }
            }
            
            all_similar_nodes_results.append(node_result)
            print(f"✅ 节点 {node_id} 处理完成\n")
        
        # 构建最终返回结果
        result = {
            "success": True,
            "query": query,
            "hop_level": hop,
            "top_k": top_k,
            "graph_stats": {
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges()
            },
            "similar_nodes_count": len(most_similar_nodes),
            "all_similar_nodes_results": all_similar_nodes_results,
            "summary": {
                "total_neighbors_found": sum(len(node_result["neighbors"]) for node_result in all_similar_nodes_results),
                "nodes_with_neighbors": len([node_result for node_result in all_similar_nodes_results if node_result["neighbors_count"]["total"] > 0])
            }
        }
        
        return result


    def embedding_search_with_neighbors_inside(self, json_file_path: str, query: str, 
                                             top_k: int = 1, min_similarity: float = 0.0, hop: int = 1) -> Dict[str, Any]:
        """搜索最相似节点并获取其多层邻居节点信息（邻居节点限制在top_k范围内）
        
        Args:
            json_file_path: JSON文件路径
            query: 查询文本
            top_k: 返回的最相似节点数量
            min_similarity: 最小相似度阈值
            hop: 搜索邻居的层数，默认为1（直接邻居）
            
        Returns:
            Dict[str, Any]: 搜索结果，包含最相似节点和其多层邻居节点信息（邻居节点限制在top_k范围内）
        """
        # 步骤1：读取JSON文件并转换为nx图结构
        print(f"📁 正在加载JSON文件: {json_file_path}")
        if not self.load_graph_from_json(json_file_path):
            return {"error": f"Failed to load graph from {json_file_path}"}
        
        print(f"✅ 图加载成功: {self.graph.number_of_nodes()} 个节点, {self.graph.number_of_edges()} 条边")
        
        # 步骤2：为查询生成embedding并获取最相似的节点
        print(f"🔍 正在搜索与查询最相似的节点...")
        print(f"查询内容: {query}")
        
        most_similar_nodes = self.search_by_embedding(
            query=query, 
            json_file_path=json_file_path,  # 使用内存中的图
            top_k=top_k, 
            min_similarity=min_similarity
        )
        
        if not most_similar_nodes:
            return {"error": "No similar nodes found", "query": query}
        
        # 步骤3：构建top_k节点的ID集合，用于邻居过滤
        top_k_node_ids = set(node['id'] for node in most_similar_nodes)
        print(f"🎯 top_k节点ID集合: {top_k_node_ids}")
        
        # 为所有相似节点获取多层邻居节点信息（限制在top_k范围内）
        all_similar_nodes_results = []
        
        for node_idx, similar_node in enumerate(most_similar_nodes):
            node_id = similar_node['id']
            
            print(f"🎯 处理第 {node_idx + 1} 个相似节点:")
            print(f"  ID: {node_id}")
            print(f"  名称: {similar_node.get('name', 'N/A')}")
            print(f"  类型: {similar_node.get('type', 'N/A')}")
            print(f"  相似度分数: {similar_node['similarity_score']:.4f}")
            
            # 获取当前节点的多层邻居节点及其encoding信息（限制在top_k范围内）
            print(f"🔗 正在获取节点 {node_id} 的 {hop} 层邻居节点（限制在top_k范围内）...")
            
            # 使用BFS搜索多层邻居
            neighbor_details = []
            visited = set()
            current_layer = {node_id}  # 从当前相似节点开始
            visited.add(node_id)  # 标记起始节点为已访问，避免包含自己
            
            for current_hop in range(1, hop + 1):
                next_layer = set()
                layer_neighbors = []
                
                print(f"  🔍 正在搜索第 {current_hop} 层邻居...")
                
                for current_node in current_layer:
                    # 获取当前节点的直接邻居
                    neighbors_info = self.get_neighbors(current_node, direction='both')
                    predecessors = neighbors_info.get('predecessors', [])
                    successors = neighbors_info.get('successors', [])
                    
                    # 处理前驱节点（只包含在top_k中的节点）
                    for pred_id in predecessors:
                        if pred_id not in visited and pred_id in top_k_node_ids:
                            visited.add(pred_id)
                            next_layer.add(pred_id)
                            
                            pred_details = self.get_node_details(pred_id)
                            if pred_details:
                                encoding = pred_details.get('encoding', {})
                                layer_neighbors.append({
                                    'id': pred_id,
                                    'name': pred_details.get('name', 'N/A'),
                                    'type': pred_details.get('type', 'N/A'),
                                    'file_path': pred_details.get('file_path', 'N/A'),
                                    'relation': 'predecessor',
                                    'hop_level': current_hop,
                                    'parent_node': current_node,
                                    'what': encoding.get('what', None),
                                    'how': encoding.get('how', None)
                                })
                    
                    # 处理后继节点（只包含在top_k中的节点）
                    for succ_id in successors:
                        if succ_id not in visited and succ_id in top_k_node_ids:
                            visited.add(succ_id)
                            next_layer.add(succ_id)
                            
                            succ_details = self.get_node_details(succ_id)
                            if succ_details:
                                encoding = succ_details.get('encoding', {})
                                layer_neighbors.append({
                                    'id': succ_id,
                                    'name': succ_details.get('name', 'N/A'),
                                    'type': succ_details.get('type', 'N/A'),
                                    'file_path': succ_details.get('file_path', 'N/A'),
                                    'relation': 'successor',
                                    'hop_level': current_hop,
                                    'parent_node': current_node,
                                    'what': encoding.get('what', None),
                                    'how': encoding.get('how', None)
                                })
                
                # 添加当前层的邻居到总结果中
                neighbor_details.extend(layer_neighbors)
                print(f"    ✅ 第 {current_hop} 层找到 {len(layer_neighbors)} 个邻居节点（限制在top_k范围内）")
                
                # 如果没有更多邻居，提前结束
                if not next_layer:
                    print(f"    ⚠️  第 {current_hop} 层后没有更多邻居节点，搜索结束")
                    break
                
                # 准备下一层搜索
                current_layer = next_layer
            
            # 按层级分组统计
            neighbors_by_hop = {}
            for neighbor in neighbor_details:
                hop_level = neighbor['hop_level']
                if hop_level not in neighbors_by_hop:
                    neighbors_by_hop[hop_level] = []
                neighbors_by_hop[hop_level].append(neighbor)
            
            print(f"👥 节点 {node_id} 总共找到 {len(neighbor_details)} 个邻居节点（{hop} 层内，限制在top_k范围内）:")
            for hop_level in sorted(neighbors_by_hop.keys()):
                level_neighbors = neighbors_by_hop[hop_level]
                print(f"  第 {hop_level} 层: {len(level_neighbors)} 个节点")
                
                for i, neighbor in enumerate(level_neighbors, 1):
                    print(f"    {i}. ID: {neighbor['id']} ({neighbor['relation']} -> {neighbor['parent_node']})")
                    print(f"       名称: {neighbor['name']}")
                    print(f"       类型: {neighbor['type']}")
                    if neighbor['what']:
                        what_preview = neighbor['what'][:50] + "..." if len(neighbor['what']) > 50 else neighbor['what']
                        print(f"       What: {what_preview}")
                    if neighbor['how']:
                        how_preview = neighbor['how'][:50] + "..." if len(neighbor['how']) > 50 else neighbor['how']
                        print(f"       How: {how_preview}")
                    print()
            
            # 构建当前节点的结果
            node_result = {
                "node_index": node_idx + 1,
                "similar_node": {
                    "id": similar_node['id'],
                    "name": similar_node.get('name'),
                    "type": similar_node.get('type'),
                    "file_path": similar_node.get('file_path'),
                    "similarity_score": similar_node['similarity_score'],
                    "what": similar_node.get('what'),
                    "how": similar_node.get('how')
                },
                "neighbors": neighbor_details,
                "neighbors_by_hop": neighbors_by_hop,
                "neighbors_count": {
                    "total": len(neighbor_details),
                    "by_hop": {str(hop_level): len(neighbors) for hop_level, neighbors in neighbors_by_hop.items()}
                }
            }
            
            all_similar_nodes_results.append(node_result)
            print(f"✅ 节点 {node_id} 处理完成\n")
        
        # 构建最终返回结果
        result = {
            "success": True,
            "query": query,
            "hop_level": hop,
            "top_k": top_k,
            "constraint": "neighbors_limited_to_top_k",
            "top_k_node_ids": list(top_k_node_ids),
            "graph_stats": {
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges()
            },
            "similar_nodes_count": len(most_similar_nodes),
            "all_similar_nodes_results": all_similar_nodes_results,
            "summary": {
                "total_neighbors_found": sum(len(node_result["neighbors"]) for node_result in all_similar_nodes_results),
                "nodes_with_neighbors": len([node_result for node_result in all_similar_nodes_results if node_result["neighbors_count"]["total"] > 0])
            }
        }
        
        return result

    def save_search_result_to_json(self, search_result: Dict[str, Any], output_file: str):
        """将搜索结果保存到JSON文件中，确保ID与原始图对齐
        
        Args:
            search_result: embedding_search_with_neighbors_inside函数的返回结果
            output_file: 输出JSON文件路径
        """
        if not search_result.get("success"):
            print(f"❌ 搜索结果失败，无法保存: {search_result.get('error', 'Unknown error')}")
            return False
        
        # 收集所有涉及的节点ID
        all_node_ids = set()
        
        # 添加所有相似节点的ID
        for node_result in search_result.get("all_similar_nodes_results", []):
            similar_node = node_result.get("similar_node", {})
            all_node_ids.add(similar_node.get("id"))
            
            # 添加所有邻居节点的ID
            for neighbor in node_result.get("neighbors", []):
                all_node_ids.add(neighbor.get("id"))
        
        # 从当前图中获取这些节点的完整信息
        nodes_data = []
        edges_data = []
        
        print(f"📊 正在保存 {len(all_node_ids)} 个节点到JSON文件...")
        
        # 获取节点信息
        for node_id in all_node_ids:
            if node_id in self.graph:
                node_data = self.graph.nodes[node_id]
                node_info = {
                    'id': node_id,
                    'type': node_data.get('node_type'),
                    'name': node_data.get('name'),
                    'file_path': node_data.get('file_path'),
                    'body': node_data.get('metadata', {}).get('body')
                }
                
                # 添加metadata信息（去除body避免重复）
                metadata = dict(node_data.get('metadata', {}))
                if 'body' in metadata:
                    del metadata['body']
                node_info['metadata'] = metadata
                
                # 添加encoding信息
                encoding = node_data.get('encoding', {
                    'what': None,
                    'how': None,
                    'embedding': None
                })
                node_info['encoding'] = encoding
                
                nodes_data.append(node_info)
        
        # 获取边信息（只包含涉及的节点之间的边）
        for source, target, edge_data in self.graph.edges(data=True):
            if source in all_node_ids and target in all_node_ids:
                edge_info = {
                    'source': source,
                    'target': target,
                    'type': edge_data.get('edge_type'),
                    'metadata': edge_data.get('metadata', {})
                }
                edges_data.append(edge_info)
        
        # 构建保存的数据结构
        save_data = {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'source_query': search_result.get('query'),
                'search_params': {
                    'top_k': search_result.get('top_k'),
                    'hop_level': search_result.get('hop_level'),
                    'constraint': search_result.get('constraint'),
                    'top_k_node_ids': search_result.get('top_k_node_ids', [])
                },
                'original_graph_stats': search_result.get('graph_stats', {}),
                'nodes_count': len(nodes_data),
                'edges_count': len(edges_data),
                'graph_type': 'directed'
            },
            'search_summary': search_result.get('summary', {}),
            'nodes': nodes_data,
            'edges': edges_data
        }
        
        # 保存到文件
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 搜索结果已保存到: {output_file}")
            print(f"📊 保存统计:")
            print(f"  - 节点数量: {len(nodes_data)}")
            print(f"  - 边数量: {len(edges_data)}")
            print(f"  - 查询内容: {search_result.get('query', 'N/A')}")
            print(f"  - Top-K: {search_result.get('top_k', 'N/A')}")
            print(f"  - 跳数: {search_result.get('hop_level', 'N/A')}")
            return True
            
        except Exception as e:
            print(f"❌ 保存文件时出错: {str(e)}")
            return False


def search_code_by_query(query: str, json_file_path: str, top_k: int = 10, 
                        min_similarity: float = 0.0) -> List[Dict[str, Any]]:
    """便利函数：基于查询文本搜索代码节点
    
    Args:
        query: 查询文本
        json_file_path: JSON文件路径
        top_k: 返回的最相似节点数量
        min_similarity: 最小相似度阈值
        
    Returns:
        List[Dict[str, Any]]: 匹配的节点列表
    """
    searcher = GraphSearcher()
    return searcher.search_by_embedding(query, json_file_path, top_k, min_similarity)


def test_embedding_search_with_neighbors(json_file_path: str, query: str, 
                                       top_k: int = 1, min_similarity: float = 0.0, hop: int = 1) -> Dict[str, Any]:
    """便利函数：测试embedding搜索和多层邻居节点获取
    
    Args:
        json_file_path: JSON文件路径
        query: 查询文本
        top_k: 返回的最相似节点数量
        min_similarity: 最小相似度阈值
        hop: 搜索邻居的层数，默认为1
        
    Returns:
        Dict[str, Any]: 测试结果
    """
    searcher = GraphSearcher()
    return searcher.embedding_search_with_neighbors(json_file_path, query, top_k, min_similarity, hop)


def test_embedding_search_with_neighbors_inside(json_file_path: str, query: str, 
                                               top_k: int = 1, min_similarity: float = 0.0, hop: int = 1) -> Dict[str, Any]:
    """便利函数：测试embedding搜索和多层邻居节点获取（邻居节点限制在top_k范围内）
    
    Args:
        json_file_path: JSON文件路径
        query: 查询文本
        top_k: 返回的最相似节点数量
        min_similarity: 最小相似度阈值
        hop: 搜索邻居的层数，默认为1
        
    Returns:
        Dict[str, Any]: 测试结果
    """
    searcher = GraphSearcher()
    return searcher.embedding_search_with_neighbors_inside(json_file_path, query, top_k, min_similarity, hop)


def test_embedding_search_with_neighbors_inside_and_save(json_file_path: str, query: str, 
                                                       output_file: str, top_k: int = 1, 
                                                       min_similarity: float = 0.0, hop: int = 1) -> Dict[str, Any]:
    """便利函数：测试embedding搜索和多层邻居节点获取（邻居节点限制在top_k范围内）并保存结果
    
    Args:
        json_file_path: JSON文件路径
        query: 查询文本
        output_file: 输出JSON文件路径
        top_k: 返回的最相似节点数量
        min_similarity: 最小相似度阈值
        hop: 搜索邻居的层数，默认为1
        
    Returns:
        Dict[str, Any]: 测试结果
    """
    searcher = GraphSearcher()
    
    # 执行搜索
    result = searcher.embedding_search_with_neighbors_inside(json_file_path, query, top_k, min_similarity, hop)
    
    # 保存搜索结果
    if result.get("success"):
        save_success = searcher.save_search_result_to_json(result, output_file)
        result["save_success"] = save_success
        result["output_file"] = output_file
    else:
        result["save_success"] = False
        result["output_file"] = None
    
    return result


def search_function_with_empty_what(json_path: str):
    print("=== 测试函数: search_function_with_empty_what() ===")
    graph_searcher = GraphSearcher()
    if graph_searcher.load_graph_from_json(json_path) == False:
        print("❌ 加载图结构失败")
        return False
    funcion_nodes = graph_searcher.find_nodes_by_type(NodeType.FUNCTION)
    function_nodes_details = [graph_searcher.get_node_details(node_id) for node_id in funcion_nodes]
    for node_details in function_nodes_details:
        if node_details.get("encoding").get("what") is None:
            print(f"⚠️  函数 {node_details['name']} 的 What 为空")
            print(f"   节点 ID: {node_details['id']}")
            print(f"   节点类型: {node_details['type']}")
            print(f"   节点文件路径: {node_details['file_path']}")
            

if __name__ == "__main__":
    print("=== 新增测试逻辑演示 ===")
    
    # 测试参数
    test_json_path = "D:/Download/github/evox-ai/evox-server/.rag/xiaozhi/wifi_connect/code_graph_recursive.json"
    test_query = "initialize and manage a WiFi station on an ESP32 device by starting the WiFi, scanning for available networks, connecting to the strongest recognized network, and handling connection lifecycle events to ensure continuous and reliable network connectivity"
    
    print("🚀 开始测试embedding搜索和邻居节点获取...")
    print("=" * 80)
    
    # 执行测试
    result = test_embedding_search_with_neighbors(
        json_file_path=test_json_path,
        query=test_query,
        top_k=20, 
        min_similarity=0.0,  # 不设置最小相似度限制
        hop=0  # 搜索1层邻居节点
    )
    
    print("=" * 80)
    print("📊 测试结果摘要:")
    
    if result.get("success"):
        print(f"✅ 测试成功完成")
        print(f"📈 图统计: {result['graph_stats']['nodes']} 个节点, {result['graph_stats']['edges']} 条边")
        print(f"🎯 最相似节点: {result['all_similar_nodes_results'][0]['similar_node']['name']} (相似度: {result['all_similar_nodes_results'][0]['similar_node']['similarity_score']:.4f})")
        
        # 安全地获取邻居节点数量信息
        neighbors_count = result.get('neighbors_count', {})
        total = neighbors_count.get('total', 0)
        predecessors = neighbors_count.get('predecessors', 0)
        successors = neighbors_count.get('successors', 0)
        print(f"👥 邻居节点数量: {total} 个 (前驱: {predecessors}, 后继: {successors})")
        
        # 显示邻居节点的encoding信息统计
        neighbors = result.get('neighbors', [])
        neighbors_with_what = sum(1 for n in neighbors if n.get('what'))
        neighbors_with_how = sum(1 for n in neighbors if n.get('how'))
        print(f"📝 邻居节点encoding信息: {neighbors_with_what} 个有'what', {neighbors_with_how} 个有'how'")
    else:
        print(f"❌ 测试失败: {result.get('error', 'Unknown error')}")
    
    # print("\n" + "=" * 80)
    # print("🔍 原有的搜索功能测试:")
    # search_function_with_empty_what("/Users/zxt/pro/xiaozhi-esp32/output/code_graph_recursive.json")
    
    print("\n" + "=" * 80)
    print("🚀 开始测试embedding搜索和邻居节点获取（限制在top_k范围内）...")
    print("=" * 80)
    
    # 设置输出文件路径
    output_file = "D:/Download/github/evox-ai/evox-server/.rag/xiaozhi/wifi_connect/search_result_neighbors_inside.json"
    
    # 执行测试新的函数（包含保存功能）
    result_inside = test_embedding_search_with_neighbors_inside_and_save(
        json_file_path=test_json_path,
        query=test_query,
        output_file=output_file,
        top_k=20, 
        min_similarity=0.0,  # 不设置最小相似度限制
        hop=1  # 搜索1层邻居节点
    )
    
    print("=" * 80)
    print("📊 测试结果摘要（限制在top_k范围内）:")
    
    if result_inside.get("success"):
        print(f"✅ 测试成功完成")
        print(f"📈 图统计: {result_inside['graph_stats']['nodes']} 个节点, {result_inside['graph_stats']['edges']} 条边")
        print(f"🎯 最相似节点: {result_inside['all_similar_nodes_results'][0]['similar_node']['name']} (相似度: {result_inside['all_similar_nodes_results'][0]['similar_node']['similarity_score']:.4f})")
        print(f"🔒 约束条件: {result_inside['constraint']}")
        print(f"🎯 top_k节点数量: {len(result_inside['top_k_node_ids'])}")
        
        # 显示邻居节点信息
        total_neighbors = result_inside.get('summary', {}).get('total_neighbors_found', 0)
        nodes_with_neighbors = result_inside.get('summary', {}).get('nodes_with_neighbors', 0)
        print(f"👥 邻居节点数量: {total_neighbors} 个（在top_k范围内）")
        print(f"🔗 有邻居的节点数量: {nodes_with_neighbors} 个")
        
        # 显示邻居节点的encoding信息统计
        all_neighbors = []
        for node_result in result_inside.get('all_similar_nodes_results', []):
            all_neighbors.extend(node_result.get('neighbors', []))
        neighbors_with_what = sum(1 for n in all_neighbors if n.get('what'))
        neighbors_with_how = sum(1 for n in all_neighbors if n.get('how'))
        print(f"📝 邻居节点encoding信息: {neighbors_with_what} 个有'what', {neighbors_with_how} 个有'how'")
        
        # 显示保存结果
        if result_inside.get("save_success"):
            print(f"💾 结果已保存到: {result_inside.get('output_file')}")
        else:
            print(f"❌ 结果保存失败")
    else:
        print(f"❌ 测试失败: {result_inside.get('error', 'Unknown error')}")
    
    # print("\n" + "=" * 80)
    # print("🔍 原有的搜索功能测试:")
    # search_function_with_empty_what("/Users/zxt/pro/xiaozhi-esp32/output/code_graph_recursive.json")