import os
import json
import random
import yaml
from typing import List, Dict, Optional
from pathlib import Path
import re

from src.core.rag.code.tools.vscode import VSCodeClient
from src.core.rag.code.context.fileanalyze import FileAnalyzer, SymbolKind, SymbolInfo
from src.utils import get_llm, Agent
from src.base import DefaultConfig


class MultilineString(str):
    """用于标记应该以多行格式输出的字符串"""
    pass


def multiline_string_representer(dumper, data):
    """自定义表示器：将 MultilineString 表示为多行文本块（使用 |）"""
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|-')


# 注册自定义表示器
yaml.add_representer(MultilineString, multiline_string_representer)

_PROMPT = """Generate a concise business logic description (1-3 sentences) for this function. Focus on WHAT it does, not HOW. Output plain text only.

## System Design
{system_design}

## Function Code (ground_truth)
```
{ground_truth}
```

Description:"""


def _resolve_path(path: str, base_dir: Optional[str] = None) -> str:
    """解析路径：若为相对路径则基于 base_dir 或当前工作目录"""
    if os.path.isabs(path):
        return path
    base = base_dir or os.getcwd()
    # 若 path 以 evox-server 开头，尝试在 base 下查找
    if path.startswith("evox-server"):
        candidate = os.path.join(base, path)
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(os.path.join(base, path))

def generate_descriptions_for_benchmark(
    function_complement_file: str = "evox-server/.rag/benchmark/function_complement.yaml",
    functions_dir: str = "evox-server/.rag/benchmark/functions_all",
    system_design_path: str = "evox-server/.rag/knowledge/system_design.md",
    skip_existing: bool = True,
    base_dir: Optional[str] = None,
) -> int:
    """
    1. Copy ground_truth from non-reference yaml in functions_dir to function_complement entries.
    2. Generate description for each ground_truth via LLM, save to description field.
    """
    functions_path = _resolve_path(functions_dir, base_dir)
    complement_path = _resolve_path(function_complement_file, base_dir)
    sd_path = _resolve_path(system_design_path, base_dir)
    if not os.path.isdir(functions_path):
        raise FileNotFoundError(f"Directory not found: {functions_path}")

    system_design = ""
    if os.path.isfile(sd_path):
        with open(sd_path, "r", encoding="utf-8") as f:
            system_design = f.read()

    # 1. Build (file_path, query) -> ground_truth from non-reference yaml in functions_dir
    gt_lookup: Dict[tuple, str] = {}
    for fname in os.listdir(functions_path):
        if not fname.endswith(".yaml") or "reference" in fname.lower():
            continue
        with open(os.path.join(functions_path, fname), "r", encoding="utf-8") as f:
            ydata = yaml.safe_load(f)
        fp = ydata.get("file_path", "")
        for entry in ydata.get("benchmark", []):
            q = entry.get("query", "")
            gt = entry.get("ground_truth", "")
            if fp and q and gt:
                gt_lookup[(fp, q)] = gt

    # 2. Load function_complement, copy ground_truth, generate description
    with open(complement_path, "r", encoding="utf-8") as f:
        complement = yaml.safe_load(f)
    benchmark_list = complement.get("benchmark", [])

    llm = get_llm(model_name=DefaultConfig.agent_model)
    agent = Agent(llm)
    total = 0
    for entry in benchmark_list:
        fp = entry.get("file_path", "")
        q = entry.get("query", "")
        ground_truth = gt_lookup.get((fp, q))
        if not ground_truth:
            continue
        entry["ground_truth"] = ground_truth
        if skip_existing and entry.get("description"):
            continue
        prompt = _PROMPT.format(system_design=system_design or "(none)", ground_truth=ground_truth[:3000])
        try:
            desc = agent.invoke(prompt).strip()
            if desc:
                entry["description"] = desc
                total += 1
        except Exception as e:
            print(f"LLM failed for {q[:40]}...: {e}")
        

    with open(complement_path, "w", encoding="utf-8") as f:
        yaml.dump(complement, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return total


class BenchmarkBuilder:
    def __init__(self, base_url: str = "http://localhost:6789", random_seed: int = 42):
        """
        Initialize benchmark builder
        :param base_url: VSCode API server address
        :param random_seed: Random seed for reproducibility
        """
        self.vscode_client = VSCodeClient(base_url)
        self.file_analyzer = FileAnalyzer(base_url)
        random.seed(random_seed)
        self.random_seed = random_seed
    
    def scan_and_filter_files(self, directory_path: str, 
                              file_extensions: List[str] = None,
                              exclude_patterns: List[str] = None) -> List[str]:
        """扫描并筛选文件（复用 FileAnalyzer 的方法）"""
        return self.file_analyzer.scan_directory_for_files(
            directory_path, file_extensions, exclude_patterns
        )
    
    def select_random_files(self, file_paths: List[str], count: int = 10) -> List[str]:
        """
        根据随机种子从文件列表中随机选择指定数量的文件
        :param file_paths: 文件路径列表
        :param count: 要选择的文件数量
        :return: 选中的文件路径列表
        """
        if len(file_paths) < count:
            print(f"Warning: Only {len(file_paths)} files available, less than requested {count}")
            return file_paths
        return random.sample(file_paths, count)
    
    def extract_functions_from_outline(self, outline_text: str) -> List[str]:
        """
        从 outline 文本中提取函数列表
        :param outline_text: outline 文本
        :return: 函数名称列表
        """
        symbols = self.file_analyzer._parse_outline_text(outline_text)
        functions, _ = self.file_analyzer.extract_functions_and_variables(symbols)
        return functions
    
    def select_random_function(self, functions: List[str]) -> Optional[str]:
        """
        从函数列表中随机选择一个函数
        :param functions: 函数名称列表
        :return: 选中的函数名称，如果列表为空则返回 None
        """
        if not functions:
            return None
        return random.choice(functions)
    
    def filter_files_by_custom_rules(self, file_paths: List[str], directory_path: str) -> List[str]:
        """
        根据自定义规则过滤文件列表
        :param file_paths: 文件路径列表
        :param directory_path: 代码仓库根目录路径
        :return: 过滤后的文件路径列表
        """
        filtered_files = []
        excluded_count_managed = 0
        excluded_count_boards = 0
        
        for file_path in file_paths:
            # 生成相对路径（相对于代码仓库根目录）
            rel_file_path = os.path.relpath(file_path, directory_path).replace('\\', '/')
            path_parts = rel_file_path.split('/')
            
            # 规则1: 去除所有 managed_components 文件夹下的文件
            if 'managed_components' in path_parts:
                excluded_count_managed += 1
                continue
            
            # 规则2: 去除 main/boards/ 文件夹下除了 atk-dnesp32s3 和 common 以外的文件夹
            if len(path_parts) >= 3 and path_parts[0] == 'main' and path_parts[1] == 'boards':
                if len(path_parts) > 2:  # 确保有第三个路径段（boards 下的文件夹名）
                    board_folder = path_parts[2]
                    if board_folder not in ['atk-dnesp32s3', 'common']:
                        excluded_count_boards += 1
                        continue
            
            filtered_files.append(file_path)
        
        if excluded_count_managed > 0:
            print(f"  🗑️  已排除 {excluded_count_managed} 个 managed_components 文件夹下的文件")
        if excluded_count_boards > 0:
            print(f"  🗑️  已排除 {excluded_count_boards} 个 main/boards/ 下不符合条件的文件")
        
        return filtered_files
    
    def load_file_list(self, file_list_path: str, directory_path: str) -> List[str]:
        """
        从文件列表中读取文件路径，并转换为绝对路径
        :param file_list_path: 文件列表路径（可以是相对路径或绝对路径）
        :param directory_path: 代码仓库根目录路径
        :return: 文件绝对路径列表
        """
        # 如果文件列表路径是相对路径，尝试相对于脚本目录查找
        if not os.path.isabs(file_list_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                file_list_path,  # 当前目录
                os.path.join(script_dir, file_list_path),  # 脚本目录
                os.path.join(directory_path, file_list_path),  # 仓库根目录
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    file_list_path = path
                    break
            else:
                raise FileNotFoundError(f"找不到文件列表: {file_list_path}")
        
        if not os.path.exists(file_list_path):
            raise FileNotFoundError(f"文件列表不存在: {file_list_path}")
        
        file_paths = []
        with open(file_list_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue
                
                # 转换为绝对路径
                if os.path.isabs(line):
                    abs_path = line
                else:
                    abs_path = os.path.join(directory_path, line)
                
                # 标准化路径分隔符（统一使用系统路径分隔符）
                abs_path = os.path.normpath(abs_path)
                
                # 检查文件是否存在
                if os.path.exists(abs_path):
                    file_paths.append(abs_path)
                else:
                    print(f"  ⚠️  警告: 文件不存在，跳过: {line}")
        
        return file_paths
    
    def build_benchmark(self, 
                       directory_path: str,
                       num_files: int = 10,
                       output_dir: str = "evox-server/.rag/benchmark",
                       function_complement_file: str = "function_complement.yaml",
                       file_list_path: Optional[str] = None) -> bool:
        """
        构建 benchmark 数据集
        
        :param directory_path: 代码仓库目录路径
        :param num_files: 要选择的文件数量
        :param output_dir: 输出目录
        :param function_complement_file: function_complement.yaml 文件名
        :param file_list_path: 文件列表路径（如果提供，则使用文件列表而不是扫描目录）
        :return: 是否成功
        """
        print(f"🔍 开始构建 benchmark，随机种子: {self.random_seed}")
        print(f"📁 代码仓库目录: {directory_path}")
        
        # 如果提供了文件列表路径，则使用文件列表；否则扫描目录
        if file_list_path:
            print(f"📄 使用文件列表: {file_list_path}")
            try:
                all_files = self.load_file_list(file_list_path, directory_path)
                print(f"✅ 从文件列表加载了 {len(all_files)} 个文件")
            except FileNotFoundError as e:
                print(f"❌ 错误: {e}")
                return False
        else:
            print(f"📁 扫描目录: {directory_path}")
            
            # 设置文件扩展名和排除模式（参考 graph_constructor.py）
            file_extensions = ['.cc']
            exclude_patterns = [
                '__pycache__', '.git', '.svn', '.hg',
                'node_modules', '.vscode', '.idea',
                'build', 'dist', '.pytest_cache',
                '.mypy_cache', '.tox', 'venv', 'env'
            ]
            
            # a. 扫描并筛选文件
            all_files = self.scan_and_filter_files(
                directory_path, 
                file_extensions=file_extensions,
                exclude_patterns=exclude_patterns
            )
            print(f"✅ 找到 {len(all_files)} 个 .cc 文件")
            
            # 应用自定义过滤规则
            print(f"\n🔍 应用自定义过滤规则...")
            all_files = self.filter_files_by_custom_rules(all_files, directory_path)
            print(f"✅ 过滤后剩余 {len(all_files)} 个 .cc 文件")
        
        # 列出所有符合条件的文件
        if all_files:
            print(f"\n📋 符合条件的文件列表（共 {len(all_files)} 个）:")
            for idx, file_path in enumerate(all_files, start=1):
                # 生成相对路径（相对于代码仓库根目录）
                rel_file_path = os.path.relpath(file_path, directory_path).replace('\\', '/')
                print(f"  {idx:4d}. {rel_file_path}")
        else:
            print("⚠️  未找到符合条件的文件")
            return False
        
        # 随机选择文件
        selected_files = self.select_random_files(all_files, num_files)
        print(f"✅ 随机选择了 {len(selected_files)} 个文件")
        
        # 准备输出
        os.makedirs(output_dir, exist_ok=True)
        functions_dir = os.path.join(output_dir, 'functions_all')
        os.makedirs(functions_dir, exist_ok=True)
        benchmark_entries = []
        successful_count = 0
        
        # b. 对每个文件获取 outline 并提取函数
        for idx, file_path in enumerate(selected_files, start=1):
            print(f"\n📄 [{idx}/{len(selected_files)}] 处理文件: {file_path}")
            
            # 获取 outline
            outline_text = self.vscode_client.get_file_outline(file_path)
            if not outline_text:
                print(f"  ⚠️  无法获取 outline，跳过")
                continue
            
            # 提取函数
            functions = self.extract_functions_from_outline(outline_text)
            if not functions:
                print(f"  ⚠️  未找到函数，跳过")
                continue
            
            print(f"  ✅ 找到 {len(functions)} 个函数")
            
            # 生成相对路径（相对于代码仓库根目录）
            rel_file_path = os.path.relpath(file_path, directory_path).replace('\\', '/')
            
            # c. 提取所有长度超过3的函数
            valid_functions = []  # 存储符合条件的函数信息
            
            for func_name in functions:
                func_info = self.vscode_client.get_function_body_with_range(file_path, func_name)
                if not func_info:
                    continue
                
                range_info = func_info['range']
                # 提取行号（VSCode 使用 0-based，转换为 1-based）
                start_line = range_info.get('start', {}).get('line', 0) + 1
                end_line = range_info.get('end', {}).get('line', 0) + 1
                
                # 计算函数长度（行数）
                function_length = end_line - start_line + 1
                
                # 只保留长度超过3的函数
                if function_length > 3:
                    function_body = func_info['functionBody']
                    # 标准化换行符：将 \r\n 和 \r 转换为 \n，并去除末尾的空白换行符
                    function_body = function_body.replace('\r\n', '\n').replace('\r', '\n').rstrip()
                    
                    valid_functions.append({
                        'name': func_name,
                        'body': function_body,
                        'start_line': start_line,
                        'end_line': end_line
                    })
                    print(f"  ✅ 函数 {func_name}: {function_length} 行 (行 {start_line}-{end_line})")
            
            # 如果该文件没有符合条件的函数，跳过
            if not valid_functions:
                print(f"  ⚠️  未找到长度超过3的函数，跳过该文件")
                continue
            
            print(f"  ✅ 共找到 {len(valid_functions)} 个符合条件的函数")
            
            # d. 生成 YAML 文件（使用源文件名命名）
            # 从文件路径中提取文件名（不含扩展名）
            file_name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
            yaml_filename = f"{file_name_without_ext}.yaml"
            yaml_path = os.path.join(functions_dir, yaml_filename)
            
            # 创建 YAML 内容（参考 main.yaml 格式）
            yaml_content = {
                'file_path': rel_file_path,
                'benchmark': []
            }
            
            # 为每个符合条件的函数创建 benchmark 条目
            for func_data in valid_functions:
                benchmark_entry = {
                    'query': f'complete the function {func_data["name"]}()',
                    'ground_truth': MultilineString(func_data['body']),  # 使用 MultilineString
                    'workflow': '',  # 暂时为空
                    'cursor': ''     # 暂时为空
                }
                yaml_content['benchmark'].append(benchmark_entry)
                
                # 同时添加到 function_complement.yaml 的条目中
                benchmark_entries.append({
                    'query': f'complete the function {func_data["name"]}()',
                    'file_path': rel_file_path,
                    'start_line': func_data['start_line'],
                    'end_line': func_data['end_line']
                })
            
            # 写入 YAML 文件
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_content, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            print(f"  ✅ 已生成: {yaml_filename} (包含 {len(valid_functions)} 个函数)")
            successful_count += 1
        
        # 生成 function_complement.yaml
        complement_path = os.path.join(output_dir, function_complement_file)
        complement_content = {'benchmark': benchmark_entries}
        with open(complement_path, 'w', encoding='utf-8') as f:
            yaml.dump(complement_content, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        print(f"\n✅ Benchmark 构建完成！")
        print(f"   - 成功处理: {successful_count}/{num_files} 个文件")
        print(f"   - 输出目录: {output_dir}")
        print(f"   - 索引文件: {function_complement_file}")
        
        return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Build benchmark dataset')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # 子命令: build - 构建 benchmark
    build_parser = subparsers.add_parser('build', help='Build benchmark from code repository')
    build_parser.add_argument('--directory', type=str, required=True, help='Code repository directory path')
    build_parser.add_argument('--num-files', type=int, default=10, help='Number of files to select')
    build_parser.add_argument('--output-dir', type=str, default='evox-server/.rag/benchmark', help='Output directory')
    build_parser.add_argument('--random-seed', type=int, default=42, help='Random seed')
    build_parser.add_argument('--base-url', type=str, default='http://localhost:6789', help='VSCode API base URL')
    build_parser.add_argument('--file-list', type=str, default=None,
                             help='Path to file list (if provided, use file list instead of scanning directory). '
                                  'Default: atk_dnesp32s3_file_list.txt in the same directory as this script')

    # 子命令: generate-descriptions - 为 benchmark 生成 description
    desc_parser = subparsers.add_parser('generate-descriptions', help='Generate business logic descriptions')
    desc_parser.add_argument('--function-complement', type=str,
                            default='evox-server/.rag/benchmark/function_complement.yaml')
    desc_parser.add_argument('--functions-dir', type=str,
                            default='evox-server/.rag/benchmark/functions_all')
    desc_parser.add_argument('--system-design', type=str,
                            default='evox-server/.rag/knowledge/system_design.md')
    desc_parser.add_argument('--overwrite', action='store_true',
                            help='Overwrite existing descriptions')
    desc_parser.add_argument('--base-dir', type=str, default=None)

    args = parser.parse_args()

    if args.command == 'generate-descriptions':
        count = generate_descriptions_for_benchmark(
            function_complement_file=args.function_complement,
            functions_dir=args.functions_dir,
            system_design_path=args.system_design,
            skip_existing=not args.overwrite,
            base_dir=args.base_dir,
        )
        print(f"✅ 完成，共生成 {count} 个 description")
    elif args.command == 'build':
        file_list_path = args.file_list
        if file_list_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            default_file_list = os.path.join(script_dir, 'atk_dnesp32s3_file_list.txt')
            if os.path.exists(default_file_list):
                file_list_path = default_file_list
                print(f"ℹ️  使用默认文件列表: {file_list_path}")
        builder = BenchmarkBuilder(base_url=args.base_url, random_seed=args.random_seed)
        builder.build_benchmark(
            directory_path=args.directory,
            num_files=args.num_files,
            output_dir=args.output_dir,
            file_list_path=file_list_path
        )
    else:
        parser.print_help()

