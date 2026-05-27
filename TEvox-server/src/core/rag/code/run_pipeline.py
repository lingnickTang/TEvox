#!/usr/bin/env python
"""
代码索引管道运行脚本
运行整个代码索引流程
"""
import os
import sys
import json
import argparse
import subprocess
import time

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Run the code indexing pipeline')
    parser.add_argument('--repo-path', 
                        type=str, 
                        required=True, 
                        help='Path to the code repository to analyze')
    parser.add_argument('--rag-path', 
                        type=str, 
                        default=None, 
                        help='Directory to store database files')
    parser.add_argument('--api-endpoint', 
                        type=str, 
                        default='http://localhost:6789', 
                        help='VSCode extension API endpoint')
    return parser.parse_args()

def create_config(args):
    """创建配置文件"""
    # 设置默认输出目录（如果没有提供）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if args.rag_path is None:
        rag_path = os.path.join(script_dir, '.output')
    else:
        rag_path = os.path.abspath(args.rag_path)
    
    # 确保输出目录存在
    os.makedirs(rag_path, exist_ok=True)
    
    # 创建配置
    config = {
        'codeRepositoryPath': os.path.abspath(args.repo_path),
        'ragOutputDir': os.path.join(rag_path, 'output'),
        'codeFilesPath': os.path.join(rag_path, 'output', 'code_files.md'),
        'symbolsJsonPath': os.path.join(rag_path, 'output', 'symbols.json'),
        'functionBodiesPath': os.path.join(rag_path, 'output', 'functions_bodys.jsonl'),
        'baseTextUnitsPath': os.path.join(rag_path, 'output', 'base_text_units.json'),
        'topKMatchesPath': os.path.join(rag_path, 'output', 'all_functions_topk_matches.json'),
        'nxGraphPath': os.path.join(rag_path, 'output', 'nxgraph_txt_with_code.graphml'),
        'apiEndpoint': args.api_endpoint,
        'cacheDir': os.path.join(rag_path, 'cache'),
    }
    
    # # 寻找基本的文本单元文件，若不存在，报错
    # base_text_units_path = os.path.join(args.rag_path, 'output', 'base_text_units.json')
    # if not os.path.exists(base_text_units_path):
    #     raise FileNotFoundError(f"Base text units file not found at {base_text_units_path}")
    # config['baseTextUnitsPath'] = base_text_units_path
    
    # 保存配置文件
    config_path = os.path.join(rag_path, 'pipeline_config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    return config_path

def run_pipeline_step(script_path, config_path, step_name):
    """运行管道中的一个步骤"""
    print(f"\n{'='*30}")
    print(f"Running {step_name}...")
    print(f"{'='*30}")
    
    start_time = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script_path, '--config', config_path],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(f"Warnings: {result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Error running {step_name}: {e}")
        print(f"Output: {e.output}")
        print(f"Error: {e.stderr}")
        return False
    
    elapsed_time = time.time() - start_time
    print(f"{step_name} completed in {elapsed_time:.2f} seconds")
    return True

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 创建配置文件
    config_path = create_config(args)
    print(f"Created configuration file: {config_path}")
    
    # 获取脚本目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    index_dir = os.path.join(script_dir, 'index')
    
    # 定义管道步骤
    pipeline_steps = [
        {
            'script': os.path.join(index_dir, 'function_graph', 'find_all_files.py'),
            'name': 'File scanning'
        },
        {
            'script': os.path.join(index_dir, 'function_graph', 'find_all_symbols.py'),
            'name': 'Symbol extraction'
        },
        {
            'script': os.path.join(index_dir, 'function_graph', 'acquire_functions_bodys.py'),
            'name': 'Function body extraction'
        },
        # {
        #     'script': os.path.join(index_dir, 'similarity', 'compute_function_text_similarities.py'),
        #     'name': 'Similarity computation'
        # },
        {
            'script': os.path.join(index_dir, 'function_graph', 'store_nxgraph_txt_with_code.py'),
            'name': 'Graph creation'
        }
    ]
    
    # 运行每个步骤
    start_time = time.time()
    
    for step in pipeline_steps:
        success = run_pipeline_step(step['script'], config_path, step['name'])
        if not success:
            print(f"Pipeline failed at step: {step['name']}")
            return 1
    
    total_time = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"Pipeline completed successfully in {total_time:.2f} seconds")
    print(f"{'='*50}")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 