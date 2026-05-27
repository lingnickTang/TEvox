#!/usr/bin/env python3
"""
Simple Extractor for Function Call Analysis
Extracts function call relationships and generates what-level descriptions
"""

import json
import os
from typing import Dict, List, Set
import openai
from pathlib import Path

from src.utils import get_llm, Agent
from src.base import DefaultConfig

class SimpleExtractor:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.function_calls = []  # 过滤后的函数调用关系
        self.function_bodies = {}  # graph_node_id -> function_body
        self.results = []  # 最终结果
        
        # 文件路径
        self.graph_file = self.base_dir / "code_graph_recursive.json"
        self.functions_file = self.base_dir / "functions_bodys.jsonl"
        self.output_file = self.base_dir / "functions_what_graph.json"
        
        # 添加LLM agent
        self.agent = Agent(get_llm(model_name=DefaultConfig.agent_model))
    
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
        """使用LLM生成what描述"""
        
        # 获取调用函数的代码
        called_functions_code = []
        for called_id in direct_calls:
            if called_id in self.function_bodies:
                called_code = self.function_bodies[called_id].get('functionBody', '')
                called_functions_code.append(f"// Called function: {called_id}\n{called_code}")
        
        # 构建提示词
        prompt = f"""
请分析以下C++函数的功能，生成简洁的what层面描述。

主函数: {function_id}
函数代码:
{function_body}

调用的函数代码:
{chr(10).join(called_functions_code) if called_functions_code else "无直接调用的函数"}

请生成一个简洁的what层面描述，说明这个函数的主要功能和目的。描述应该：
1. 简洁明了，一句话概括主要功能
2. 使用自然语言
3. 避免技术细节，重点关注功能目的

描述：
"""
        
        try:
            result = self.agent.invoke(prompt)
            return result
        except Exception as e:
            print(f"LLM生成描述失败 {function_id}: {e}")
            return f"该函数{function_id.split(':')[-1]}的功能描述生成失败"
    
    def process_each_function(self):
        """处理每个函数，生成结果"""
        print("Processing functions...")
        
        direct_calls = self.build_direct_calls()
        
        self.results = []
        for function_id in self.function_bodies.keys():
            called_functions = direct_calls.get(function_id, [])
            
            # 获取函数体
            function_body = ""
            if function_id in self.function_bodies:
                function_body = self.function_bodies[function_id].get('functionBody', '')
            
            # 使用LLM生成描述
            what_description = self.generate_what_description_with_llm(
                function_id, function_body, called_functions
            )
            
            result = {
                "function_id": function_id,
                "function_body": function_body,
                "direct_calls": called_functions,
                "what_description": what_description
            }
            
            self.results.append(result)
        
        print(f"Processed {len(self.results)} functions")
    
    def save_results(self):
        """保存结果到JSON文件"""
        print(f"Saving results to {self.output_file}")
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"Results saved successfully!")
    
    def run(self):
        """运行完整的提取流程"""
        print("Starting Simple Extractor...")
        
        # 检查文件是否存在
        if not self.graph_file.exists():
            raise FileNotFoundError(f"Graph file not found: {self.graph_file}")
        if not self.functions_file.exists():
            raise FileNotFoundError(f"Functions file not found: {self.functions_file}")
        
        # 执行流程
        self.load_and_filter()
        self.process_each_function()
        self.save_results()
        
        print("Extraction completed successfully!")

def main():
    """主函数"""
    # 设置工作目录
    base_dir = r"D:\Download\github\evox-ai\evox-server\.rag\xiaozhi\wifi_connect"
    
    # 创建提取器并运行
    extractor = SimpleExtractor(base_dir)
    extractor.run()

if __name__ == "__main__":
    main()
