import json
import os
import networkx as nx
from typing import Dict, List, Set, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import sys
import hashlib

# 添加相对路径以导入分析模块
sys.path.append(os.path.join(os.path.dirname(__file__), '../../context'))

# 导入图搜索器
from graph_searcher import GraphSearcher, NodeType, EdgeType

try:
    from fileanalyze import FileAnalyzer, FileAnalysisResult
    from folderanalyze import FolderAnalyzer, FolderAnalysisResult
except ImportError:
    print("Warning: Could not import fileanalyze or folderanalyzer modules")

@dataclass
class GraphNode:
    """图节点数据结构"""
    node_id: str
    node_type: NodeType
    name: str
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    encoding: Optional[Dict[str, Any]] = None

@dataclass
class GraphEdge:
    """图边数据结构"""
    source: str
    target: str
    edge_type: EdgeType
    metadata: Optional[Dict[str, Any]] = None

class GraphConstructor:
    """图构造器类，用于构建和管理代码分析图"""
    
    def __init__(self, base_path: str = None, id_strategy: str = "relative", exclude_declarations: bool = True):
        """
        初始化图构造器
        
        Args:
            base_path: 项目基础路径，用于计算相对路径
            id_strategy: ID生成策略，可选值：
                - "relative": 使用相对路径（推荐，默认）
                - "smart": 智能简化路径
                - "hash": 使用哈希值（最简洁）
                - "absolute": 使用绝对路径（原始方法）
            exclude_declarations: 是否排除只有声明没有实现的函数节点（默认True）
        """
        self.graph = nx.DiGraph()  # 使用有向图
        self.file_analyzer = None
        self.folder_analyzer = None
        
        # ID生成策略配置
        self.base_path = base_path or os.getcwd()
        self.id_strategy = id_strategy
        
        # 控制是否排除函数声明
        self.exclude_declarations = exclude_declarations
        
        # 函数体数据缓存
        self.function_bodies = {}
        
        # 初始化图搜索器
        self.searcher = GraphSearcher(self.graph)
        
        print(f"GraphConstructor initialized with ID strategy: {id_strategy}")
        if id_strategy == "relative":
            print(f"Base path: {self.base_path}")
        if exclude_declarations:
            print("Function declarations without body will be excluded from graph")
    
    def load_function_bodies(self, functions_bodies_file: str):
        """
        从functions_bodys.jsonl文件加载函数体数据
        
        Args:
            functions_bodies_file: functions_bodys.jsonl文件路径
        """
        self.function_bodies = {}
        if not os.path.exists(functions_bodies_file):
            print(f"Warning: Function bodies file not found: {functions_bodies_file}")
            return
        
        try:
            with open(functions_bodies_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        filepath = data.get('filepath', '')
                        symbol_name = data.get('symbolName', '')
                        function_body = data.get('functionBody', '')
                        
                        if filepath and symbol_name:
                            # 使用相对路径作为键，确保与graph_constructor的ID生成策略一致
                            rel_path = self._get_relative_path(filepath)
                            func_key = f"{rel_path}:{symbol_name}"
                            self.function_bodies[func_key] = function_body
                    except json.JSONDecodeError as e:
                        print(f"Warning: Failed to parse line in function bodies file: {e}")
            
            print(f"Loaded {len(self.function_bodies)} function bodies from {functions_bodies_file}")
        except Exception as e:
            print(f"Error loading function bodies from {functions_bodies_file}: {e}")
    
    def _get_function_body(self, file_path: str, function_name: str) -> Optional[str]:
        """
        获取函数体
        
        Args:
            file_path: 文件路径
            function_name: 函数名
            
        Returns:
            函数体字符串，如果未找到则返回None
        """
        rel_path = self._get_relative_path(file_path)
        func_key = f"{rel_path}:{function_name}"
        return self.function_bodies.get(func_key)
    
    def _is_function_declaration_only(self, function_body: str) -> bool:
        """
        判断函数是否只是声明（没有实际实现）
        
        Args:
            function_body: 函数体字符串
            
        Returns:
            True如果只是声明，False如果有实现
        """
        if not function_body:
            return True
        
        # 去除空白字符
        body = function_body.strip()
        
        # 如果为空字符串
        if not body:
            return True
        
        # 常见的函数声明模式
        declaration_patterns = [
            ';',  # C/C++函数声明以分号结尾
            '= 0;',  # 纯虚函数
            '= delete;',  # 删除的函数
            '= default;',  # 默认函数
        ]
        
        # 检查是否只是以声明模式结尾
        for pattern in declaration_patterns:
            if body.endswith(pattern):
                return True
        
        # 检查是否只包含很少的内容（可能是空实现或注释）
        # 移除注释和空行
        lines = [line.strip() for line in body.split('\n') if line.strip()]
        non_comment_lines = [line for line in lines if not line.startswith('//') and not line.startswith('/*') and not line.startswith('*')]
        
        # 如果没有非注释行，或者只有很少的实际代码
        if len(non_comment_lines) <= 1:
            # 检查是否只有简单的返回语句或空语句
            if not non_comment_lines:
                return True
            
            single_line = non_comment_lines[0]
            simple_patterns = [
                '{',  # 只有开始括号
                '}',  # 只有结束括号
                '{}',  # 空函数体
                'return;',  # 空返回
                'return 0;',  # 简单返回
                'return nullptr;',  # 空指针返回
                'return NULL;',  # NULL返回
            ]
            
            if single_line in simple_patterns or single_line.startswith('return ') and single_line.endswith(';'):
                return True
        
        return False
    
    def set_analyzers(self, base_url: str = "http://localhost:6789"):
        """设置分析器"""
        try:
            self.file_analyzer = FileAnalyzer(base_url)
            self.folder_analyzer = FolderAnalyzer(self.file_analyzer)
        except NameError:
            print("Error: FileAnalyzer or FolderAnalyzer not available")
    
    def _normalize_path(self, path: str) -> str:
        """标准化路径，统一使用正斜杠"""
        return os.path.normpath(path).replace('\\', '/')
    
    def _get_relative_path(self, file_path: str) -> str:
        """获取相对于base_path的相对路径"""
        try:
            rel_path = os.path.relpath(file_path, self.base_path)
            return self._normalize_path(rel_path)
        except ValueError:
            # 如果无法计算相对路径（比如在不同驱动器），返回文件名
            return os.path.basename(file_path)
    
    def _generate_hash_id(self, content: str) -> str:
        """生成基于内容的短哈希ID"""
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _generate_node_id(self, node_type: NodeType, name: str, file_path: str = "") -> str:
        """生成唯一的节点ID - 支持多种策略"""
        
        # 对函数名进行标准化处理
        if node_type == NodeType.FUNCTION:
            name = self._normalize_function_signature(name)
        
        if self.id_strategy == "relative":
            # 方案1: 使用相对路径（推荐）
            if node_type == NodeType.FILE:
                rel_path = self._get_relative_path(name)
                return f"file:{rel_path}"
            elif node_type == NodeType.FOLDER:
                rel_path = self._get_relative_path(name)
                return f"folder:{rel_path}"
            elif node_type == NodeType.FUNCTION:
                rel_path = self._get_relative_path(file_path)
                return f"func:{rel_path}:{name}"
            elif node_type == NodeType.GLOBAL_VARIABLE:
                rel_path = self._get_relative_path(file_path)
                return f"var:{rel_path}:{name}"
            elif node_type == NodeType.STRUCT:
                rel_path = self._get_relative_path(file_path)
                return f"struct:{rel_path}:{name}"
            elif node_type == NodeType.CLASS:
                rel_path = self._get_relative_path(file_path)
                return f"class:{rel_path}:{name}"
            elif node_type == NodeType.FIELD:
                rel_path = self._get_relative_path(file_path)
                return f"field:{rel_path}:{name}"
                
        elif self.id_strategy == "hash":
            # 方案2: 使用哈希值，简短但不可读
            if node_type == NodeType.FILE:
                content = f"file:{self._normalize_path(name)}"
                return f"f_{self._generate_hash_id(content)}"
            elif node_type == NodeType.FOLDER:
                content = f"folder:{self._normalize_path(name)}"
                return f"d_{self._generate_hash_id(content)}"
            elif node_type == NodeType.FUNCTION:
                content = f"func:{self._normalize_path(file_path)}:{name}"
                return f"fn_{self._generate_hash_id(content)}"
            elif node_type == NodeType.GLOBAL_VARIABLE:
                content = f"var:{self._normalize_path(file_path)}:{name}"
                return f"v_{self._generate_hash_id(content)}"
                
        elif self.id_strategy == "smart":
            # 方案3: 智能简化，使用文件名和必要的路径信息
            if node_type == NodeType.FILE:
                filename = os.path.basename(name)
                parent_dir = os.path.basename(os.path.dirname(name))
                if parent_dir and parent_dir not in [".", ""]:
                    return f"file:{parent_dir}/{filename}"
                return f"file:{filename}"
            elif node_type == NodeType.FOLDER:
                folder_name = os.path.basename(name)
                return f"folder:{folder_name}"
            elif node_type == NodeType.FUNCTION:
                filename = os.path.basename(file_path)
                # 清理函数名中的一些特殊字符以提高可读性
                clean_name = name.replace("const ", "").replace("&", "ref").replace("*", "ptr")
                return f"func:{filename}:{clean_name}"
            elif node_type == NodeType.GLOBAL_VARIABLE:
                filename = os.path.basename(file_path)
                return f"var:{filename}:{name}"
                
        else:  # "absolute" - 原始方法
            if node_type == NodeType.FILE:
                return f"file:{self._normalize_path(name)}"
            elif node_type == NodeType.FOLDER:
                return f"folder:{self._normalize_path(name)}"
            elif node_type == NodeType.FUNCTION:
                return f"func:{self._normalize_path(file_path)}:{name}"
            elif node_type == NodeType.GLOBAL_VARIABLE:
                return f"var:{self._normalize_path(file_path)}:{name}"
        
        # 默认情况
        return f"{node_type.value}:{name}"
    
    def add_node(self, node: GraphNode):
        """添加节点到图中"""
        # 初始化encoding字段，包含what、how、embedding三个部分，初始值为null
        default_encoding = {
            'what': None,
            'how': None,
            'embedding': None
        }
        
        self.graph.add_node(
            node.node_id,
            node_type=node.node_type.value,
            name=node.name,
            file_path=node.file_path,
            metadata=node.metadata or {},
            encoding=node.encoding or default_encoding
        )
    
    def add_edge(self, edge: GraphEdge):
        """添加边到图中"""
        self.graph.add_edge(
            edge.source,
            edge.target,
            edge_type=edge.edge_type.value,
            metadata=edge.metadata or {}
        )
    
    def _analyze_function_variable_usage(self, function_body: str, global_variables: List[str]) -> List[str]:
        """
        分析函数体中使用的全局变量
        
        Args:
            function_body: 函数体代码
            global_variables: 文件中的全局变量列表
            
        Returns:
            函数中使用的全局变量列表
        """
        if not function_body:
            return []
        
        used_variables = []
        
        # 简单的词法分析，查找变量使用
        for var_name in global_variables:
            # 使用正则表达式查找变量使用
            # 这里使用简单的方法，可以根据需要改进
            import re
            
            # 匹配变量名，确保它不是其他标识符的一部分
            pattern = r'\b' + re.escape(var_name) + r'\b'
            if re.search(pattern, function_body):
                used_variables.append(var_name)
        
        return used_variables

    def get_node_type_by_value(self, value: str) -> NodeType:
        """根据值获取NodeType"""
        try:
            return NodeType(value)
        except ValueError:
            raise ValueError(f"Invalid NodeType value: {value}")

    def get_node_type_by_name(self, name: str) -> NodeType:
        """根据名称获取NodeType"""
        try:
            return NodeType[name.upper()]
        except KeyError:
            raise ValueError(f"Invalid NodeType name: {name}")

    def build_graph_from_file_analysis(self, result):
        """从单个文件分析结果构建图
        
        Args:
            result: FileAnalysisResult对象
        """
        file_path = result.file_path
        file_id = self._generate_node_id(NodeType.FILE, file_path)
        
        # 预先计算要添加的函数数量（如果启用了排除声明选项）
        actual_functions_count = len(result.functions)
        if self.exclude_declarations:
            actual_functions_count = 0
            for func_name in result.functions:
                function_body = self._get_function_body(file_path, func_name)
                if not self._is_function_declaration_only(function_body):
                    actual_functions_count += 1
        
        # 添加文件节点
        file_node = GraphNode(
            node_id=file_id,
            node_type=NodeType.FILE,
            name=os.path.basename(file_path),
            file_path=file_path,
            metadata={
                'full_path': file_path,
                'functions_count': actual_functions_count,  # 使用实际添加的函数数量
                'total_functions_detected': len(result.functions),  # 保留原始检测到的函数总数
                'variables_count': len(result.global_variables),
                'symbols_count': len(result.all_symbols) if hasattr(result, 'all_symbols') else 0,
                'body': None  # 文件节点body为null
            }
        )
        self.add_node(file_node)

        # 添加struct
        for struct_name, struct_analysis in result.struct_analysis.items():
            struct_id = self._generate_node_id(NodeType.STRUCT, struct_name, file_path)
            struct_node = GraphNode(
                node_id=struct_id,
                node_type=NodeType.STRUCT,
                name=struct_name,
                file_path=file_path,
                metadata={
                    'fields': struct_analysis.get('fields'),
                    'references': struct_analysis.get('references'),
                }
            )
            self.add_node(struct_node)
            for field in struct_analysis.get('fields', []):
                field_id = self._generate_node_id(NodeType.FIELD, field["name"], file_path)
                field_node = GraphNode(
                    node_id=field_id,
                    node_type=NodeType.FIELD,
                    name=field["name"],
                    file_path=file_path,
                )
                self.add_node(field_node)
            for ref in struct_analysis.get('references', []):
                if len(ref['symbol']) == 0:
                    continue
                print(ref)
                targetName = ref["symbol"][0]["symbolName"]
                targetType = ref["symbol"][0]["type"]
                if targetType == "Variable":
                    targetType = "global_variable"
                target_id = self._generate_node_id(self.get_node_type_by_value(targetType.lower()), targetName, ref['uri']["fsPath"])
                print(target_id)
                ref_edge = GraphEdge(
                    source=struct_id,
                    target=target_id,
                    edge_type=EdgeType.CLASS_AND_INSTANCE
                )
                print(ref_edge)
                self.add_edge(ref_edge)

        # 添加全局变量节点和关系（先添加变量节点）
        for var_name in result.global_variables:
            var_analysis = result.global_var_analysis.get(var_name, {})
            
            # 检查变量是否在本文件中定义
            definition_info = var_analysis.get('definition', '')
            if isinstance(definition_info, dict):
                def_file_path = definition_info.get('file_path', '')
            else:
                def_file_path = ''
            if def_file_path != file_path:
                continue

            var_id = self._generate_node_id(NodeType.GLOBAL_VARIABLE, var_name, file_path)
            
            var_node = GraphNode(
                node_id=var_id,
                node_type=NodeType.GLOBAL_VARIABLE,
                name=var_name,
                file_path=file_path,
                metadata={
                    'definition': var_analysis.get('definition'),
                    'references_count': len(var_analysis.get('references', [])),
                    'referencing_files_count': len(var_analysis.get('referencing_files', [])),
                    'body': None  # 全局变量节点body为null
                }
            )
            self.add_node(var_node)
            
            # 文件包含变量的关系
            contains_edge = GraphEdge(
                source=file_id,
                target=var_id,
                edge_type=EdgeType.CONTAINS_VARIABLE
            )
            self.add_edge(contains_edge)
            
            # 变量引用关系（跨文件）
            for ref_info in var_analysis.get('references', []):
                ref_file_path = ref_info.get('file_path', '')
                if ref_file_path and ref_file_path != file_path:
                    ref_file_id = self._generate_node_id(NodeType.FILE, ref_file_path)
                    ref_edge = GraphEdge(
                        source=ref_file_id,
                        target=var_id,
                        edge_type=EdgeType.VARIABLE_REFERENCES,
                        metadata={
                            'reference_range': ref_info.get('range', [])
                        }
                    )
                    self.add_edge(ref_edge)
        
        # 添加函数节点和关系
        functions_added = 0
        functions_skipped = 0
        
        for func_name in result.functions:
            func_id = self._generate_node_id(NodeType.FUNCTION, func_name, file_path)
            
            # 获取函数体
            function_body = self._get_function_body(file_path, func_name)
            
            # 如果启用了排除声明选项且函数只是声明，跳过
            if self.exclude_declarations and self._is_function_declaration_only(function_body):
                functions_skipped += 1
                continue
            
            func_node = GraphNode(
                node_id=func_id,
                node_type=NodeType.FUNCTION,
                name=func_name,
                file_path=file_path,
                metadata={
                    'outgoing_calls_count': len(result.outgoing_calls.get(func_name, [])),
                    'incoming_calls_count': len(result.incoming_calls.get(func_name, [])),
                    'body': function_body,  # 添加函数体
                    'is_declaration_only': self._is_function_declaration_only(function_body)
                }
            )
            self.add_node(func_node)
            functions_added += 1
            
            # 文件包含函数的关系
            contains_edge = GraphEdge(
                source=file_id,
                target=func_id,
                edge_type=EdgeType.CONTAINS_FUNCTION
            )
            self.add_edge(contains_edge)
            
            # 分析函数体中的变量使用并添加边
            if function_body:
                used_variables = self._analyze_function_variable_usage(function_body, result.global_variables)
                for var_name in used_variables:
                    var_analysis = result.global_var_analysis.get(var_name, {})
                    if isinstance(definition_info, dict):
                        def_file_path = definition_info.get('file_path', '')
                    else:
                        def_file_path = ''
                    var_id = self._generate_node_id(NodeType.GLOBAL_VARIABLE, var_name, def_file_path)
                    # 添加函数使用变量的边
                    uses_edge = GraphEdge(
                        source=func_id,
                        target=var_id,
                        edge_type=EdgeType.FUNCTION_USES_VARIABLE,
                        metadata={
                            'variable_name': var_name,
                            'detected_by': 'function_body_analysis'
                        }
                    )
                    self.add_edge(uses_edge)
            
            # 函数调用关系（outgoing calls）
            for call_info in result.outgoing_calls.get(func_name, []):
                target_func_name = call_info.get('name', '')
                target_file_path = call_info.get('file_path', '')
                if target_func_name and target_file_path:
                    target_func_id = self._generate_node_id(NodeType.FUNCTION, target_func_name, target_file_path)
                    call_edge = GraphEdge(
                        source=func_id,
                        target=target_func_id,
                        edge_type=EdgeType.FUNCTION_CALLS,
                        metadata={
                            'call_ranges': call_info.get('call_ranges', []),
                            'target_range': call_info.get('range', [])
                        }
                    )
                    self.add_edge(call_edge)
            
            # 函数被调用关系（incoming calls）
            for call_info in result.incoming_calls.get(func_name, []):
                source_func_name = call_info.get('name', '')
                source_file_path = call_info.get('file_path', '')
                if source_func_name and source_file_path:
                    source_func_id = self._generate_node_id(NodeType.FUNCTION, source_func_name, source_file_path)
                    incoming_edge = GraphEdge(
                        source=source_func_id,
                        target=func_id,
                        edge_type=EdgeType.FUNCTION_INCOMING,
                        metadata={
                            'call_ranges': call_info.get('call_ranges', []),
                            'source_range': call_info.get('range', [])
                        }
                    )
                    self.add_edge(incoming_edge)
        
        # 输出函数处理统计信息
        if self.exclude_declarations and functions_skipped > 0:
            rel_path = self._get_relative_path(file_path)
            print(f"  📄 {rel_path}: 添加了 {functions_added} 个函数节点，跳过了 {functions_skipped} 个函数声明")

        # 添加class,并添加class 和 class method的关系
        for class_name, members in result.class_members.items():
            class_id = self._generate_node_id(NodeType.CLASS, class_name, file_path)
            class_node = GraphNode(
                node_id=class_id,
                node_type=NodeType.CLASS,
                name=class_name,
                file_path=file_path,
                metadata={
                    'members': members,
                }
            )
            self.add_node(class_node)
            for member in members:
                if member.get('type') == 'Field':
                    field_id = self._generate_node_id(NodeType.FIELD, member.get('name'), file_path)
                    field_node =  GraphNode(
                        node_id=field_id,
                        node_type=NodeType.FIELD,
                        name=member.get('name'),
                        file_path=file_path,
                        metadata={
                            'type': member.get('type'),
                        }
                    )
                    self.add_node(field_node)
                if member.get('type') == 'Method':
                    func_id = self._generate_node_id(NodeType.FUNCTION, member.get('name'), file_path)
                    contain_edge = GraphEdge(
                        source = class_id,
                        target = func_id,
                        edge_type = EdgeType.CLASS_CONTAINS_METHOD
                    )
                    self.add_edge(contain_edge)
        for class_name, references in result.class_references.items():
            class_id = self._generate_node_id(NodeType.CLASS, class_name, file_path)
            for ref in references:
                targetName = ref["symbol"][0]["symbolName"]
                targetType = ref["symbol"][0]["type"]
                target_id = self._generate_node_id(NodeType[targetType.lower()], targetName, ref['uri']["path"])
                ref_edge = GraphEdge(
                    source=class_id,
                    target=target_id,
                    edge_type=EdgeType.CLASS_AND_INSTANCE
                )
                self.add_edge(ref_edge)

        
        # 添加文件引用关系
        for ref_file_path in result.referenced_files:
            ref_file_id = self._generate_node_id(NodeType.FILE, ref_file_path)
            ref_edge = GraphEdge(
                source=file_id,
                target=ref_file_id,
                edge_type=EdgeType.FILE_REFERENCES
            )
            self.add_edge(ref_edge)
        
        # 添加被引用关系
        for ref_file_path in result.referencing_files:
            ref_file_id = self._generate_node_id(NodeType.FILE, ref_file_path)
            ref_edge = GraphEdge(
                source=ref_file_id,
                target=file_id,
                edge_type=EdgeType.FILE_REFERENCES
            )
            self.add_edge(ref_edge)
    
    def build_graph_from_folder_analysis(self, result):
        """从文件夹分析结果构建图
        
        Args:
            result: FolderAnalysisResult对象
        """
        folder_path = result.folder_path
        folder_id = self._generate_node_id(NodeType.FOLDER, folder_path)
        
        # 添加文件夹节点
        folder_node = GraphNode(
            node_id=folder_id,
            node_type=NodeType.FOLDER,
            name=os.path.basename(folder_path),
            file_path=folder_path,
            metadata={
                'full_path': folder_path,
                'files_count': len(result.files_analyzed),
                'referenced_folders_count': len(result.referenced_folders),
                'referencing_folders_count': len(result.referencing_folders),
                'body': None  # 文件夹节点body为null
            }
        )
        self.add_node(folder_node)
        
        # 为每个文件构建图
        for file_path, file_result in result.file_analysis_results.items():
            self.build_graph_from_file_analysis(file_result)
            
            # 添加文件夹包含文件的关系
            file_id = self._generate_node_id(NodeType.FILE, file_path)
            contains_edge = GraphEdge(
                source=folder_id,
                target=file_id,
                edge_type=EdgeType.FOLDER_CONTAINS
            )
            self.add_edge(contains_edge)
        
        # 添加文件夹间的引用关系
        for ref_folder_path in result.referenced_folders:
            ref_folder_id = self._generate_node_id(NodeType.FOLDER, ref_folder_path)
            ref_edge = GraphEdge(
                source=folder_id,
                target=ref_folder_id,
                edge_type=EdgeType.FILE_REFERENCES
            )
            self.add_edge(ref_edge)
    
    def analyze_and_build_file_graph(self, file_path: str, use_cache: bool = True, cache_dir: str = None) -> bool:
        """分析单个文件并构建图"""
        if not self.file_analyzer:
            self.set_analyzers()
        
        if not self.file_analyzer:
            print("Error: FileAnalyzer not available")
            return False
        
        result = self.file_analyzer.analyze_file(file_path, use_cache, cache_dir)
        if result:
            self.build_graph_from_file_analysis(result)
            return True
        return False
    
    def analyze_and_build_folder_graph(self, folder_path: str, use_cache: bool = True, cache_dir: str = None) -> bool:
        """分析文件夹并构建图"""
        if not self.folder_analyzer:
            self.set_analyzers()
        
        if not self.folder_analyzer:
            print("Error: FolderAnalyzer not available")
            return False
        
        result = self.folder_analyzer.analyze_folder(folder_path, use_cache, cache_dir)
        self.build_graph_from_folder_analysis(result)
        return True
    
    def analyze_and_build_folder_graph_recursive(self, root_folder_path: str, 
                                                use_cache: bool = True, 
                                                cache_dir: str = None,
                                                file_extensions: List[str] = None,
                                                exclude_patterns: List[str] = None,
                                                max_depth: int = None) -> bool:
        """
        递归分析文件夹及其所有子文件夹并构建图
        
        Args:
            root_folder_path: 根文件夹路径
            use_cache: 是否使用缓存
            cache_dir: 缓存目录
            file_extensions: 要分析的文件扩展名列表，例如 ['.py', '.cpp', '.h']
            exclude_patterns: 要排除的文件夹/文件模式列表，例如 ['__pycache__', '.git', 'node_modules']
            max_depth: 最大递归深度，None表示不限制
            
        Returns:
            是否成功构建图
        """
        if not self.file_analyzer:
            self.set_analyzers()
        
        if not self.file_analyzer:
            print("Error: FileAnalyzer not available")
            return False
        
        # 默认配置
        if file_extensions is None:
            file_extensions = ['.py', '.cpp', '.c', '.h', '.hpp', '.cc', '.cxx', '.js', '.ts']
        
        if exclude_patterns is None:
            exclude_patterns = [
                '__pycache__', '.git', '.svn', '.hg',
                'node_modules', '.vscode', '.idea',
                'build', 'dist', '.pytest_cache',
                '.mypy_cache', '.tox', 'venv', 'env'
            ]
        
        print(f"🚀 开始递归分析文件夹: {root_folder_path}")
        print(f"📁 文件扩展名: {file_extensions}")
        print(f"🚫 排除模式: {exclude_patterns}")
        if max_depth is not None:
            print(f"📏 最大深度: {max_depth}")
        print()
        
        # 统计信息
        analyzed_folders = []
        analyzed_files = []
        skipped_folders = []
        
        def should_exclude(path: str) -> bool:
            """检查路径是否应该被排除"""
            path_name = path
            for pattern in exclude_patterns:
                if pattern in path_name or path_name.startswith('.'):
                    return True
            return False
        
        def has_valid_extension(file_path: str) -> bool:
            """检查文件是否有有效的扩展名"""
            _, ext = os.path.splitext(file_path)
            return ext.lower() in [e.lower() for e in file_extensions]
        
        def analyze_folder_recursive(folder_path: str, current_depth: int = 0) -> bool:
            """递归分析文件夹的内部函数"""
            
            # 检查深度限制
            if max_depth is not None and current_depth > max_depth:
                return True
            
            # 检查是否应该排除此文件夹
            if should_exclude(folder_path):
                skipped_folders.append(folder_path)
                return True
            
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                print(f"⚠️  跳过不存在或非文件夹的路径: {folder_path}")
                return True
            
            print(f"{'  ' * current_depth}📁 分析文件夹: {os.path.basename(folder_path)} (深度 {current_depth})")
            analyzed_folders.append(folder_path)
            
            # 创建文件夹节点
            folder_id = self._generate_node_id(NodeType.FOLDER, folder_path)
            
            # 获取文件夹中的文件和子文件夹
            folder_files = []
            subfolders = []
            
            try:
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    
                    if os.path.isfile(item_path):
                        if has_valid_extension(item_path):
                            folder_files.append(item_path)
                    elif os.path.isdir(item_path):
                        if not should_exclude(item_path):
                            subfolders.append(item_path)
            except PermissionError:
                print(f"⚠️  权限不足，跳过文件夹: {folder_path}")
                return True
            
            # 创建并添加文件夹节点
            folder_node = GraphNode(
                node_id=folder_id,
                node_type=NodeType.FOLDER,
                name=os.path.basename(folder_path),
                file_path=folder_path,
                metadata={
                    'full_path': folder_path,
                    'files_count': len(folder_files),
                    'subfolders_count': len(subfolders),
                    'depth': current_depth,
                    'body': None  # 文件夹节点body为null
                }
            )
            self.add_node(folder_node)
            
            # 分析文件夹中的每个文件
            files_analyzed = 0
            for file_path in folder_files:
                try:
                    result = self.file_analyzer.analyze_file(file_path, use_cache, cache_dir)
                    if result:
                        self.build_graph_from_file_analysis(result)
                        analyzed_files.append(file_path)
                        files_analyzed += 1
                        print(f"成功分析了{folder_path}下的 {files_analyzed}/{len(folder_files)} 个文件")
                        
                        # 添加文件夹包含文件的关系
                        file_id = self._generate_node_id(NodeType.FILE, file_path)
                        contains_edge = GraphEdge(
                            source=folder_id,
                            target=file_id,
                            edge_type=EdgeType.FOLDER_CONTAINS
                        )
                        self.add_edge(contains_edge)
                            
                except Exception as e:
                    print(f"⚠️  分析文件失败 {file_path}: {e}")
            
            print(f"{'  ' * current_depth}   ✅ 成功分析 {files_analyzed}/{len(folder_files)} 个文件")
            
            # 递归分析子文件夹
            for subfolder_path in subfolders:
                analyze_folder_recursive(subfolder_path, current_depth + 1)
                
                # 添加文件夹包含子文件夹的关系
                subfolder_id = self._generate_node_id(NodeType.FOLDER, subfolder_path)
                contains_edge = GraphEdge(
                    source=folder_id,
                    target=subfolder_id,
                    edge_type=EdgeType.FOLDER_CONTAINS
                )
                self.add_edge(contains_edge)
            
            return True
        
        # 开始递归分析
        success = analyze_folder_recursive(root_folder_path, 0)
        
        # 输出统计信息
        print(f"\n📊 递归分析完成:")
        print(f"  ✅ 分析的文件夹: {len(analyzed_folders)}")
        print(f"  ✅ 分析的文件: {len(analyzed_files)}")
        print(f"  🚫 跳过的文件夹: {len(skipped_folders)}")
        
        if analyzed_folders:
            print(f"\n📁 分析的文件夹列表:")
            for i, folder in enumerate(analyzed_folders[:10]):  # 只显示前10个
                rel_path = self._get_relative_path(folder)
                print(f"  {i+1}. {rel_path}")
            if len(analyzed_folders) > 10:
                print(f"  ... 还有 {len(analyzed_folders) - 10} 个文件夹")
        
        if skipped_folders:
            print(f"\n🚫 跳过的文件夹示例:")
            for i, folder in enumerate(skipped_folders[:5]):  # 只显示前5个
                rel_path = self._get_relative_path(folder)
                print(f"  {i+1}. {rel_path}")
            if len(skipped_folders) > 5:
                print(f"  ... 还有 {len(skipped_folders) - 5} 个文件夹")
        
        return success
    
    def save_graph_to_json(self, output_file: str, include_metadata: bool = True):
        """将图保存为JSON文件"""
        return self.searcher.save_graph_to_json(output_file, include_metadata)
    
    def load_graph_from_json(self, input_file: str) -> bool:
        """从JSON文件加载图"""
        # 使用searcher加载图，然后更新本地引用
        success = self.searcher.load_graph_from_json(input_file)
        if success:
            # 确保graph引用保持同步
            self.graph = self.searcher.graph
        return success
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """获取图的统计信息"""
        return self.searcher.get_graph_statistics()
    
    def find_nodes_by_type(self, node_type: NodeType) -> List[str]:
        """根据类型查找节点"""
        return self.searcher.find_nodes_by_type(node_type)
    
    def find_nodes_by_file(self, file_path: str) -> List[str]:
        """查找属于特定文件的所有节点"""
        return self.searcher.find_nodes_by_file(file_path)
    
    def get_function_call_chain(self, start_function_id: str, max_depth: int = 5) -> List[List[str]]:
        """获取函数调用链"""
        return self.searcher.get_function_call_chain(start_function_id, max_depth)
    
    def export_to_networkx_format(self, output_file: str):
        """导出为NetworkX兼容的格式（用于其他工具分析）"""
        return self.searcher.export_to_networkx_format(output_file)

    def _normalize_function_signature(self, func_name: str) -> str:
        """
        标准化函数签名，移除参数名，只保留类型信息
        
        Args:
            func_name: 原始函数名（可能包含参数名）
            
        Returns:
            标准化后的函数签名
        """
        import re
        
        # 如果没有括号，直接返回
        if '(' not in func_name:
            return func_name
        
        # 分离函数名和参数部分
        match = re.match(r'^([^(]+)\((.*)\)$', func_name)
        if not match:
            return func_name
        
        base_name = match.group(1).strip()
        params_str = match.group(2).strip()
        
        if not params_str:
            return f"{base_name}()"
        
        # 处理参数列表
        normalized_params = []
        
        # 分割参数，考虑模板和嵌套类型
        params = self._split_function_parameters(params_str)
        
        for param in params:
            param = param.strip()
            if not param:
                continue
            
            # 移除参数名，只保留类型
            # 处理各种C++类型模式
            normalized_param = self._extract_parameter_type(param)
            if normalized_param:
                normalized_params.append(normalized_param)
        
        return f"{base_name}({', '.join(normalized_params)})"
    
    def _split_function_parameters(self, params_str: str) -> List[str]:
        """
        智能分割函数参数，考虑模板和嵌套类型
        
        Args:
            params_str: 参数字符串
            
        Returns:
            参数列表
        """
        params = []
        current_param = ""
        bracket_depth = 0
        angle_depth = 0
        
        for char in params_str:
            if char in '<(':
                if char == '<':
                    angle_depth += 1
                else:
                    bracket_depth += 1
                current_param += char
            elif char in '>)':
                if char == '>':
                    angle_depth -= 1
                else:
                    bracket_depth -= 1
                current_param += char
            elif char == ',' and bracket_depth == 0 and angle_depth == 0:
                if current_param.strip():
                    params.append(current_param.strip())
                current_param = ""
            else:
                current_param += char
        
        if current_param.strip():
            params.append(current_param.strip())
        
        return params
    
    def _extract_parameter_type(self, param: str) -> str:
        """
        从参数字符串中提取类型信息，移除参数名
        
        Args:
            param: 单个参数字符串
            
        Returns:
            标准化的参数类型
        """
        import re
        
        param = param.strip()
        
        # 处理常见的C++类型模式
        # 模式1: const Type& varName -> const Type&
        # 模式2: Type varName -> Type
        # 模式3: Type* varName -> Type*
        # 模式4: const Type* const varName -> const Type* const
        
        # 特殊处理：函数指针等复杂类型
        if '(' in param and ')' in param:
            # 可能是函数指针，保持原样
            return param
        
        # 移除默认值
        if '=' in param:
            param = param.split('=')[0].strip()
        
        # 查找最后一个可能的变量名
        # 从右往左找，跳过 &, *, const 等修饰符
        words = param.split()
        if len(words) <= 1:
            return param
        
        # 构建类型部分（除了最后一个词，它可能是变量名）
        potential_var_name = words[-1]
        type_part = ' '.join(words[:-1])
        
        # 检查最后一个词是否是类型修饰符而不是变量名
        type_modifiers = {'&', '*', 'const', 'volatile', 'mutable'}
        if (potential_var_name in type_modifiers or 
            potential_var_name.endswith('&') or 
            potential_var_name.endswith('*') or
            '<' in potential_var_name or
            '>' in potential_var_name):
            # 最后一个词也是类型的一部分
            return param
        
        # 检查是否是有效的标识符（变量名）
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', potential_var_name):
            # 是变量名，返回类型部分
            return type_part.strip()
        
        # 否则保持原样
        return param

def test_recursive_folder_analysis(test_folder, output_dir, file_extensions, exclude_patterns, base_path=None):
    """测试递归文件夹分析功能
    
    Args:
        test_folder: 测试文件夹路径
    """
    print("🔄 测试递归文件夹分析功能（含functions_bodys.jsonl生成）")
    print("="*80)
    
    # 设置项目基础路径
    if base_path is None:
        base_path = test_folder
    
    # 确认文件夹存在
    if not os.path.exists(test_folder):
        print(f"❌ 测试文件夹不存在: {test_folder}")
        return False
    
    # 输出路径配置
    functions_bodies_file = os.path.join(output_dir, "functions_bodys.jsonl")
    graph_output_file = os.path.join(output_dir, "code_graph_recursive.json")
    cache_dir = os.path.join(output_dir, "cache")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    print("📋 路径配置:")
    print(f"  测试文件夹: {test_folder}")
    print(f"  基础路径: {base_path}")
    print(f"  函数体文件: {functions_bodies_file}")
    print(f"  图输出文件: {graph_output_file}")
    print(f"  缓存目录: {cache_dir}")
    print()
    
    # 第一步：使用FileAnalyzer生成functions_bodys.jsonl
    print("🔍 第一步：生成functions_bodys.jsonl文件")
    print("-" * 50)
    
    try:
        # 初始化FileAnalyzer
        file_analyzer = FileAnalyzer("http://localhost:6789")
        
        # 扫描目录获取所有文件
        print("📂 扫描目录获取文件列表...")
        file_paths = file_analyzer.scan_directory_for_files(
            test_folder,
            file_extensions=file_extensions,
            exclude_patterns=exclude_patterns
        )
        
        print(f"📄 找到 {len(file_paths)} 个文件")
        for i, file_path in enumerate(file_paths[:10]):  # 显示前10个文件
            rel_path = file_analyzer._get_relative_path(file_path, base_path)
            print(f"  {i+1}. {rel_path}")
        if len(file_paths) > 10:
            print(f"  ... 还有 {len(file_paths) - 10} 个文件")
        print()
        
        # 生成functions_bodys.jsonl
        print("🔧 生成functions_bodys.jsonl文件...")
        success = file_analyzer.generate_functions_bodies_jsonl(
            file_paths=file_paths,
            output_file=functions_bodies_file,
            base_path=base_path
        )
        
        if not success:
            print("❌ 生成functions_bodys.jsonl失败")
            return False
        
        print("✅ functions_bodys.jsonl生成成功!")
        print()
        
    except Exception as e:
        print(f"❌ 生成functions_bodys.jsonl时出错: {e}")
        return False
    
    # 第二步：使用GraphConstructor构建图结构
    print("🏗️  第二步：构建图结构")
    print("-" * 50)
    
    try:
        # 初始化GraphConstructor（启用排除声明选项）
        constructor = GraphConstructor(base_path=base_path, id_strategy="relative", exclude_declarations=True)
        constructor.set_analyzers("http://localhost:6789")
        
        # 加载函数体数据
        print("📖 加载函数体数据...")
        constructor.load_function_bodies(functions_bodies_file)
        
        # 执行递归分析
        print("🔄 执行递归图构建...")
        success = constructor.analyze_and_build_folder_graph_recursive(
            root_folder_path=test_folder,
            use_cache=True,
            cache_dir=cache_dir,
            file_extensions=file_extensions,  # 指定要分析的文件类型
            exclude_patterns=exclude_patterns,  # 排除模式
            max_depth=5  # 最大递归深度
        )
        
        if not success:
            print("❌ 递归文件夹分析失败")
            return False
        
        print("✅ 递归文件夹分析成功!")
        
        # 保存图
        print("💾 保存图结构...")
        constructor.save_graph_to_json(graph_output_file)
        
        # 获取统计信息
        stats = constructor.get_graph_statistics()
        print(f"\n📊 图结构统计信息:")
        print(f"  总节点数: {stats['total_nodes']}")
        print(f"  总边数: {stats['total_edges']}")
        print(f"  文件节点: {stats.get('files', 0)}")
        print(f"  函数节点: {stats.get('functions', 0)}")
        print(f"  变量节点: {stats.get('variables', 0)}")
        print(f"  文件夹节点: {stats.get('folders', 0)}")
        
        # 显示文件夹层次结构
        print(f"\n📁 文件夹层次结构:")
        folder_nodes = constructor.find_nodes_by_type(NodeType.FOLDER)
        for folder_id in folder_nodes:
            node_data = constructor.graph.nodes[folder_id]
            metadata = node_data.get('metadata', {})
            depth = metadata.get('depth', 0)
            name = node_data.get('name', 'Unknown')
            files_count = metadata.get('files_count', 0)
            subfolders_count = metadata.get('subfolders_count', 0)
            print(f"  {'  ' * depth}📁 {name} ({files_count} 文件, {subfolders_count} 子文件夹)")
        
        # 显示带body的函数节点示例
        print(f"\n🔍 函数体示例 (前5个):")
        function_nodes = constructor.find_nodes_by_type(NodeType.FUNCTION)
        count = 0
        for func_id in function_nodes:
            if count >= 5:
                break
            node_data = constructor.graph.nodes[func_id]
            function_name = node_data.get('name', 'Unknown')
            file_path = node_data.get('file_path', '')
            body = node_data.get('metadata', {}).get('body')
            rel_file_path = constructor._get_relative_path(file_path)
            
            if body:
                body_preview = body[:100] + "..." if len(body) > 100 else body
                print(f"  ✅ {function_name} in {rel_file_path}")
                print(f"      Body: {body_preview}")
            else:
                print(f"  ⚠️  {function_name} in {rel_file_path} (no body)")
            count += 1
        
        # 测试图加载功能
        print(f"\n🔄 测试图加载功能...")
        new_constructor = GraphConstructor(base_path=base_path, id_strategy="relative")
        if new_constructor.load_graph_from_json(graph_output_file):
            new_stats = new_constructor.get_graph_statistics()
            print(f"✅ 图加载成功，统计信息匹配: {stats == new_stats}")
        else:
            print(f"❌ 图加载失败")
        
        print(f"\n🎉 完整测试流程成功完成!")
        print(f"📄 函数体文件: {functions_bodies_file}")
        print(f"📄 图结构文件: {graph_output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 构建图结构时出错: {e}")
        return False

if __name__ == "__main__":
    # 测试递归文件夹分析
    print("\n4️⃣ 测试递归文件夹分析")
    # test_folder = "D:/Download/github/xiaozhi-esp32s3_box/xiaozhi-esp32s3_box"
    # output_folder = "D:/Download/github/evox-ai/evox-server/.rag/xiaozhi/box"
    # test_folder = "D:/Download/github/xiaozhi-esp32/managed_components/78__esp-wifi-connect"
    test_folder = "F:/github/xiaozhi-esp32/main/audio"
    output_folder = "D:/Download/github/evox-ai/evox-server/.rag/xiaozhi/audio"
    test_recursive_folder_analysis(test_folder = test_folder, output_dir = output_folder, file_extensions=['.cc', '.c', '.h'], exclude_patterns=['__pycache__', '.git', 'node_modules', '.vscode', '.git', '.github', 'build', 'test', 'example', 'managed_components'], base_path = test_folder)
    #test_recursive_folder_analysis(test_folder = test_folder, output_dir = output_folder, file_extensions=['.cpp', '.h', '.cc', '.c', 'py'], exclude_patterns=['__pycache__', '.git', 'node_modules', '.vscode', '.git', '.github', 'build'], base_path = test_folder)