from queue import Queue
import os, sys
import json
import time
from datetime import datetime
from tqdm import tqdm
import concurrent
from typing import Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import threading
# Add parent directory to sys.path to import config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.rag.code.index.autoencoder.agent import AutoEncoderAgent
from src.utils.llm import get_llm, get_embedding
from src.utils import logger, Agent
from src.base import DefaultConfig
MAX_ITERATION = 20
# 导入GraphSearcher
from graph_searcher import GraphSearcher, NodeType, EdgeType

def clean_data_for_json(data):
    """递归清理数据中的控制字符"""
    if isinstance(data, str):
        # 移除 ASCII 控制字符，但保留换行符和制表符
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', data)
    elif isinstance(data, dict):
        return {key: clean_data_for_json(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    else:
        return data


class Encoder:
    """代码编码器类，负责管理代码的编码和图结构信息提取"""
    
    def __init__(self, graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json", num_agents=30):
        """初始化编码器，创建graph_searcher和autoencoder_agent实例
        
        Args:
            graph_json_path: 图数据JSON文件路径
            num_agents: 预先创建的 AutoEncoderAgent 实例数量
        """
        self.graph_json_path = graph_json_path
        self.graph_searcher = None
        self.autoencoder_agent = None
        self.llm_queue = Queue()
        self.agent_pool = []
        self.embedding_model = None
        self._file_lock = threading.RLock()
        
        # 初始化GraphSearcher
        self._init_graph_searcher()
        
        # 创建多个 AutoEncoderAgent 实例用于并发处理
        if num_agents <= 0:
            num_agents = 1
        
        for _ in range(num_agents):
            agent = Agent(get_llm())
            autoencoder_agent = AutoEncoderAgent(agent)
            self.agent_pool.append(autoencoder_agent)
        
        # 将 agent_pool 中的 autoencoder_agent 放入队列供线程获取
        for agent in self.agent_pool:
            self.llm_queue.put(agent)
        
        # 初始化主 AutoEncoderAgent（保持原有功能不变）
        self._init_autoencoder_agent()
        
        # 初始化Embedding模型
        self._init_embedding_model()
    
    def _init_graph_searcher(self):
        """初始化GraphSearcher实例"""
        try:
            self.graph_searcher = GraphSearcher()
            success = self.graph_searcher.load_graph_from_json(self.graph_json_path)
            if success:
                logger.info(f"Loaded graph data into GraphSearcher from {self.graph_json_path}")
            else:
                logger.error(f"Failed to load graph data from {self.graph_json_path}")
        except Exception as e:
            logger.error(f"Failed to initialize GraphSearcher from {self.graph_json_path}: {str(e)}")
            self.graph_searcher = None
    
    def _init_autoencoder_agent(self):
        """初始化AutoEncoderAgent实例"""
        try:
            self.autoencoder_agent = AutoEncoderAgent(Agent(get_llm()))
            logger.info("Created AutoEncoderAgent instance in Encoder")
        except Exception as e:
            logger.error(f"Failed to create AutoEncoderAgent: {str(e)}")
            self.autoencoder_agent = None
    
    def _init_embedding_model(self):
        """初始化Embedding模型"""
        try:
            self.embedding_model = get_embedding(
                openai_api_base=DefaultConfig.embedding_api_base,
                openai_api_key=DefaultConfig.embedding_api_key,
                model_name=DefaultConfig.embedding_model,
            )
            logger.info("Initialized embedding model in Encoder")
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {str(e)}")
            self.embedding_model = None
    
    def generate_embedding_for_text(self, text: str) -> List[float]:
        """为给定文本生成embedding向量
        
        Args:
            text: 要生成embedding的文本
            
        Returns:
            List[float]: embedding向量，如果失败返回空列表
        """
        if not self.embedding_model:
            logger.error("Embedding model not initialized")
            return []
        
        try:
            embedding = self.embedding_model.embed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {str(e)}")
            return []
    
    def generate_embeddings_for_nodes(self, max_workers: int = 4):
        """为所有节点生成embedding向量
        
        Args:
            max_workers: 并发处理的最大线程数
            
        Returns:
            bool: 是否成功完成所有embedding生成
        """
        if not self.embedding_model:
            logger.error("Embedding model not initialized")
            return False
        
        try:
            # 读取JSON文件
            with open(self.graph_json_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
            
            nodes = graph_data.get('nodes', [])
            nodes_to_process = []
            
            # 筛选需要处理的节点
            for node in nodes:
                encoding = node.get('encoding', {})
                what = encoding.get('what')
                how = encoding.get('how')
                embedding = encoding.get('embedding')
                
                # 只处理有what和how但没有embedding的节点
                if what and how and embedding is None:
                    nodes_to_process.append(node)
            
            if not nodes_to_process:
                logger.info("No nodes need embedding generation")
                return True
            
            logger.info(f"Found {len(nodes_to_process)} nodes to generate embeddings")
            
            def _process_node(node):
                """处理单个节点的embedding生成"""
                try:
                    encoding = node.get('encoding', {})
                    what = encoding.get('what', '')
                    how = encoding.get('how', '')
                    
                    # 组合what和how作为embedding文本
                    text = f"What: {what}\nHow: {how}"
                    
                    # 生成embedding
                    embedding = self.generate_embedding_for_text(text)
                    
                    if embedding:
                        # 更新节点的embedding
                        if 'encoding' not in node:
                            node['encoding'] = {}
                        node['encoding']['embedding'] = embedding
                        logger.debug(f"Generated embedding for node {node.get('id', 'unknown')}")
                        return True
                    else:
                        logger.error(f"Failed to generate embedding for node {node.get('id', 'unknown')}")
                        return False
                except Exception as e:
                    logger.error(f"Error processing node {node.get('id', 'unknown')}: {str(e)}")
                    return False
            
            # 使用线程池并发处理
            success_count = 0
            total_futures = len(nodes_to_process)
            completed_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_process_node, node) for node in nodes_to_process]
                
                for future in as_completed(futures):
                    try:
                        if future.result():
                            success_count += 1
                        completed_count += 1
                        if completed_count % 10 == 0 or completed_count == total_futures:
                            logger.info(f"Progress: {completed_count}/{total_futures} nodes processed")
                    except Exception as e:
                        completed_count += 1
                        logger.exception(f"Error in embedding generation: {e}")
            
            # 保存更新后的JSON文件
            with open(self.graph_json_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Successfully generated embeddings for {success_count}/{len(nodes_to_process)} nodes")
            return success_count == len(nodes_to_process)
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings for nodes: {str(e)}")
            return False
    
    def generate_embeddings_for_specific_path(self, max_workers: int = 4):
        """为指定JSON文件中的节点生成embedding向量
        
        Args:
            target_graph_json_path: 目标JSON文件路径
            max_workers: 并发处理的最大线程数
            
        Returns:
            bool: 是否成功完成所有embedding生成
        """
        if not self.embedding_model:
            logger.error("Embedding model not initialized")
            return False
        target_graph_json_path = self.graph_json_path
        # 检查文件是否存在
        if not os.path.exists(target_graph_json_path):
            logger.error(f"Target JSON file does not exist: {target_graph_json_path}")
            return False
        
        try:
            # 读取JSON文件
            with open(target_graph_json_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
            
            nodes = graph_data.get('nodes', [])
            nodes_to_process = []
            
            # 筛选需要处理的节点
            for node in nodes:
                encoding = node.get('encoding', {})
                what = encoding.get('what')
                how = encoding.get('how')
                embedding = encoding.get('embedding')
                
                # 只处理有what和how的节点
                if what and how:
                    nodes_to_process.append(node)
            
            if not nodes_to_process:
                logger.info(f"No nodes need embedding generation in {target_graph_json_path}")
                return True
            
            logger.info(f"Found {len(nodes_to_process)} nodes to generate embeddings in {target_graph_json_path}")
            
            def _process_node(node):
                """处理单个节点的embedding生成"""
                try:
                    encoding = node.get('encoding', {})
                    what = encoding.get('what', '')
                    how = encoding.get('how', '')
                    
                    # 组合what和how作为embedding文本
                    text = f"What: {what}\nHow: {how}"
                    
                    # 生成embedding
                    embedding = self.generate_embedding_for_text(text)
                    
                    if embedding:
                        # 更新节点的embedding
                        if 'encoding' not in node:
                            node['encoding'] = {}
                        node['encoding']['embedding'] = embedding
                        logger.debug(f"Generated embedding for node {node.get('id', 'unknown')}")
                        return True
                    else:
                        logger.error(f"Failed to generate embedding for node {node.get('id', 'unknown')}")
                        return False
                except Exception as e:
                    logger.error(f"Error processing node {node.get('id', 'unknown')}: {str(e)}")
                    return False
            
            # 使用线程池并发处理
            success_count = 0
            total_futures = len(nodes_to_process)
            completed_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_process_node, node) for node in nodes_to_process]
                
                for future in as_completed(futures):
                    try:
                        if future.result():
                            success_count += 1
                        completed_count += 1
                        if completed_count % 10 == 0 or completed_count == total_futures:
                            logger.info(f"Progress: {completed_count}/{total_futures} nodes processed")
                    except Exception as e:
                        completed_count += 1
                        logger.exception(f"Error in embedding generation: {e}")
            
            # 保存更新后的JSON文件
            with open(target_graph_json_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Successfully generated embeddings for {success_count}/{len(nodes_to_process)} nodes in {target_graph_json_path}")
            return success_count == len(nodes_to_process)
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings for nodes in {target_graph_json_path}: {str(e)}")
            return False


    def batch_update_node_encodings_in_json(self, encoding_updates) -> bool:
        """
        批量更新多个节点的encoding字段
        
        Args:
            encoding_updates: dict, {node_id: {'what': ..., 'how': ..., 'embedding': ...}}
        
        Returns:
            bool: 更新是否成功
        """
        with self._file_lock:
            try:
                # 1. 清理所有输入数据中的控制字符
                cleaned_updates = {}
                for node_id, encoding_data in encoding_updates.items():
                    cleaned_updates[node_id] = {}
                    for key, value in encoding_data.items():
                        if key in ['what', 'how'] and value is not None:
                            cleaned_updates[node_id][key] = clean_data_for_json(value)
                        else:
                            cleaned_updates[node_id][key] = value
                
                # 2. 读取并解析JSON文件
                try:
                    with open(self.graph_json_path, 'r', encoding='utf-8') as f:
                        graph_data = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.error(f"Failed to read JSON file {self.graph_json_path}: {e}")
                    return False
                
                # 3. 批量更新节点数据
                updated_nodes = []
                for node in graph_data.get('nodes', []):
                    node_id = node.get('id')
                    if node_id in cleaned_updates:
                        if 'encoding' not in node:
                            node['encoding'] = {}
                        
                        update_data = cleaned_updates[node_id]
                        for key, value in update_data.items():
                            if value is not None:
                                node['encoding'][key] = value
                        
                        updated_nodes.append(node_id)
                
                # 4. 验证JSON序列化（在内存中测试）
                try:
                    json.dumps(graph_data, ensure_ascii=False, indent=2)
                except (TypeError, ValueError) as e:
                    logger.error(f"JSON serialization validation failed: {e}")
                    return False
                
                # 5. 安全的原子写入
                temp_path = self.graph_json_path + '.tmp'
                try:
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        json.dump(graph_data, f, ensure_ascii=False, indent=2)
                        f.flush()
                        os.fsync(f.fileno())  # 强制写入磁盘
                    
                    # 原子替换
                    if os.name == 'nt':  # Windows
                        if os.path.exists(self.graph_json_path):
                            os.remove(self.graph_json_path)
                    os.rename(temp_path, self.graph_json_path)
                    
                except Exception as e:
                    # 清理临时文件
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    raise e
                
                # 6. 更新内存中的GraphSearcher（如果存在）
                try:
                    if hasattr(self, 'graph_searcher') and self.graph_searcher and \
                    hasattr(self.graph_searcher, 'graph'):
                        for node_id in updated_nodes:
                            if self.graph_searcher.graph.has_node(node_id):
                                if 'encoding' not in self.graph_searcher.graph.nodes[node_id]:
                                    self.graph_searcher.graph.nodes[node_id]['encoding'] = {}
                                
                                update_data = cleaned_updates[node_id]
                                for key, value in update_data.items():
                                    if value is not None:
                                        self.graph_searcher.graph.nodes[node_id]['encoding'][key] = value
                except Exception as e:
                    # 内存更新失败不影响文件更新的成功
                    logger.warning(f"Failed to update in-memory graph: {e}")
                
                logger.info(f"Successfully batch updated encoding for {len(updated_nodes)} nodes")
                return True
                
            except Exception as e:
                logger.error(f"Failed to batch update node encodings: {str(e)}")
                return False

    def update_node_encoding_in_json(self, node_id: str, what: Optional[str] = None, 
                                    how: Optional[str] = None, embedding: Optional[Any] = None) -> bool:
        """
        单个节点更新的便捷方法，内部调用批量更新
        
        Args:
            node_id: 节点ID
            what: what字段内容
            how: how字段内容  
            embedding: 可选的embedding数据
            
        Returns:
            bool: 更新是否成功
        """
        encoding_data = {}
        if what is not None:
            encoding_data['what'] = what
        if how is not None:
            encoding_data['how'] = how
        if embedding is not None:
            encoding_data['embedding'] = embedding
        
        if not encoding_data:
            logger.warning(f"No encoding data provided for node {node_id}")
            return False
        
        return self.batch_update_node_encodings_in_json({node_id: encoding_data})

    def set_node_generating_state(self, node_id, state="generating"):
        """设置节点的生成状态，防止环形依赖"""
        if state == "generating":
            return self.update_node_encoding_in_json(node_id, "generating", "generating", None, None)
        else:
            # 恢复状态时，设置为null
            return self.update_node_encoding_in_json(node_id, None, None, None, None)

    def extract_directory_tree_info(self, directory_path):
        """使用GraphSearcher从图中提取目录树信息，如果what为null则自动encode
        
        Args:
            directory_path: 目录路径
        
        Returns:
            str: 格式化的目录树分析信息
        """
        if not self.graph_searcher:
            logger.error("GraphSearcher not initialized")
            return f"DIRECTORY_TREE_ANALYSIS:\n- Directory: {directory_path}\n- Status: GraphSearcher not available"
        
        # 标准化目录路径
        normalized_dir_path = os.path.normpath(directory_path).replace('\\', '/')
        
        # 找到对应的目录节点
        folder_nodes = self.graph_searcher.find_nodes_by_type(NodeType.FOLDER)
        directory_node_id = None
        
        for node_id in folder_nodes:
            node_details = self.graph_searcher.get_node_details(node_id)
            if node_details and node_details.get("file_path"):
                node_path = os.path.normpath(node_details["file_path"]).replace('\\', '/')
                if normalized_dir_path.lower() in node_path.lower() or node_path.lower().endswith(normalized_dir_path.lower()):
                    directory_node_id = node_id
                    break
        
        if not directory_node_id:
            logger.warning(f"Directory node not found for path: {directory_path}")
            return f"DIRECTORY_TREE_ANALYSIS:\n- Directory: {directory_path}\n- Status: Not found in graph"
        
        # 检查目录节点的what是否为null或"generating"
        directory_details = self.graph_searcher.get_node_details(directory_node_id)
        directory_what = directory_details.get('encoding', {}).get('what')
        directory_how = directory_details.get('encoding', {}).get('how')
        
        if directory_what is None:
            # 设置生成状态
            self.set_node_generating_state(directory_node_id, "generating")
            try:
                # 调用encode_directory生成what和how
                logger.info(f"Encoding directory node {directory_node_id} as what is null")
                what, how, iteration = self.encode_directory(directory_path)
                
                # 写回JSON文件
                self.update_node_encoding_in_json(directory_node_id, what, how, None, iteration)
                directory_what = what
                directory_how = how
                
            except Exception as e:
                logger.error(f"Failed to encode directory {directory_node_id}: {str(e)}")
                # 恢复状态
                self.set_node_generating_state(directory_node_id, "restore")
                directory_what = ""
                directory_how = ""
            finally:
                # 确保状态被恢复
                if directory_what == "generating":
                    self.set_node_generating_state(directory_node_id, "restore")
        elif directory_what == "generating":
            # 正在生成中，避免环形依赖
            directory_what = "[Generating...]"
            directory_how = "[Generating...]"
        
        # 使用GraphSearcher查找包含关系的边
        folder_contains_edges = self.graph_searcher.search_by_edge_type(EdgeType.FOLDER_CONTAINS, source_node=directory_node_id)
        
        contained_files = []
        contained_folders = []
        
        for edge in folder_contains_edges:
            target_id = edge['target']
            target_details = self.graph_searcher.get_node_details(target_id)
            if target_details:
                if target_details['type'] == 'file':
                    # 检查文件的what是否需要生成
                    file_what = target_details.get('encoding', {}).get('what')
                    if file_what is None:
                        # 递归调用extract_structured_info_from_file
                        file_path = target_details.get('file_path', '')
                        if file_path:
                            self.extract_structured_info_from_file(file_path)
                            # 重新获取更新后的详情
                            target_details = self.graph_searcher.get_node_details(target_id)
                    contained_files.append(target_details)
                elif target_details['type'] == 'folder':
                    # 检查子文件夹的what是否需要生成
                    folder_what = target_details.get('encoding', {}).get('what')
                    if folder_what is None:
                        # 递归调用extract_directory_tree_info
                        subfolder_path = target_details.get('file_path', '')
                        if subfolder_path:
                            self.extract_directory_tree_info(subfolder_path)
                            # 重新获取更新后的详情
                            target_details = self.graph_searcher.get_node_details(target_id)
                    contained_folders.append(target_details)
        
        # 生成结构化目录树信息
        total_items = len(contained_files) + len(contained_folders)
        structured_tree_info = f"""
DIRECTORY_TREE_ANALYSIS:
- Directory: {directory_details.get('name', 'unknown')}
- Path: {directory_details.get('file_path', 'unknown')}
- Purpose: {directory_what if directory_what else 'Not specified'}
- Architecture: Hierarchical file organization with {len(contained_files)} files and {len(contained_folders)} subfolders
- Total Items: {total_items}

DIRECTORY_TREE_STRUCTURE:"""
        
        # 添加子文件夹
        for folder in contained_folders:
            folder_what = folder.get('encoding', {}).get('what', '')
            folder_desc = f" - {folder_what}" if folder_what else ""
            structured_tree_info += f"\n📁 {folder.get('name', 'unknown')} (folder){folder_desc}"
        
        # 添加文件
        for file in contained_files:
            file_what = file.get('encoding', {}).get('what', '')
            file_desc = f" - {file_what}" if file_what else ""
            structured_tree_info += f"\n📄 {file.get('name', 'unknown')} (file){file_desc}"
        
        logger.info(f"Extract directory tree info using GraphSearcher: Generated info for {total_items} items")
        return structured_tree_info.strip()

    def extract_structured_info_from_file(self, file_path):
        """使用GraphSearcher从图中提取文件的结构化信息，如果what为null则自动encode
        
        Args:
            file_path: 文件路径
        
        Returns:
            str: 格式化的结构化信息
        """
        if not self.graph_searcher:
            logger.error("GraphSearcher not initialized")
            return f"FILE_STRUCTURE_ANALYSIS:\n- File: {file_path}\n- Status: GraphSearcher not available"
        
        # 标准化文件路径
        normalized_file_path = os.path.normpath(file_path).replace('\\', '/')
        
        # 使用GraphSearcher查找对应的文件节点
        file_nodes = self.graph_searcher.find_nodes_by_type(NodeType.FILE)
        file_node_id = None
        
        for node_id in file_nodes:
            node_details = self.graph_searcher.get_node_details(node_id)
            if node_details and node_details.get("file_path"):
                node_path = os.path.normpath(node_details["file_path"]).replace('\\', '/')
                if normalized_file_path.lower() in node_path.lower() or node_path.lower().endswith(normalized_file_path.lower()):
                    file_node_id = node_id
                    break
        
        if not file_node_id:
            logger.warning(f"File node not found for path: {file_path}")
            return f"FILE_STRUCTURE_ANALYSIS:\n- File: {file_path}\n- Status: Not found in graph"
        
        # 检查文件节点的what是否为null或"generating"
        file_details = self.graph_searcher.get_node_details(file_node_id)
        file_what = file_details.get('encoding', {}).get('what')
        file_how = file_details.get('encoding', {}).get('how')
        
        if file_what is None:
            # 设置生成状态
            self.set_node_generating_state(file_node_id, "generating")
            try:
                # 调用encode_file生成what和how
                logger.info(f"Encoding file node {file_node_id} as what is null")
                what, how, iteration = self.encode_file(file_path)
                
                # 写回JSON文件
                self.update_node_encoding_in_json(file_node_id, what, how, None, iteration)
                file_what = what
                file_how = how
                
            except Exception as e:
                logger.error(f"Failed to encode file {file_node_id}: {str(e)}")
                # 恢复状态
                self.set_node_generating_state(file_node_id, "restore")
                file_what = ""
                file_how = ""
            finally:
                # 确保状态被恢复
                if file_what == "generating":
                    self.set_node_generating_state(file_node_id, "restore")
        elif file_what == "generating":
            # 正在生成中，避免环形依赖
            file_what = "[Generating...]"
            file_how = "[Generating...]"
        
        # 使用GraphSearcher查找文件包含的函数和变量
        functions_info = {}
        variables_info = {}
        
        # 查找包含函数的边
        contains_function_edges = self.graph_searcher.search_by_edge_type(EdgeType.CONTAINS_FUNCTION, source_node=file_node_id)
        for edge in contains_function_edges:
            target_id = edge['target']
            func_details = self.graph_searcher.get_node_details(target_id)
            if func_details:
                func_name = func_details.get('name', 'unknown_function')
                outgoing_calls_count = func_details.get('metadata', {}).get('outgoing_calls_count', 0)
                
                # 检查函数的what是否需要生成
                func_what = func_details.get('encoding', {}).get('what')
                func_how = func_details.get('encoding', {}).get('how')
                
                if func_what is None:
                    # 设置生成状态
                    self.set_node_generating_state(target_id, "generating")
                    try:
                        # 获取函数体进行编码
                        func_body = func_details.get('metadata', {}).get('body', '')
                        if func_body:
                            logger.info(f"Encoding function node {target_id} as what is null")
                            what, how, iteration = self.encode_code(func_body, target_id)
                            
                            # 写回JSON文件
                            self.update_node_encoding_in_json(target_id, what, how, None, iteration)
                            func_what = what
                            func_how = how
                        else:
                            func_what = f"Function {func_name} (no body available)"
                            func_how = "Function signature only"
                            self.update_node_encoding_in_json(target_id, func_what, func_how, None, 0)
                            
                    except Exception as e:
                        logger.error(f"Failed to encode function {target_id}: {str(e)}")
                        self.set_node_generating_state(target_id, "restore")
                        func_what = f"Function {func_name}"
                        func_how = "Encoding failed"
                    finally:
                        if func_what == "generating":
                            self.set_node_generating_state(target_id, "restore")
                elif func_what == "generating":
                    func_what = "[Generating...]"
                    func_how = "[Generating...]"
                
                functions_info[func_name] = {
                    'desc': f"Function {func_name} - {outgoing_calls_count} outgoing calls",
                    'what': func_what,
                    'how': func_how
                }
        
        # 查找包含变量的边
        contains_variable_edges = self.graph_searcher.search_by_edge_type(EdgeType.CONTAINS_VARIABLE, source_node=file_node_id)
        for edge in contains_variable_edges:
            target_id = edge['target']
            var_details = self.graph_searcher.get_node_details(target_id)
            if var_details:
                var_name = var_details.get('name', 'unknown_variable')
                
                # 检查变量的what是否需要生成
                var_what = var_details.get('encoding', {}).get('what')
                var_how = var_details.get('encoding', {}).get('how')
                
                if var_what is None:
                    # 为变量生成简单的描述
                    var_what = f"Global variable {var_name}"
                    var_how = "Variable declaration and usage"
                    self.update_node_encoding_in_json(target_id, var_what, var_how, None, 0)
                elif var_what == "generating":
                    var_what = "[Generating...]"
                    var_how = "[Generating...]"
                    
                variables_info[var_name] = {
                    'desc': f"Global variable {var_name}",
                    'what': var_what,
                    'how': var_how
                }
        
        # 生成结构化文件信息
        file_name = file_details.get('name', 'unknown')
        total_functions = len(functions_info)
        total_variables = len(variables_info)
        
        structured_info = f"""
FILE_STRUCTURE_ANALYSIS:
- File: {file_name}
- Path: {file_details.get('file_path', 'unknown')}
- Purpose: {file_what if file_what else 'Contains code functionality'}
- Architecture: Structured code file with {total_functions} function(s) and {total_variables} variable(s)"""
        
        # 添加函数签名检测部分
        if functions_info:
            structured_info += f"""

DETECTED_FUNCTION_SIGNATURES:
- Total functions detected: {total_functions}
- Function names: {', '.join(functions_info.keys())}"""
        
        structured_info += """

STRUCTURED_ELEMENTS:"""
        
        # 添加函数信息
        if functions_info:
            for func_name, func_info in functions_info.items():
                structured_info += f"""
- Function: {func_name}"""
                if func_info['what']:
                    structured_info += f""" - What: {func_info['what']}"""
                if func_info['how']:
                    structured_info += f""" - How: {func_info['how']}"""
        
        # 添加变量信息
        if variables_info:
            for var_name, var_info in variables_info.items():
                structured_info += f"""
- Variable: {var_name}"""
                if var_info['what']:
                    structured_info += f""" - What: {var_info['what']}"""
                if var_info['how']:
                    structured_info += f""" - How: {var_info['how']}"""
        
        if not functions_info and not variables_info:
            structured_info += """
- No functions or variables found in graph"""
        
        logger.info(f"Extract structured info using GraphSearcher: Generated info for {total_functions} functions and {total_variables} variables")
        return structured_info.strip()

    def extract_context_from_code(self, code_id):
        """从代码中提取上下文信息，包括调用的函数和使用的全局变量"""
        if not self.graph_searcher: 
            return ""
        
        context_parts = []
        
        try:
            # 1. 查找当前代码节点调用的其他函数
            function_call_edges = self.graph_searcher.search_by_edge_type(
                EdgeType.FUNCTION_CALLS, 
                source_node=code_id
            )
            
            # 获取被调用函数的信息
            called_functions = []
            for edge in function_call_edges:
                target_func_id = edge['target']
                func_details = self.graph_searcher.get_node_details(target_func_id)
                
                if func_details:
                    func_name = func_details.get('name', 'unknown')
                    func_body = func_details.get('metadata', {}).get('body', '')
                    
                    called_functions.append({
                        'name': func_name,
                        'body': func_body,
                        'type': 'function'
                    })
            
            # 2. 查找当前代码节点使用的全局变量
            function_uses_var_edges = self.graph_searcher.search_by_edge_type(
                EdgeType.FUNCTION_USES_VARIABLE, 
                source_node=code_id
            )
            
            # 获取使用的全局变量信息
            used_variables = []
            for edge in function_uses_var_edges:
                target_var_id = edge['target']
                var_details = self.graph_searcher.get_node_details(target_var_id)
                
                if var_details:
                    var_name = var_details.get('name', 'unknown')
                    var_definition = var_details.get('metadata', {}).get('definition', '')
                    
                    used_variables.append({
                        'name': var_name,
                        'definition': var_definition,
                        'type': 'variable'
                    })
            
            # 3. 构建上下文信息
            if called_functions or used_variables:
                context_parts.append("=== CONTEXT INFORMATION ===")
                context_parts.append("")
                
                # 添加被调用函数的上下文
                if called_functions:
                    context_parts.append("--- Called Functions ---")
                    for func_info in called_functions:
                        context_parts.append(f"Function: {func_info['name']}")
                        if func_info['body'] and func_info['body'].strip():
                            context_parts.append("Body:")
                            context_parts.append(func_info['body'])
                        else:
                            context_parts.append("Body: [No implementation available]")
                        context_parts.append("")  # 空行分隔
                
                # 添加使用的全局变量的上下文
                if used_variables:
                    context_parts.append("--- Used Global Variables ---")
                    for var_info in used_variables:
                        context_parts.append(f"Variable: {var_info['name']}")
                        if var_info['definition'] and var_info['definition'].strip():
                            context_parts.append("Definition:")
                            context_parts.append(var_info['definition'])
                        else:
                            context_parts.append("Definition: [No definition available]")
                        context_parts.append("")  # 空行分隔
                
                context_parts.append("=== END CONTEXT ===")
            
            return '\n'.join(context_parts).strip()
            
        except Exception as e:
            logger.error(f"Failed to extract context for {code_id}: {str(e)}")
            return ""

    def encode_code(self, code, code_id, max_iteration=MAX_ITERATION, encode_agent=None):
        '''Use the idea of autoencoder to convert code into document. First, extract the code into document, then determine whether it needs to be generated again. If necessary, generate it again. If not, get the result. Try up to 20 times.
        
        Returns:
            tuple: (what, how, iteration) where what is the purpose/meaning, how is the implementation details
        '''
        extract_context = self.extract_context_from_code(code_id)
        #print("code_id: , extract_context: ", code_id, extract_context)
        #return "encode code what test", "encode code how test", 0
        if encode_agent is None:
            encode_agent = self.autoencoder_agent
        
        if not encode_agent:
            logger.error("encode_agent not initialized")
            return "Code encoding not available", "encode_agent not available", 0
        document = encode_agent.generate_document_from_code(code, extract_context)
        regenerated_code = encode_agent.generate_code_from_document(document)
        regenerate = encode_agent.decide_regenerate_or_stop_from_code(code, document, regenerated_code)
        iteration = 0
        if regenerate:
            while iteration < max_iteration:
                document = encode_agent.regenerate_document_from_code(code, document, regenerated_code)
                regenerated_code = encode_agent.generate_code_from_document(document)
                regenerate = encode_agent.decide_regenerate_or_stop_from_code(code, document, regenerated_code)
                iteration += 1
                if not regenerate:
                    break
        
        # 解析document为what和how
        print("document: ", document, type(document))
        what, how = document.what, document.how
        return what, how, iteration

    def encode_code_with_full_context(self, code, code_id, max_iteration=MAX_ITERATION, encode_agent=None):
        """使用完整的上下文信息（包括调用的函数和全局变量的 what 描述）对代码进行编码
        
        Args:
            code: 要编码的代码内容
            code_id: 代码节点ID
            max_iteration: 最大迭代次数
            
        Returns:
            tuple: (what, how, iteration) where what是代码的目的/意义，how是实现细节
        """
        if encode_agent is None:
            encode_agent = self.autoencoder_agent

        if not encode_agent:
            logger.error("encode_agent not initialized")
            return "Code encoding not available", "encode_agent not available", 0

        # 提取上下文信息，包括调用的函数和使用的全局变量的 what 描述
        extract_context = self.extract_context_from_code_with_full_what(code_id)
        
        # 构建完整的代码描述
        if not extract_context:
            extract_context = "No additional context information available"
        
        # 使用autoencoder agent生成文档
        document = encode_agent.generate_document_from_code(code, extract_context)
        
        # 基于文档重新生成代码以验证质量
        regenerated_code = encode_agent.generate_code_from_document(document)
        regenerate = encode_agent.decide_regenerate_or_stop_from_code(
            code, 
            document, 
            regenerated_code
        )
        
        iteration = 0
        if regenerate:
            while iteration < max_iteration:
                document = encode_agent.regenerate_document_from_code(
                    code, 
                    document, 
                    regenerated_code
                )
                regenerated_code = encode_agent.generate_code_from_document(document)
                regenerate = encode_agent.decide_regenerate_or_stop_from_code(
                    code, 
                    document, 
                    regenerated_code
                )
                iteration += 1
                if not regenerate:
                    break
        
        # 解析document为what和how
        what, how = document.what, document.how
        return what, how, iteration

    def encode_file(self, file_path,  max_iteration=MAX_ITERATION):
        '''Use the idea of autoencoder to convert file into document. First, extract structured info from file and generate document, then determine whether it needs to be generated again. If necessary, generate it again. If not, get the result. Try up to 20 times.
        
        Returns:
            tuple: (what, how, iteration) where what is the purpose/meaning, how is the implementation details
        '''
        #return "encode file what test", "encode file how test", 0
        
        if not self.autoencoder_agent:
            logger.error("AutoEncoderAgent not initialized")
            return "File encoding not available", "AutoEncoderAgent not available", 0
        
        # 从graph中提取结构化信息并生成初始文档
        structured_info = self.extract_structured_info_from_file(file_path)
        document = self.autoencoder_agent.generate_document_from_file(structured_info)
        
        # 基于文档重新生成结构化信息
        regenerated_structured_info = self.autoencoder_agent.generate_file_from_document(document)
        
        # 判断是否需要重新生成
        regenerate, reason = self.autoencoder_agent.decide_regenerate_or_stop_from_file(structured_info, regenerated_structured_info)
        
        iteration = 0
        if regenerate:
            while iteration < max_iteration:
                document = self.autoencoder_agent.regenerate_document_from_file(structured_info, document, regenerated_structured_info)
                regenerated_structured_info = self.autoencoder_agent.generate_file_from_document(document)
                regenerate, reason = self.autoencoder_agent.decide_regenerate_or_stop_from_file(structured_info, regenerated_structured_info)
                iteration += 1
                if not regenerate:
                    break
        
        # 解析document为what和how
        what, how = document.what, document.how
        return what, how, iteration

    def encode_directory(self, directory_path,max_iteration=MAX_ITERATION):
        '''Use the idea of autoencoder to convert directory into document. First, extract directory tree info and generate document, then determine whether it needs to be generated again. If necessary, generate it again. If not, get the result. Try up to 20 times.
        
        This method will also encode individual files within the directory by calling encode_file for each file.
        
        Returns:
            tuple: (what, how, iteration) where what is the purpose/meaning, how is the implementation details
        '''
        # return "encode directory what test", "encode directory how test", 0
        
        if not self.autoencoder_agent:
            logger.error("AutoEncoderAgent not initialized")
            return "Directory encoding not available", "AutoEncoderAgent not available", 0
        
        # 从graph中提取目录树结构化信息并生成初始文档
        directory_tree_info = self.extract_directory_tree_info(directory_path)
        document = self.autoencoder_agent.generate_document_from_directory_tree(directory_tree_info)
        
        # 基于文档重新生成目录树结构
        regenerated_directory_tree_info = self.autoencoder_agent.generate_directory_tree_from_document(document)
        
        # 判断是否需要重新生成
        regenerate = self.autoencoder_agent.decide_regenerate_or_stop_from_directory_tree(directory_tree_info, regenerated_directory_tree_info)
        
        iteration = 0
        if regenerate:
            while iteration < max_iteration:
                document = self.autoencoder_agent.regenerate_document_from_directory_tree(directory_tree_info, document, regenerated_directory_tree_info)
                regenerated_directory_tree_info = self.autoencoder_agent.generate_directory_tree_from_document(document)
                regenerate = self.autoencoder_agent.decide_regenerate_or_stop_from_directory_tree(directory_tree_info, regenerated_directory_tree_info)
                iteration += 1
                if not regenerate:
                    break
        
        # 解析document为what和how
        what, how = document.what, document.how
        return what, how, iteration

    def extract_context_from_global_variable(self, node_id):
        """从全局变量中提取上下文信息，包括所有引用该变量的函数体"""
        if not self.graph_searcher:
            return ""
        
        context_parts = []
        
        try:
            # 查找使用该全局变量的函数
            uses_edges = self.graph_searcher.search_by_edge_type(EdgeType.FUNCTION_USES_VARIABLE, target_node=node_id)
            
            # 收集所有引用该变量的函数体
            for edge in uses_edges:
                func_id = edge['source']
                func_details = self.graph_searcher.get_node_details(func_id)
                
                if func_details and func_details.get('metadata', {}).get('body'):
                    # 获取函数详情
                    func_name = func_details.get('name', 'unknown')
                    file_path = func_details.get('file_path', '')
                    
                    # 添加函数体信息
                    context_parts.append(f"// 函数 {func_name} 使用了该变量")
                    context_parts.append(func_details['metadata']['body'])
                    context_parts.append("")  # 空行分隔
        
            if context_parts:
                header = "=== CONTEXT INFORMATION ==="
                footer = "=== END CONTEXT ==="
                return '\n'.join([header] + context_parts + [footer])
            else:
                return ""
            
        except Exception as e:
            logger.error(f"Failed to extract context for global variable {node_id}: {str(e)}")
            return ""

    def extract_context_from_code_with_full_what(self, code_id):
        """从代码中提取上下文信息，包括调用的函数和使用的全局变量的 what 描述
        
        Args:
            code_id: 代码节点ID
            
        Returns:
            str: 格式化的上下文信息，包含调用函数和全局变量的 what 描述
        """
        if not self.graph_searcher:
            return ""
        
        context_parts = []
        
        try:
            # 获取当前代码调用的函数
            function_call_edges = self.graph_searcher.search_by_edge_type(
                EdgeType.FUNCTION_CALLS, 
                source_node=code_id
            )
            
            # 收集被调用函数的 what 描述
            called_functions = []
            for edge in function_call_edges:
                target_func_id = edge['target']
                func_details = self.graph_searcher.get_node_details(target_func_id)
                
                if func_details:
                    encoding = func_details.get('encoding', {})
                    what = encoding.get('what', '')
                    how = encoding.get('how', '')
                    
                    called_functions.append({
                        'id': target_func_id,
                        'name': func_details.get('name', 'unknown'),
                        'what': what,
                        'how': how
                    })
            
            # 获取当前代码使用的全局变量
            function_uses_var_edges = self.graph_searcher.search_by_edge_type(
                EdgeType.FUNCTION_USES_VARIABLE, 
                source_node=code_id
            )
            
            # 收集全局变量的 what 描述
            used_variables = []
            for edge in function_uses_var_edges:
                target_var_id = edge['target']
                var_details = self.graph_searcher.get_node_details(target_var_id)
                
                if var_details:
                    encoding = var_details.get('encoding', {})
                    what = encoding.get('what', '')
                    how = encoding.get('how', '')
                    
                    used_variables.append({
                        'id': target_var_id,
                        'name': var_details.get('name', 'unknown_variable'),
                        'what': what,
                        'how': how
                    })
            
            # 构建上下文信息
            if called_functions or used_variables:
                context_parts.append("=== CONTEXT INFORMATION ===")
                context_parts.append("")
                
                # 添加被调用函数的上下文
                if called_functions:
                    context_parts.append("--- Called Functions ---")
                    for func_info in called_functions:
                        context_parts.append(f"Function: {func_info['name']}")
                        if func_info['what']:
                            context_parts.append(f"What: {func_info['what']}")
                        context_parts.append("")  # 空行分隔
                
                # 添加使用的全局变量的上下文
                if used_variables:
                    context_parts.append("--- Used Global Variables ---")
                    for var_info in used_variables:
                        context_parts.append(f"Variable: {var_info['name']}")
                        if var_info['what']:
                            context_parts.append(f"What: {var_info['what']}")
                        context_parts.append("")  # 空行分隔
                
                context_parts.append("=== END CONTEXT ===")
            
            return '\n'.join(context_parts).strip()
            
        except Exception as e:
            logger.error(f"Failed to extract context for {code_id}: {str(e)}")
            return ""

    def encode_global_variable(self, node_id, max_iteration=MAX_ITERATION, encode_agent = None):
        """
        将当前图中的全局变量进行编码
        参照现有的 encode_code, encode_file 和 encode_directory 方法实现

        Args:
            node_id: 全局变量节点ID
            max_iteration: 最大迭代次数

        Returns:
            tuple: (what, how, iteration) where what是变量的目的/意义，how是实现细节
        """
        if encode_agent is None:
            encode_agent = self.autoencoder_agent

        if not encode_agent:
            logger.error("encode_agent not initialized")
            return "Global variable encoding not available", "encode_agent not available", 0

        # 获取全局变量节点详细信息
        var_details = self.graph_searcher.get_node_details(node_id)
        if not var_details or var_details.get('type') != NodeType.GLOBAL_VARIABLE.value:
            logger.error(f"Node {node_id} is not a global variable")
            return "Invalid node type", "Not a global variable", 0

        # 获取变量定义
        var_definition = var_details.get('metadata', {}).get('definition', '')
        var_name = var_details.get('name', 'unknown_variable')

        # 提取上下文信息（所有使用该变量的函数体）
        extract_context = self.extract_context_from_global_variable(node_id)

        # 构建完整的变量描述
        if var_definition:
            variable_description = f"Global variable: {var_name}\nDefinition: {var_definition}"
        else:
            variable_description = f"Global variable: {var_name}"

        # 如果有上下文信息，将其添加到描述中
        if extract_context:
            variable_description += f"\n\n{extract_context}"

        # 使用autoencoder agent生成文档
        document = encode_agent.generate_document_from_global_variable({
            'variable_name': var_name,
            'file_path': var_details.get('file_path', ''),
            'definition': var_definition,
            'references_count': len(var_details.get('metadata', {}).get('references', [])),
            'referencing_files_count': len(var_details.get('metadata', {}).get('referencing_files', []))
        })
        
        # 生成代码以验证文档质量
        regenerated_variable_info = encode_agent.generate_global_variable_from_document(document)
        
        # 判断是否需要重新生成
        regenerate = encode_agent.decide_regenerate_or_stop_from_global_variable(
            {
                'name': var_name,
                'file_path': var_details.get('file_path', ''),
                'metadata': {
                    'definition': var_definition
                }
            },
            regenerated_variable_info
        )
        
        iteration = 0
        if regenerate:
            while iteration < max_iteration:
                document = encode_agent.regenerate_document_from_global_variable(
                    {
                        'name': var_name,
                        'file_path': var_details.get('file_path', ''),
                        'metadata': {
                            'definition': var_definition
                        }
                    },
                    document,
                    regenerated_variable_info
                )
                
                regenerated_variable_info = encode_agent.generate_global_variable_from_document(document)
                
                regenerate = encode_agent.decide_regenerate_or_stop_from_global_variable(
                    {
                        'name': var_name,
                        'file_path': var_details.get('file_path', ''),
                        'metadata': {
                            'definition': var_definition
                        }
                    },
                    regenerated_variable_info
                )
                iteration += 1
                if not regenerate:
                    break

        # 更新节点的encoding信息
        self.update_node_encoding_in_json(
            node_id, 
            document.what, 
            document.how, 
            None
        )
        
        # 解析document为what和how
        what, how = document.what, document.how
        return what, how, iteration

    def encode_all_global_variables_concurrently(self, max_workers=5):
        """并行编码所有全局变量，批量更新JSON文件"""
        
        variable_nodes = self.graph_searcher.find_nodes_by_type(NodeType.GLOBAL_VARIABLE)
        total_tasks = len(variable_nodes)
        if total_tasks == 0:
            logger.warning("No variables found for encoding")
            return True

        logger.info(f"Start concurrent encoding with {max_workers} workers")
        logger.info(f"Encoding {len(variable_nodes)} global variables")

        # 并行编码，收集结果
        encoding_results = {}
        completed_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures_to_node = {}
            
            for var_id in variable_nodes:
                future = executor.submit(self._encode_global_variable_task, var_id)
                futures_to_node[future] = ('variable', var_id)

            # 收集所有编码结果
            for future in tqdm(concurrent.futures.as_completed(futures_to_node), 
                            total=total_tasks, desc="Encoding Progress"):
                node_type, node_id = futures_to_node[future]
                try:
                    result = future.result()
                    node_id, what, how, iteration = result
                    if what is not None and how is not None:
                        encoding_results[node_id] = {
                            'what': what,
                            'how': how,
                            'embedding': None
                        }
                except Exception as exc:
                    logger.error(f"{node_type} {node_id} generated an exception: {exc}")
                finally:
                    completed_count += 1

        # 批量更新JSON文件（只锁一次）
        if encoding_results:
            success = self.batch_update_node_encodings_in_json(encoding_results)
            if not success:
                logger.error("Failed to update JSON file with encoding results")
                return False

        logger.info(f"Finished encoding {completed_count}/{total_tasks} nodes")
        return completed_count == total_tasks
    
    def encode_all_functions_concurrently(self, max_workers=30):
        """
        并行编码所有函数，不考虑函数调用的子函数的what，只考虑body
        
        Args:
            max_workers: 最大并发线程数
        """
        if not self.autoencoder_agent:
            logger.error("AutoEncoderAgent not initialized")
            return False

        # 获取所有函数节点
        function_nodes = self.graph_searcher.find_nodes_by_type(NodeType.FUNCTION)

        total_tasks = len(function_nodes)
        if total_tasks == 0:
            logger.warning("No functions found for encoding")
            return True

        logger.info(f"Start concurrent encoding with {max_workers} workers")
        logger.info(f"Encoding {len(function_nodes)} functions")

        # 并行编码，收集结果
        encoding_results = {}
        completed_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures_to_node = {}
            
            # 提交函数编码任务
            for func_id in function_nodes:
                future = executor.submit(self._encode_function_task, func_id)
                futures_to_node[future] = ('function', func_id)

            # 收集所有编码结果
            for future in tqdm(concurrent.futures.as_completed(futures_to_node), 
                            total=total_tasks, desc="Encoding Progress"):
                node_type, node_id = futures_to_node[future]
                try:
                    result = future.result()
                    node_id, what, how, iteration = result
                    if what is not None and how is not None:
                        encoding_results[node_id] = {
                            'what': what,
                            'how': how,
                            'embedding': None
                        }
                except Exception as exc:
                    logger.error(f"{node_type} {node_id} generated an exception: {exc}")
                finally:
                    completed_count += 1

        # 批量更新JSON文件（只写一次）
        if encoding_results:
            success = self.batch_update_node_encodings_in_json(encoding_results)
            if not success:
                logger.error("Failed to update JSON file with encoding results")
                return False

        logger.info(f"Finished encoding {completed_count}/{total_tasks} nodes")
        return completed_count == total_tasks


    def _encode_function_task(self, func_id):
        """用于并发编码函数的子任务"""
        try:
            # 从队列中获取一个可用的 encode_agent 实例
            encode_agent = self.llm_queue.get(timeout=10)  # 设置超时防止死锁
            
            # 使用当前 autoencoder_agent 实例进行编码
            code_node = self.graph_searcher.get_node_details(func_id)
            code = code_node.get("body")
            what, how, iteration = self.encode_code(code = code, code_id = func_id, encode_agent=encode_agent)
            return (func_id, what, how, iteration)
        except Exception as e:
            logger.error(f"Failed to encode function {func_id}: {str(e)}")
            return (func_id, None, None, 0)
        finally:
            # 将 encode_agent 放回队列供其他线程使用
            if 'encode_agent' in locals():
                self.llm_queue.put(encode_agent)

    def _encode_global_variable_task(self, var_id):
        """用于并发编码全局变量的子任务"""
        try:
            # 从队列中获取一个可用的 encode_agent 实例
            encode_agent = self.llm_queue.get(timeout=10)  # 设置超时防止死锁
            
            # 使用当前 autoencoder_agent 实例进行编码
            what, how, iteration = self.encode_global_variable(node_id = var_id, encode_agent=encode_agent)
            return (var_id, what, how, iteration)
        except Exception as e:
            logger.error(f"Failed to encode global variable {var_id}: {str(e)}")
            return (var_id, None, None, 0)
        finally:
            # 将 encode_agent 放回队列供其他线程使用
            if 'encode_agent' in locals():
                self.llm_queue.put(encode_agent)



    def encode_all_functions_with_dependency_order(self, max_workers=5):
        """
        按依赖顺序对所有函数进行编码：
        - 每轮迭代找出所有其依赖（调用的函数）已编码的函数
        - 如果没有这样的函数，则选择“调用子函数最少”的函数进行处理
        - 每轮迭代使用线程池并发执行，提升效率
        
        Args:
            max_workers: 最大并发线程数
            
        Returns:
            bool: 是否成功编码所有函数
        """
        if not self.autoencoder_agent:
            logger.error("AutoEncoderAgent not initialized")
            return False

        # 获取所有需要编码的函数节点
        all_function_nodes = self.graph_searcher.find_nodes_by_type(NodeType.FUNCTION)
        all_function_nodes = [node for node in all_function_nodes if self.graph_searcher.get_node_body(node)]
        total_functions = len(all_function_nodes)
        logger.info(f"Total functions to encode: {total_functions}")
        logger.info(all_function_nodes)
        if total_functions == 0:
            logger.warning("No functions found for encoding")
            return True

        # 记录已完成编码的节点
        completed_functions = set()
        failed_functions = set()
        
        # 主循环：直到所有函数完成或无法继续
        while len(completed_functions) < total_functions:
            # 找出当前可编码的函数（其依赖已全部完成）
            ready_to_encode = []
            
            for func_id in all_function_nodes:
                if func_id in completed_functions or func_id in failed_functions:
                    continue
                
                # 检查该函数调用的所有函数是否已完成编码
                edges = self.graph_searcher.search_by_edge_type(EdgeType.FUNCTION_CALLS, source_node=func_id)
                dependencies = [edge['target'] for edge in edges]
                
                # 判断所有函数依赖是否已完成，若函数调用的子函数没有body则视为外部函数，不进行等待
                external_deps = []
                local_deps = []
                for dep in dependencies:
                    if not self.graph_searcher.get_node_body(dep):
                        external_deps.append(dep)
                    else:
                        local_deps.append(dep)
                
                # 只需等待本地函数依赖完成，外部函数（如标准库）无需等待
                if all(dep in completed_functions for dep in local_deps):
                    ready_to_encode.append(func_id)
            
            # 如果没有可编码的函数，选择“调用子函数最少”的函数进行处理
            if not ready_to_encode:
                logger.info("No functions with all dependencies encoded. Selecting function with fewest calls.")
                # 统计每个函数的调用次数
                call_counts = {}
                for func_id in all_function_nodes:
                    if func_id in completed_functions or func_id in failed_functions:
                        continue
                    edges = self.graph_searcher.search_by_edge_type(EdgeType.FUNCTION_CALLS, source_node=func_id)
                    call_counts[func_id] = len(edges)
                
                # 按调用次数排序，选择最少调用的函数
                sorted_funcs = sorted(call_counts.items(), key=lambda x: x[1])
                if sorted_funcs:
                    ready_to_encode.append(sorted_funcs[0][0])
                else:
                    logger.warning("All functions already processed or failed.")
                    break
            
            # 并发执行本轮任务，收集编码结果
            logger.info(f"Encoding {len(ready_to_encode)} functions in this round")
            logger.info(ready_to_encode)
            
            encoding_results = {}
            round_completed = set()
            round_failed = set()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures_to_func = {
                    executor.submit(self.encode_code_with_full_context, self.graph_searcher.get_node_body(func_id), func_id): func_id 
                    for func_id in ready_to_encode
                }
                
                for future in tqdm(concurrent.futures.as_completed(futures_to_func), 
                                total=len(futures_to_func), 
                                desc="Encoding Round Progress"):
                    func_id = futures_to_func[future]
                    try:
                        result = future.result()
                        what, how, iteration = result
                        if what is not None and how is not None:
                            # 收集编码结果，稍后批量更新
                            encoding_results[func_id] = {
                                'what': what,
                                'how': how,
                                'embedding': None
                            }
                            round_completed.add(func_id)
                        else:
                            round_failed.add(func_id)
                    except Exception as exc:
                        logger.error(f"Function {func_id} generated an exception: {exc}")
                        round_failed.add(func_id)
            
            # 批量更新JSON文件（每轮只写一次）
            if encoding_results:
                success = self.batch_update_node_encodings_in_json(encoding_results)
                if not success:
                    logger.error("Failed to update JSON file with encoding results")
                    # 即使文件更新失败，也要更新内存状态，避免死循环
                    round_failed.update(round_completed)
                    round_completed.clear()
            
            # 更新全局状态
            completed_functions.update(round_completed)
            failed_functions.update(round_failed)
            
            logger.info(f"Round completed: {len(round_completed)} success, {len(round_failed)} failed")

        # 总体结果统计
        success_rate = len(completed_functions) / total_functions
        logger.info(f"Finished encoding. Success rate: {success_rate:.2%} ({len(completed_functions)}/{total_functions})")
        return len(completed_functions) == total_functions


    def scan_directory_for_code_files(self, directory_path):
        """使用GraphSearcher从图中扫描目录，获取所有代码文件"""
        if not self.graph_searcher:
            logger.error("GraphSearcher not initialized")
            return []
        
        # 标准化目录路径
        normalized_dir_path = os.path.normpath(directory_path).replace('\\', '/')
        
        # 使用GraphSearcher查找对应的目录节点
        folder_nodes = self.graph_searcher.find_nodes_by_type(NodeType.FOLDER)
        directory_node_id = None
        
        for node_id in folder_nodes:
            node_details = self.graph_searcher.get_node_details(node_id)
            if node_details and node_details.get("file_path"):
                node_path = os.path.normpath(node_details["file_path"]).replace('\\', '/')
                if normalized_dir_path.lower() in node_path.lower() or node_path.lower().endswith(normalized_dir_path.lower()):
                    directory_node_id = node_id
                    break
        
        if not directory_node_id:
            logger.warning(f"Directory node not found for path: {directory_path}")
            return []
        
        # 递归查找所有子文件
        def find_files_recursive(folder_id, current_path=""):
            files = []
            folder_contains_edges = self.graph_searcher.search_by_edge_type(EdgeType.FOLDER_CONTAINS, source_node=folder_id)
            
            for edge in folder_contains_edges:
                target_id = edge['target']
                target_details = self.graph_searcher.get_node_details(target_id)
                
                if target_details:
                    if target_details.get('type') == 'file':
                        file_name = target_details.get('name', 'unknown')
                        file_path = target_details.get('file_path', '')
                        relative_path = os.path.relpath(file_path, directory_path) if file_path else file_name
                        
                        # 判断文件类型
                        file_ext = os.path.splitext(file_name)[1].lower()
                        code_extensions = {
                            '.py': 'python',
                            '.cpp': 'cpp',
                            '.cc': 'cpp',
                            '.cxx': 'cpp',
                            '.c++': 'cpp',
                            '.h': 'cpp_header',
                            '.hpp': 'cpp_header',
                            '.hxx': 'cpp_header',
                            '.h++': 'cpp_header'
                        }
                        
                        if file_ext in code_extensions:
                            files.append({
                                'filename': file_name,
                                'relative_path': relative_path,
                                'full_path': file_path,
                                'file_type': code_extensions[file_ext],
                                'extension': file_ext
                            })
                    elif target_details.get('type') == 'folder':
                        # 递归处理子文件夹
                        files.extend(find_files_recursive(target_id, current_path))
            return files
        
        code_files = find_files_recursive(directory_node_id)
        logger.info(f"Found {len(code_files)} code files using GraphSearcher for directory: {directory_path}")
        return code_files


# 为了保持向后兼容性，创建全局实例和函数
_default_encoder = None

def get_default_encoder(graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json"):
    """获取默认的编码器实例"""
    global _default_encoder
    if _default_encoder is None:
        _default_encoder = Encoder(graph_json_path)
    return _default_encoder

# 兼容性函数，保持原有API不变
def extract_directory_tree_info(directory_path, graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json"):
    encoder = get_default_encoder(graph_json_path)
    return encoder.extract_directory_tree_info(directory_path)

def extract_structured_info_from_file(file_path, graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json"):
    encoder = get_default_encoder(graph_json_path)
    return encoder.extract_structured_info_from_file(file_path)

def encode_code(code, code_id, max_iteration=MAX_ITERATION):
    encoder = get_default_encoder()
    return encoder.encode_code(code, code_id, max_iteration)

def encode_file(file_path, max_iteration=MAX_ITERATION, graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json"):
    encoder = get_default_encoder(graph_json_path)
    return encoder.encode_file(file_path, max_iteration)

def encode_directory(directory_path, max_iteration=MAX_ITERATION, graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json"):
    encoder = get_default_encoder(graph_json_path)
    return encoder.encode_directory(directory_path, max_iteration)

def scan_directory_for_code_files(directory_path, graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json"):
    encoder = get_default_encoder(graph_json_path)
    return encoder.scan_directory_for_code_files(directory_path)

# Embedding生成相关的便利函数
def generate_embeddings_for_nodes(graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json", max_workers=4):
    """为指定JSON文件中的所有节点生成embedding向量"""
    encoder = get_default_encoder(graph_json_path)
    return encoder.generate_embeddings_for_nodes(max_workers)

def generate_embeddings_for_specific_path(target_graph_json_path, max_workers=4):
    """为指定路径的JSON文件中的节点生成embedding向量"""
    encoder = Encoder()  # 创建新实例，因为需要处理不同的文件
    return encoder.generate_embeddings_for_specific_path(target_graph_json_path, max_workers)

def generate_embedding_for_text(text, graph_json_path="evox-server/.rag/graph_test/output/code_graph_recursive.json"):
    """为给定文本生成embedding向量"""
    encoder = get_default_encoder(graph_json_path)
    return encoder.generate_embedding_for_text(text)


if __name__ == "__main__":
    # 使用新的Encoder类
    encoder = Encoder("D:/Download/github/evox-ai/evox-server/.rag/xiaozhi/wifi_connect_bp/code_graph_recursive.json")
    encoder.encode_directory("D:/Download/github/xiaozhi-esp32s3_box/xiaozhi-esp32s3_box/managed_components/78__esp-wifi-connect")
    success = encoder.generate_embeddings_for_specific_path(max_workers=4)
    print(f"Embedding generation success: {success}")
    
    # 也可以使用便利函数
    # success = generate_embeddings_for_specific_path(target_path, max_workers=2)
    # print(f"Embedding generation using convenience function: {success}")

    # directory_path = "D:/Download/github/evox-ai/evox-server/src/core/rag/code/index/autoencoder/test_graph_constructor"
    
    # print(encoder.encode_directory(directory_path))
    #print(encoder.extract_directory_tree_info(directory_path))
    #print(encoder.encode_code("const char* getModuleName() {\r\n    return MODULE_NAME;\r\n}", "func:src/core/rag/code/index/autoencoder/test_graph_constructor/folder2/file3.cpp:getModuleName()"))
    #print(encoder.encode_file("D:/Download/github/evox-ai/evox-server/src/core/rag/code/index/autoencoder/test_graph_constructor/folder2/file3.cpp"))
    # print(encoder.encode_directory(directory_path))
    encoder = Encoder("/Users/zxt/pro/xiaozhi-esp32/output_init/code_graph_recursive.json")
    # nodes = encoder.graph_searcher.find_nodes_by_type(NodeType.GLOBAL_VARIABLE)
    # encoder.encode_global_variable(node_id=nodes[0])
    encoder.encode_all_global_variables_concurrently(max_workers=30)
    # encoder.encode_all_functions_with_dependency_order(max_workers=30)