#!/usr/bin/env python3
"""
Concurrent Extractor for Function Call Analysis
Extracts function call relationships and generates what-level descriptions using concurrent processing
"""

import json
import os
from typing import Dict, List, Set, Tuple, Any
import openai
from pathlib import Path
import concurrent.futures
import threading
import time

from src.utils import get_llm, get_embedding, Agent, get_dashscope_embedding
from src.base import DefaultConfig

class EmbeddingGenerator:
    """Embedding生成器，负责为JSON文件中的节点生成embedding表征"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        # 初始化embedding模型
        self.embedding_model = get_dashscope_embedding(
            model=DefaultConfig.embedding_model,
        )
        self.lock = threading.Lock()  # 线程安全
    
    def generate_embeddings_from_json(self, json_file_path: str, max_workers: int = 5) -> Dict[str, List[float]]:
        """从JSON文件生成embeddings"""
        print(f"Loading JSON file: {json_file_path}")
        
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        nodes = data.get('nodes', [])
        if not nodes:
            print("No nodes found in JSON file")
            return {}
        
        print(f"Found {len(nodes)} nodes to process")
        
        # 并发生成embeddings
        embeddings = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_node = {
                executor.submit(self._generate_single_embedding, node): node 
                for node in nodes
            }
            
            for future in concurrent.futures.as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    node_id, embedding = future.result()
                    if embedding:  # 只保存非空的embedding
                        embeddings[node_id] = embedding
                        print(f"Generated embedding for: {node_id}")
                except Exception as e:
                    print(f"Error generating embedding for {node.get('id', 'unknown')}: {e}")
        
        print(f"Successfully generated {len(embeddings)} embeddings")
        return embeddings
    
    def _generate_single_embedding(self, node: Dict) -> Tuple[str, List[float]]:
        """生成单个节点的embedding（线程安全）"""
        node_id = node.get('id', '')
        description = node.get('description', '')
        
        if not description.strip():
            print(f"Warning: No description found for node {node_id}")
            return node_id, []
        
        try:
            with self.lock:  # 确保embedding调用的线程安全
                embedding = self.embedding_model.embed_query(description)
                return node_id, embedding
        except Exception as e:
            print(f"Error generating embedding for {node_id}: {e}")
            return node_id, []
    
    def save_embeddings(self, embeddings: Dict[str, List[float]], output_path: str):
        """保存embeddings到JSON文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(embeddings, f, ensure_ascii=False, indent=2)
        print(f"Embeddings saved to: {output_path}")

class ConcurrentExtractor:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.function_calls = []  # 过滤后的函数调用关系
        self.function_bodies = {}  # graph_node_id -> function_body
        self.results = []  # 最终结果
        
        # 文件路径
        self.graph_file = self.base_dir / "code_graph_recursive.json"
        self.functions_file = self.base_dir / "functions_bodys.jsonl"
        self.output_file = self.base_dir / "functions_what_graph_concurrent.json"
        
        # 添加LLM agent
        self.agent = Agent(get_llm(model_name=DefaultConfig.agent_model))
        self.lock = threading.Lock()  # 用于线程安全的agent调用
        
        # 添加embedding生成器
        self.embedding_generator = EmbeddingGenerator(base_dir)
    
    def load_and_filter(self):
        """加载数据并过滤函数调用关系"""
        print("Loading and filtering data...")
        
        # 1. 读取code_graph_recursive.json
        with open(self.graph_file, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        
        # 2. 过滤函数调用关系: type="function_calls" AND source包含.cc AND target包含.cc
        self.function_calls = []
        for edge in graph_data.get('edges', []):
            if (edge.get('type') == 'function_calls' and 
                '.cc' in edge.get('source', '') and 
                '.cc' in edge.get('target', '')):
                self.function_calls.append(edge)
        
        print(f"Found {len(self.function_calls)} function call relationships")
        
        # 3. 读取functions_bodys.jsonl构建function_bodies字典
        self.function_bodies = {}
        with open(self.functions_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    func_data = json.loads(line)
                    graph_node_id = func_data.get('graph_node_id')
                    if graph_node_id:
                        self.function_bodies[graph_node_id] = func_data
        
        print(f"Loaded {len(self.function_bodies)} function bodies")
    
    def build_direct_calls(self) -> Dict[str, List[str]]:
        """为每个函数构建直接调用关系"""
        print("Building direct call relationships...")
        
        direct_calls = {}  # function_id -> [called_function_ids]
        
        # 初始化所有函数
        for func_id in self.function_bodies.keys():
            direct_calls[func_id] = []
        
        # 构建调用关系
        for call in self.function_calls:
            source = call.get('source')
            target = call.get('target')
            
            if source in direct_calls and target in direct_calls:
                direct_calls[source].append(target)
        
        return direct_calls
    
    def generate_what_description_with_llm(self, function_id: str, function_body: str, direct_calls: List[str]) -> str:
        """使用LLM生成what描述（线程安全版本）"""
        
        # 获取调用函数的代码
        called_functions_code = []
        for called_id in direct_calls:
            if called_id in self.function_bodies:
                called_code = self.function_bodies[called_id].get('functionBody', '')
                called_functions_code.append(f"// Called function: {called_id}\n{called_code}")
        
        # 构建提示词
        prompt = f"""
Please analyze the following C++ function and generate a concise WHAT-level description.

Main function: {function_id}
Function code:
{function_body}

Directly called function code:
{chr(10).join(called_functions_code) if called_functions_code else "No directly called functions"}

Describe WHAT the code does - the functional purpose, responsibilities, and behavior, considering the context. The description should be concise and clear.

Description:
"""
        
        try:
            with self.lock:  # 确保agent调用的线程安全
                result = self.agent.invoke(prompt)
                return result
        except Exception as e:
            print(f"LLM生成描述失败 {function_id}: {e}")
            return f"该函数{function_id.split(':')[-1]}的功能描述生成失败"
    
    def process_function_single(self, function_id: str, direct_calls: List[str]) -> Dict:
        """处理单个函数"""
        #start_time = time.time()
        # print(f"Processing function: {function_id}")
        
        # 获取函数体
        function_body = ""
        if function_id in self.function_bodies:
            function_body = self.function_bodies[function_id].get('functionBody', '')
        
        # 使用LLM生成描述
        #what_description = ""
        what_description = self.generate_what_description_with_llm(
            function_id, function_body, direct_calls
        )
        
        result = {
            "id": function_id,
            "code": function_body,
            "direct_calls": direct_calls,
            "description": what_description
        }
        
        # end_time = time.time()
        # print(f"Completed processing: {function_id} (耗时: {end_time - start_time:.2f}秒)")
        return result
    
    def process_each_function(self, max_workers: int = 5):
        """并发处理每个函数，生成结果"""
        print(f"Processing functions with {max_workers} workers...")
        start_time = time.time()
        
        direct_calls = self.build_direct_calls()
        
        # 准备任务列表
        tasks = []
        for function_id in self.function_bodies.keys():
            called_functions = direct_calls.get(function_id, [])
            tasks.append((function_id, called_functions))
        
        # 使用ThreadPoolExecutor并发处理
        self.results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_function = {
                executor.submit(self.process_function_single, func_id, calls): func_id 
                for func_id, calls in tasks
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_function):
                function_id = future_to_function[future]
                try:
                    result = future.result()
                    self.results.append(result)
                    #print(f"Successfully processed: {function_id}")
                except Exception as e:
                    print(f"Error processing {function_id}: {e}")
                    # 添加错误结果
                    self.results.append({
                        "id": function_id,
                        "code": "",
                        "direct_calls": direct_calls.get(function_id, []),
                        "description": f"处理失败: {str(e)}"
                    })
        
        end_time = time.time()
        print(f"Processed {len(self.results)} functions in {end_time - start_time:.2f} seconds")
    
    def test_concurrent_requests(self):
        """测试函数：同时发起两个LLM请求来验证并发功能"""
        print("Testing concurrent LLM requests...")
        start_time = time.time()
        
        # 选择两个函数进行测试
        function_ids = list(self.function_bodies.keys())[:2]
        if len(function_ids) < 2:
            print("Not enough functions to test concurrent requests")
            return
        
        test_functions = []
        for func_id in function_ids:
            function_body = self.function_bodies[func_id].get('functionBody', '')
            test_functions.append((func_id, function_body, []))
        
        print(f"Testing concurrent processing of: {function_ids}")
        
        # 使用ThreadPoolExecutor并发处理两个请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 提交两个并发任务
            futures = []
            for func_id, function_body, direct_calls in test_functions:
                future = executor.submit(
                    self.generate_what_description_with_llm, 
                    func_id, 
                    function_body, 
                    direct_calls
                )
                futures.append((future, func_id))
            
            # 收集结果
            results = []
            for future, func_id in futures:
                try:
                    result = future.result()
                    results.append((func_id, result))
                    print(f"Concurrent test completed for: {func_id}")
                except Exception as e:
                    print(f"Concurrent test failed for {func_id}: {e}")
                    results.append((func_id, f"Error: {str(e)}"))
        
        end_time = time.time()
        
        # 输出测试结果
        print(f"\n=== Concurrent Test Results (耗时: {end_time - start_time:.2f}秒) ===")
        for func_id, description in results:
            print(f"Function: {func_id}")
            print(f"Description: {description}")
            print("-" * 50)
        
        return results
    
    def save_results(self):
        """保存结果到JSON文件"""
        print(f"Saving results to {self.output_file}")
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump({"nodes": self.results}, f, ensure_ascii=False, indent=2)
        
        print(f"Results saved successfully!")
    
    def generate_embeddings_for_json(self, json_file_path: str, max_workers: int = 5) -> str:
        """为指定JSON文件生成embeddings"""
        print(f"Generating embeddings for: {json_file_path}")
        
        # 检查文件是否存在
        json_path = Path(json_file_path)
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_file_path}")
        
        # 生成embeddings
        embeddings = self.embedding_generator.generate_embeddings_from_json(
            json_file_path, max_workers
        )
        
        # 生成输出文件路径
        emb_path = json_path.parent / f"{json_path.stem}_emb{json_path.suffix}"
        
        # 保存embeddings
        self.embedding_generator.save_embeddings(embeddings, str(emb_path))
        
        return str(emb_path)
    
    def run(self, max_workers: int = 5):
        """运行完整的提取流程"""
        print("Starting Concurrent Extractor...")
        
        # 检查文件是否存在
        if not self.graph_file.exists():
            raise FileNotFoundError(f"Graph file not found: {self.graph_file}")
        if not self.functions_file.exists():
            raise FileNotFoundError(f"Functions file not found: {self.functions_file}")
        
        # 执行流程
        self.load_and_filter()
        self.process_each_function(max_workers)
        self.save_results()
        
        print("Extraction completed successfully!")

def generate_embeddings_for_file(input_json_path: str, max_workers: int = 5) -> str:
    """为指定JSON文件生成embeddings的独立方法"""
    json_path = Path(input_json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {input_json_path}")
    
    # 创建embedding生成器
    generator = EmbeddingGenerator(json_path.parent)
    
    # 生成embeddings
    embeddings = generator.generate_embeddings_from_json(input_json_path, max_workers)
    
    # 生成输出文件路径
    emb_path = json_path.parent / f"{json_path.stem}_emb{json_path.suffix}"
    
    # 保存embeddings
    generator.save_embeddings(embeddings, str(emb_path))
    
    print(f"Embeddings generated successfully: {emb_path}")
    return str(emb_path)

def main():
    """主函数"""
    # 设置工作目录
    base_dir = r"D:\Download\github\evox-ai\evox-server\.rag\xiaozhi\full_code"
    
    # 创建提取器
    extractor = ConcurrentExtractor(base_dir)
    
    # 选择运行模式
    print("=== Concurrent Extractor with Embedding Support ===")
    print("1. 完整提取流程")
    print("2. 生成embeddings")
    print("3. 测试并发功能")
    print("4. 为指定JSON文件生成embeddings")
    
    try:
        mode = input("请选择运行模式 (1-4): ").strip()
        
        if mode == "1":
            print("\n=== Running Full Extraction ===")
            extractor.run(max_workers=5)
        elif mode == "2":
            json_file = input("请输入JSON文件路径: ").strip()
            if json_file:
                result_path = extractor.generate_embeddings_for_json(json_file, max_workers=5)
                print(f"Embeddings生成完成: {result_path}")
            else:
                print("未提供JSON文件路径")
        elif mode == "3":
            print("\n=== Testing Concurrent Requests ===")
            extractor.load_and_filter()
            extractor.test_concurrent_requests()
        elif mode == "4":
            json_file = input("请输入JSON文件路径: ").strip()
            if json_file:
                result_path = generate_embeddings_for_file(json_file, max_workers=5)
                print(f"Embeddings生成完成: {result_path}")
            else:
                print("未提供JSON文件路径")
        else:
            print("无效的选择，运行默认的完整提取流程")
            print("\n=== Running Full Extraction ===")
            extractor.run(max_workers=5)
            
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()