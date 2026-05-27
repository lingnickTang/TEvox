#!/usr/bin/env python3
"""
从函数调用关系图生成文件依赖关系图
"""
import json
import os
from collections import defaultdict

def extract_file_path(func_id):
    """从函数ID中提取文件路径
    输入: "func:main/application.cc:Application()"
    输出: "main/application.cc" (去除file:前缀)
    """
    if not func_id.startswith("func:"):
        return None
    # 移除 "func:" 前缀，然后找到第三个冒号之前的部分
    parts = func_id[5:].split(":", 1)  # 分割成 [file_path, function_name]
    if len(parts) < 1:
        return None
    return parts[0]  # 直接返回文件路径，不添加"file:"前缀

def load_valid_modules(file_status_path):
    """从file_status.json加载有效模块路径集合"""
    with open(file_status_path, 'r', encoding='utf-8') as f:
        file_status = json.load(f)
    
    # 提取所有模块的path字段，组成集合
    valid_modules = {item['path'] for item in file_status if 'path' in item}
    return valid_modules

def build_file_dependencies(input_file, output_file, file_status_path):
    """构建文件依赖关系图"""
    # 加载有效模块集合
    valid_modules = load_valid_modules(file_status_path)
    print(f"加载了 {len(valid_modules)} 个有效模块")
    
    # 读取函数调用关系图
    with open(input_file, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    
    # 使用 defaultdict 自动初始化空集合
    # key: 文件路径, value: 该文件依赖的文件路径集合
    file_dependencies = defaultdict(set)
    
    # 遍历所有函数节点
    for node in graph.get("nodes", []):
        caller_func_id = node.get("id")
        caller_file = extract_file_path(caller_func_id)
        
        if not caller_file:
            continue
        
        # 只处理在有效模块列表中的文件
        if caller_file not in valid_modules:
            continue
        
        # 遍历该函数调用的所有函数
        for callee_func_id in node.get("direct_calls", []):
            callee_file = extract_file_path(callee_func_id)
            
            if not callee_file:
                continue
            
            # 只处理在有效模块列表中的被调用文件
            if callee_file not in valid_modules:
                continue
            
            # 如果调用者和被调用者不在同一文件，建立依赖关系
            if caller_file != callee_file:
                # caller_file 依赖 callee_file
                # 所以在 file_dependencies[caller_file] 中添加 callee_file
                file_dependencies[caller_file].add(callee_file)
    
    # 确保所有有效模块都出现在输出中，即使没有依赖关系也记录为 []
    # 首先初始化所有模块为空列表
    output_edges = {module: [] for module in valid_modules}
    
    # 然后更新有依赖关系的模块
    for file, dependents in file_dependencies.items():
        if file in output_edges:
            output_edges[file] = sorted(dependents)
    
    # 转换为输出格式：字典，值为排序后的列表
    # key 已经是文件路径（无"file:"前缀），value 是该文件依赖的文件列表
    output = {
        "edges": {
            file: dependents 
            for file, dependents in sorted(output_edges.items())
        }
    }
    
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"已生成文件依赖关系图: {output_file}")
    print(f"共 {len(output['edges'])} 个文件")

if __name__ == "__main__":
    base_path = "D:/Download/github/evox-ai/evox-server/.rag/xiaozhi/full_code"
    input_file = os.path.join(base_path, "functions_what_graph_concurrent.json")
    output_file = os.path.join(base_path, "file_dependencies.json")
    file_status_path = os.path.join(base_path, "file_status.json")
    
    build_file_dependencies(input_file, output_file, file_status_path)

