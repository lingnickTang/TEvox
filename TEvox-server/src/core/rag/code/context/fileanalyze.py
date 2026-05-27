import json
import requests
import re
import os
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from tqdm import tqdm
import hashlib
import uuid

class SymbolKind(Enum):
    """VSCode SymbolKind枚举值"""
    FILE = 0
    MODULE = 1
    NAMESPACE = 2
    PACKAGE = 3
    CLASS = 4
    METHOD = 5
    PROPERTY = 6
    FIELD = 7
    CONSTRUCTOR = 8
    ENUM = 9
    INTERFACE = 10
    FUNCTION = 11
    VARIABLE = 12
    CONSTANT = 13
    STRING = 14
    NUMBER = 15
    BOOLEAN = 16
    ARRAY = 17
    OBJECT = 18
    KEY = 19
    NULL = 20
    ENUM_MEMBER = 21
    STRUCT = 22
    EVENT = 23
    OPERATOR = 24
    TYPE_PARAMETER = 25

@dataclass
class SymbolInfo:
    name: str
    kind: str  # 使用字符串类型，因为API返回的是文本
    kind_enum: Optional[SymbolKind] = None

@dataclass
class FileAnalysisResult:
    file_path: str
    functions: List[str]
    global_variables: List[str]
    global_var_analysis: Dict[str, Dict] 
    all_symbols: List[SymbolInfo]
    referenced_files: Set[str]
    referencing_files: Set[str]
    outgoing_calls: Dict[str, List[str]]
    incoming_calls: Dict[str, List[str]]
    struct_analysis: Dict[str, Dict]
    class_members: Dict[str, List]
    class_references: Dict[str, List]

class FileAnalyzer:
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        # 定义符号类型映射，基于VSCode API文档 [[0]](#__0)
        self.symbol_kind_mapping = {
            'Function': SymbolKind.FUNCTION,
            'Method': SymbolKind.METHOD,
            'Variable': SymbolKind.VARIABLE,
            'Constant': SymbolKind.CONSTANT,
            'Class': SymbolKind.CLASS,
            'Interface': SymbolKind.INTERFACE,
            'Enum': SymbolKind.ENUM,
            'Property': SymbolKind.PROPERTY,
            'Field': SymbolKind.FIELD,
            'Constructor': SymbolKind.CONSTRUCTOR,
            'Module': SymbolKind.MODULE,
            'Namespace': SymbolKind.NAMESPACE,
            'Package': SymbolKind.PACKAGE,
            'Struct': SymbolKind.STRUCT,
            'Event': SymbolKind.EVENT,
            'Operator': SymbolKind.OPERATOR,
            'TypeParameter': SymbolKind.TYPE_PARAMETER,
        }

    def _normalize_path(self, path: str) -> str:
        """标准化路径，统一使用正斜杠"""
        return os.path.normpath(path).replace('\\', '/')

    def _get_relative_path(self, file_path: str, base_path: str) -> str:
        """获取相对于base_path的相对路径"""
        try:
            rel_path = os.path.relpath(file_path, base_path)
            return self._normalize_path(rel_path)
        except ValueError:
            # 如果无法计算相对路径（比如在不同驱动器），返回文件名
            return os.path.basename(file_path)

    def _generate_function_node_id(self, file_path: str, function_name: str, base_path: str) -> str:
        """生成与graph_constructor对齐的函数节点ID"""
        rel_path = self._get_relative_path(file_path, base_path)
        return f"func:{rel_path}:{function_name}"

    def get_function_body(self, file_path: str, symbol_name: str) -> Optional[str]:
        """获取函数体
        
        Args:
            file_path: 文件路径
            symbol_name: 符号名称
            
        Returns:
            函数体字符串，如果获取失败则返回None
        """
        try:
            response = requests.get(
                f"{self.base_url}/symbols/function_body",
                params={"filePath": file_path, "symbolName": symbol_name.strip()}
            )
            if response.status_code == 200:
                resp = response.json()
                function_body = resp.get('functionBody', '')
                # 跳过函数声明（以分号结尾）
                if function_body.endswith(');'):
                    return None
                return function_body
            return None
        except Exception as e:
            print(f"Error getting function body for {symbol_name} in {file_path}: {e}")
            return None

    def generate_functions_bodies_jsonl(self, file_paths: List[str], output_file: str, base_path: str = None) -> bool:
        """生成functions_bodys.jsonl文件
        
        Args:
            file_paths: 文件路径列表
            output_file: 输出文件路径
            base_path: 项目基础路径，用于生成相对路径
            
        Returns:
            是否成功生成
        """
        if base_path is None:
            base_path = os.getcwd()
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 检查已存在的函数体
        existing_functions = set()
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        filepath = data.get('filepath', '').strip()
                        symbol_name = data.get('symbolName', '').strip()
                        existing_functions.add(f"{filepath}:{symbol_name}")
                    except:
                        continue
        
        total_functions = 0
        success_count = 0
        
        print(f"🔍 开始生成functions_bodys.jsonl文件...")
        print(f"📁 基础路径: {base_path}")
        print(f"📄 输出文件: {output_file}")
        
        # 使用追加模式打开文件
        with open(output_file, 'a', encoding='utf-8') as f:
            for file_path in tqdm(file_paths, desc="Processing files"):
                # 获取文件的函数符号
                symbols = self.get_file_outline(file_path)
                if not symbols:
                    continue
                functions, _ = self.extract_functions_and_variables(symbols)
                total_functions += len(functions)
                
                for func_name in functions:
                    func_key = f"{file_path}:{func_name}"
                    if func_key in existing_functions:
                        success_count += 1
                        continue
                    
                    # 获取函数体
                    function_body = self.get_function_body(file_path, func_name)
                    if function_body:
                        # 构建数据结构
                        data = {
                            'filepath': file_path,
                            'symbolName': func_name,
                            'functionBody': function_body,
                            'id': str(uuid.uuid4()),
                            'graph_node_id': self._generate_function_node_id(file_path, func_name, base_path),
                            'relative_path': self._get_relative_path(file_path, base_path)
                        }
                        
                        # 写入文件
                        f.write(json.dumps(data, ensure_ascii=False) + '\n')
                        success_count += 1
        
        print(f"✅ 成功生成 {success_count}/{total_functions} 个函数体")
        print(f"📄 输出文件: {output_file}")
        return True

    def scan_directory_for_files(self, directory_path: str, 
                                file_extensions: List[str] = None,
                                exclude_patterns: List[str] = None) -> List[str]:
        """扫描目录获取所有符合条件的文件
        
        Args:
            directory_path: 目录路径
            file_extensions: 文件扩展名列表
            exclude_patterns: 排除模式列表
            
        Returns:
            文件路径列表
        """
        if file_extensions is None:
            file_extensions = ['.py', '.cpp', '.c', '.h', '.hpp', '.cc', '.cxx', '.js', '.ts']
        
        if exclude_patterns is None:
            exclude_patterns = [
                '__pycache__', '.git', '.svn', '.hg',
                'node_modules', '.vscode', '.idea',
                'build', 'dist', '.pytest_cache',
                '.mypy_cache', '.tox', 'venv', 'env'
            ]
        
        file_paths = []
        
        def should_exclude(path: str) -> bool:
            """检查路径是否应该被排除"""
            path_name = os.path.basename(path)
            for pattern in exclude_patterns:
                if pattern in path_name or path_name.startswith('.'):
                    return True
            return False
        
        def has_valid_extension(file_path: str) -> bool:
            """检查文件是否有有效的扩展名"""
            _, ext = os.path.splitext(file_path)
            return ext.lower() in [e.lower() for e in file_extensions]
        
        for root, dirs, files in os.walk(directory_path):
            # 过滤目录
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d))]
            
            # 处理文件
            for file in files:
                file_path = os.path.join(root, file)
                if has_valid_extension(file_path) and not should_exclude(file_path):
                    file_paths.append(file_path)
        
        return file_paths

    def get_file_outline(self, file_path: str) -> Optional[List[SymbolInfo]]:
        """获取文件的符号outline"""
        try:
            # 使用与你示例相同的API端点格式
            response = requests.get(f"{self.base_url}/symbols/outline", 
                                  params={"filePath": file_path})
            if response.status_code == 200:
                res = json.loads(response.text)['outline']
                return self._parse_outline_text(res)
            else:
                print(f"Failed to get outline for {file_path}: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error getting outline for {file_path}: {e}")
            return None
    
    def _parse_outline_text(self, outline_text: str) -> List[SymbolInfo]:
        """解析文本格式的outline"""
        symbols = []
        lines = outline_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 解析格式如 "GPIO_TAG (Variable)" [[1]](#__1)
            match = re.match(r'(.*?)\s+\((.*?)\)$', line)
            if match:
                symbol_name = match.group(1).strip()
                symbol_kind = match.group(2).strip()
                
                # 处理特殊结构体命名情况
                # 例如：camera_state_t (Interface)
                # 后面跟着__unnamed_struct_345c_1 (Struct)
                if symbol_kind == 'Interface':
                    next_line = lines[lines.index(line)+1] if lines.index(line)+1 < len(lines) else None
                    if next_line and next_line.strip().startswith('__unnamed_struct_'):
                        struct_match = re.match(r'(.*?)\s+\((.*?)\)$', next_line.strip())
                        if struct_match:
                            symbol_kind = 'Struct'
                
                # 转换为枚举类型
                kind_enum = self.symbol_kind_mapping.get(symbol_kind)
                
                symbol_info = SymbolInfo(
                    name=symbol_name,
                    kind=symbol_kind,
                    kind_enum=kind_enum
                )
                symbols.append(symbol_info)
        
        return symbols
    
    def extract_functions_and_variables(self, symbols: List[SymbolInfo]) -> Tuple[List[str], List[str]]:
        """从符号列表中提取函数和全局变量"""
        functions = []
        global_variables = []
        
        for symbol in symbols:
            # 根据VSCode Workspace Symbol Provider API，提取函数类型符号 [[3]](#__3)
            if symbol.kind_enum in [SymbolKind.FUNCTION, SymbolKind.METHOD]:
                functions.append(symbol.name)
            # 提取变量和常量 [[0]](#__0)
            elif symbol.kind_enum in [SymbolKind.VARIABLE, SymbolKind.CONSTANT]:
                global_variables.append(symbol.name)
        
        return functions, global_variables
    
    def get_function_calls(self, file_path: str, function_name: str) -> Tuple[List[Dict], List[Dict]]:
        """获取函数的调用和被调用关系
        
        Returns:
            Tuple[List[Dict], List[Dict]]: 返回(outgoing_calls, incoming_calls)
            每个调用包含完整信息：
            {
                'name': 函数名,
                'file_path': 文件路径,
                'range': 函数定义范围,
                'call_ranges': 调用位置范围列表
            }
        """
        try:
            # 获取outgoing calls
            outgoing_response = requests.get(
                f"{self.base_url}/symbols/outgoing_calls", 
                params={"filePath": file_path, "symbolName": function_name}
            )
            outgoing_calls = []
            if outgoing_response.status_code == 200:
                outgoing_data = outgoing_response.json()
                for call in outgoing_data.get('outgoingCalls', []):
                    to_info = call.get('to', {})
                    outgoing_calls.append({
                        'name': to_info.get('name', ''),
                        'file_path': to_info.get('uri', {}).get('fsPath', ''),
                        'range': to_info.get('range', []),
                        'call_ranges': call.get('fromRanges', [])
                    })
            
            # 获取incoming calls
            incoming_response = requests.get(
                f"{self.base_url}/symbols/incoming_calls", 
                params={"filePath": file_path, "symbolName": function_name}
            )
            incoming_calls = []
            if incoming_response.status_code == 200:
                incoming_data = incoming_response.json()
                for call in incoming_data.get('incomingCalls', []):
                    from_info = call.get('from', {})
                    incoming_calls.append({
                        'name': from_info.get('name', ''),
                        'file_path': from_info.get('uri', {}).get('fsPath', ''),
                        'range': from_info.get('range', []),
                        'call_ranges': call.get('fromRanges', [])
                    })
            
            return outgoing_calls, incoming_calls
            
        except Exception as e:
            print(f"Error getting function calls for {function_name}: {e}")
            return [], []
        
    def get_variable_definition(self, file_path: str, var_name: str) -> Optional[Dict]:
        """获取变量的定义位置"""
        try:
            response = requests.get(
                f"{self.base_url}/symbols/definition",
                params={"filePath": file_path, "symbolName": var_name}
            )
            definition = None
            if response.status_code == 200:
                data = response.json()
                definition = data.get('definition')
                if definition:
                    # 确保返回格式与函数调用一致
                    definition = {
                        'name': var_name,
                        'file_path': definition.get('uri', {}).get('fsPath', ''),
                        'range': definition.get('range', []),
                    }
            return definition
                
        except Exception as e:
            print(f"Error getting variable definition for {var_name}: {e}")
            return None

    def get_variable_references(self, file_path: str, var_name: str) -> List[Dict]:
        """获取变量的所有引用位置"""
        try:
            response = requests.get(
                f"{self.base_url}/symbols/references",
                params={"filePath": file_path, "symbolName": var_name}
            )
            references = []
            if response.status_code == 200:
                data = response.json()
                for ref in data.get('references', []):
                    references.append({
                        'name': var_name,
                        'file_path': ref.get('uri', {}).get('fsPath', ''),
                        'range': ref.get('range', []),
                        'call_ranges': [ref.get('range', [])]  # 保持与函数调用格式一致
                    })
            return references
                
        except Exception as e:
            print(f"Error getting variable references for {var_name}: {e}")
            return []

    def get_variable_hover(self, file_path: str, var_name: str) -> str:
        """获取变量的hover信息"""
        try:
            response = requests.get(
                f"{self.base_url}/symbols/symbol_hover",
                params={"filePath": file_path, "symbolName": var_name}
            )
            return response.json().get('hover', '')
        except Exception as e:
            print(f"Error getting variable hover for {var_name}: {e}")
            return ""
        
    def analyze_global_variable(self, file_path: str, var_name: str) -> Dict:
        """分析单个全局变量的完整信息"""
        # 获取变量定义
        definition = self.get_variable_definition(file_path, var_name)
        
        # 获取变量引用
        references = self.get_variable_references(file_path, var_name)

        hover = self.get_variable_hover(file_path, var_name)

        # 收集引用该变量的文件
        referencing_files = set()
        for ref in references:
            ref_file = ref['file_path']
            if ref_file != file_path:
                referencing_files.add(ref_file)
        
        return {
            'name': var_name,
            'hover': hover,
            'definition': definition,
            'references': references,
            'referencing_files': list(referencing_files)
        }

    def extract_class(self, symbols: List[SymbolInfo]):
        all_classes = []
        for symbol in symbols:
            if symbol.kind == 'class':
                all_classes.append(symbol)
        return all_classes
    
    def get_class_members(self, file_path: str,  classes: List[SymbolInfo]):
        class_members = {}
        for class_item in classes:
            try:
                response = requests.get(
                    f"{self.base_url}/symbols/class_members",
                    params={"filePath": file_path, "className": class_item.name}
                )
                if response.status_code == 200:
                    data = response.json()
                    now_members = data.get('members', [])
                    class_members[class_item.name] = now_members
            except Exception as e:
                print(f"Error getting class members for {class_item.name}: {e}")
        return class_members
    
    def get_class_references(self, file_path: str, classes: List[SymbolInfo]):
        class_references = {}
        for class_item in classes:
            try:
                response = requests.get(
                    f"{self.base_url}/symbols/references",
                    params={"filePath": file_path, "symbolName": class_item.name}
                )
                if response.status_code == 200:
                    data = response.json()
                    now_references = data.get('references', [])
                    for ref in now_references:
                        ref_file = ref['uri']["path"]
                        response = requests.get(f"{self.base_url}/symbols/find_symbols_refer_this_symbol",
                            params={"filePath": ref_file,"symbolName":class_item.name, "start_line": ref["range"][0]["line"],"end_line": ref["range"][1]["line"]}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            ref['symbol'] = data.get('symbol', {})
                    class_references[class_item.name] = now_references
            except Exception as e:
                print(f"Error getting class references for {class_item.name}: {e}")
        return class_references

    def analyze_file(self, file_path: str, use_cache: bool = True, cache_dir: str = None) -> Optional[FileAnalysisResult]:
        """分析单个文件的完整信息"""
        # print(f"Analyzing file: {file_path}")
        
        # 获取文件outline
        symbols = self.get_file_outline(file_path)
        if not symbols:
            return None
        
        # 提取函数和全局变量
        functions, global_variables = self.extract_functions_and_variables(symbols)
        
        # 分析函数调用关系
        outgoing_calls = {}
        incoming_calls = {}
        referenced_files = set()
        referencing_files = set()
        
        for func_name in functions:
            outgoing, incoming = self.get_function_calls(file_path, func_name)
            outgoing_calls[func_name] = outgoing
            incoming_calls[func_name] = incoming
            
            # 从调用关系中提取文件引用信息
            for call in outgoing:
                call_file = call['file_path']
                if call_file and call_file != file_path:
                    referenced_files.add(call_file)
            
            for call in incoming:
                call_file = call['file_path']
                if call_file and call_file != file_path:
                    referencing_files.add(call_file)
        
        # 分析全局变量
        global_var_analysis = {}
        for var_name in global_variables:
            var_info = self.analyze_global_variable(file_path, var_name)
            global_var_analysis[var_name] = var_info
            
            # 添加引用全局变量的文件到引用关系中
            referencing_files.update(var_info['referencing_files'])
        
        # 分析结构体使用情况
        struct_definitions = [s for s in symbols if s.kind == 'Struct']
        struct_analysis_results = {}
        for struct in struct_definitions:
            struct_name = struct.name
            # 调用API获取结构体详细分析结果
            try:
                struct_results = {}
                response = requests.get(
                    f"{self.base_url}/symbols/struct_fields",
                    params={"filePath": file_path, "structName": struct_name}
                )
                if response.status_code == 200:
                    data = response.json()
                    struct_results['fields'] = data.get('fields', [])
                
                response = requests.get(
                    f"{self.base_url}/symbols/references",
                    params={"filePath": file_path, "symbolName": struct_name}
                )

                if response.status_code == 200:
                    data = response.json()
                    references = data.get('references', [])
                    for ref in references:
                        ref_file = ref['uri']["fsPath"]
                        response = requests.get(f"{self.base_url}/symbols/find_symbols_refer_this_symbol",
                            params={"filePath": ref_file, "symbolName":struct_name, "start_line": ref["range"][0]["line"], "end_line": ref["range"][1]["line"]}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            ref['symbol'] = data.get('symbol', {})
                            
                    struct_results['references'] = references
                
                print(struct_results)
                struct_analysis_results[struct_name] = struct_results

            except Exception as e:
                print(f"Error analyzing struct {struct_name}: {e}")
        
        classes = self.extract_class(symbols)
        class_members = self.get_class_members(file_path, classes)
        class_references = self.get_class_references(file_path, classes)

        result = FileAnalysisResult(
            file_path=file_path,
            functions=functions,
            global_variables=global_variables,
            global_var_analysis=global_var_analysis,
            all_symbols=symbols,
            referenced_files=referenced_files,
            referencing_files=referencing_files,
            outgoing_calls=outgoing_calls,
            incoming_calls=incoming_calls,
            struct_analysis=struct_analysis_results,
            class_members=class_members,
            class_references=class_references
        )
        
        return result
    
    def generate_file_summary(self, result: FileAnalysisResult) -> str:
        """生成文件分析摘要"""
        summary = f"""
    文件分析报告: {result.file_path}
    ==========================================

    函数列表 ({len(result.functions)}个):
    {chr(10).join(f"  - {func}" for func in result.functions)}

    全局变量 ({len(result.global_variables)}个):
    {chr(10).join(f"  - {var}" for var in result.global_variables)}

    所有符号 ({len(result.all_symbols)}个):
    {chr(10).join(f"  - {s.name} ({s.kind})" for s in result.all_symbols)}

    引用的文件 ({len(result.referenced_files)}个):
    {chr(10).join(f"  - {file}" for file in result.referenced_files)}

    被引用的文件 ({len(result.referencing_files)}个):
    {chr(10).join(f"  - {file}" for file in result.referencing_files)}

    全局变量分析:
    """
        # 添加全局变量分析部分
        for var_name, var_info in result.global_var_analysis.items():
            summary += f"\n  {var_name}:\n"
            
            # 添加定义位置
            if var_info['definition']:
                def_uri = var_info['definition']['file_path']
                def_range = var_info['definition']['range']
                summary += f"    定义位置: {def_uri} (行 {def_range[0]['line'] + 1})\n"
            
            # 添加引用信息
            references = var_info['references']
            if references:
                summary += f"    引用位置 ({len(references)}处):\n"
                for ref in references:
                    ref_uri = ref['file_path']
                    ref_range = ref['range']
                    summary += f"      - {ref_uri} (行 {ref_range[0]['line'] + 1})\n"
            
            # 添加被其他文件引用的信息
            referencing_files = var_info['referencing_files']
            if referencing_files:
                summary += f"    被以下文件引用 ({len(referencing_files)}个):\n"
                for ref_file in referencing_files:
                    summary += f"      - {ref_file}\n"

        summary += "\n函数调用关系:\n"
        
        for func_name in result.functions:
            outgoing = result.outgoing_calls.get(func_name, [])
            incoming = result.incoming_calls.get(func_name, [])
            
            summary += f"\n  {func_name}:\n"
            if outgoing:
                summary += "    调用:\n"
                for call in outgoing:
                    summary += f"      - {call['name']} (在 {call['file_path']})\n"
            if incoming:
                summary += "    被调用:\n"
                for call in incoming:
                    summary += f"      - 被 {call['name']} 调用 (在 {call['file_path']})\n"
        
        return summary


# 使用示例
if __name__ == "__main__":
    analyzer = FileAnalyzer("http://localhost:6789")
    
    # 分析单个文件
    result = analyzer.analyze_file("F:/github/xiaozhi-esp32/main/audio/wake_words/afe_wake_word.cc")
    if result:
        print(analyzer.generate_file_summary(result))
