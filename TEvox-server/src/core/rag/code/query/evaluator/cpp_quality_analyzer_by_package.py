# evox-server/src/core/rag/code/query/evaluator/cpp_quality_analyzer_by_package.py

"""
基于Lizard的C++代码质量分析器
使用Lizard的AST解析能力，手动计算Halstead等指标
与cpp_quality_analyzer.py保持相同的接口和输出格式
"""

import os
import re
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from collections import Counter

try:
    import lizard
except ImportError:
    raise ImportError("请安装 lizard: pip install lizard")


# ==================== 数据类定义（与原文件保持一致） ====================

class AnalysisErrorType(Enum):
    SYNTAX_ERROR = "syntax_error"
    PARSING_ERROR = "parsing_error"
    INVALID_CODE = "invalid_code"


@dataclass
class AnalysisError:
    """分析错误信息"""
    error_type: AnalysisErrorType
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None


@dataclass
class CppQualityMetrics:
    """C++代码质量指标结果"""
    # 基础指标
    avg_cyclomatic_complexity: float
    halstead_volume: float
    halstead_effort: float
    halstead_difficulty: float
    lines_of_code: int
    function_count: int
    comment_density: float
    avg_function_length: float
    
    # 错误信息
    has_errors: bool
    errors: List[AnalysisError]


@dataclass
class EvaluationResult:
    """单个评估结果"""
    query: str
    generated_code: str
    baseline_metrics: Optional[CppQualityMetrics] = None
    ours_metrics: Optional[CppQualityMetrics] = None
    comparison_result: Optional[Dict[str, Any]] = None


# ==================== 主分析器类 ====================

class CppCodeAnalyzerByPackage:
    """基于Lizard的C++代码质量分析器"""
    
    def __init__(self):
        """初始化分析器"""
        # C++操作符集合（用于Halstead计算）
        self.cpp_operators = {
            '+', '-', '*', '/', '%', '=', '==', '!=', '<', '>', '<=', '>=',
            '&&', '||', '!', '&', '|', '^', '~', '<<', '>>', '++', '--',
            '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<=', '>>=',
            '->', '.', '::', '?', ':', ',', ';', '(', ')', '[', ']', '{', '}',
            'new', 'delete', 'sizeof', 'typeof'
        }
        
        # C++关键字（用于Halstead计算）
        self.cpp_keywords = {
            'auto', 'break', 'case', 'catch', 'char', 'class', 'const', 'constexpr',
            'continue', 'default', 'delete', 'do', 'double', 'else', 'enum', 'explicit',
            'extern', 'float', 'for', 'friend', 'goto', 'if', 'inline', 'int', 'long',
            'namespace', 'new', 'operator', 'private', 'protected', 'public', 'return',
            'short', 'signed', 'sizeof', 'static', 'struct', 'switch', 'template',
            'this', 'throw', 'try', 'typedef', 'typename', 'union', 'unsigned',
            'virtual', 'void', 'volatile', 'while', 'bool', 'true', 'false', 'nullptr'
        }
    
    def analyze_code_quality(self, code: str, source_name: Optional[str] = None) -> CppQualityMetrics:
        """
        分析C++代码质量，返回八个评估指标

        Args:
            code: 要分析的C++代码字符串
            source_name: 可选，用于 Lizard 结果中的文件名（如真实路径或 submodule id），便于日志/调试；默认 "temp.cpp"
        Returns:
            CppQualityMetrics: 包含八个指标的结果
        """
        errors = []
        filename = source_name if source_name is not None else "temp.cpp"
        try:
            # 使用Lizard进行分析（filename 仅用于结果标识，不读盘）
            lizard_result = lizard.analyze_file.analyze_source_code(filename, code)
            # 1. 基础指标（Lizard直接提供）
            lines_of_code = lizard_result.nloc  # Non-comment lines of code
            function_count = len(lizard_result.function_list)
            
            # 2. 计算注释密度
            comment_density = self._calculate_comment_density(code, lizard_result)
            
            # 3. 计算平均圈复杂度
            avg_cyclomatic_complexity = self._calculate_avg_complexity(lizard_result)
            
            # 4. 计算平均函数长度
            avg_function_length = self._calculate_avg_function_length(lizard_result)
            
            # 5. 计算Halstead指标（手动实现）
            halstead_metrics = self._calculate_halstead_metrics(code, lizard_result)
            
            return CppQualityMetrics(
                avg_cyclomatic_complexity=avg_cyclomatic_complexity,
                halstead_volume=halstead_metrics['volume'],
                halstead_effort=halstead_metrics['effort'],
                halstead_difficulty=halstead_metrics['difficulty'],
                lines_of_code=lines_of_code,
                function_count=function_count,
                comment_density=comment_density,
                avg_function_length=avg_function_length,
                has_errors=len(errors) > 0,
                errors=errors
            )
            
        except Exception as e:
            errors.append(AnalysisError(
                error_type=AnalysisErrorType.PARSING_ERROR,
                message=f"代码解析错误: {str(e)}"
            ))
            return CppQualityMetrics(
                avg_cyclomatic_complexity=0.0,
                halstead_volume=0.0,
                halstead_effort=0.0,
                halstead_difficulty=0.0,
                lines_of_code=0,
                function_count=0,
                comment_density=0.0,
                avg_function_length=0.0,
                has_errors=True,
                errors=errors
            )
    
    def _calculate_comment_density(self, code: str, lizard_result) -> float:
        """
        计算注释密度
        使用总行数和NLOC的差值估算注释行数
        """
        # 使用所有行（包括空行）作为总行数
        total_lines = len(code.split('\n'))
        if total_lines == 0:
            return 0.0
        
        # NLOC是非注释代码行，差值大致为注释+空行
        # Lizard提供comment_lines字段，优先使用
        if hasattr(lizard_result, 'comment_lines'):
            comment_lines = lizard_result.comment_lines
        else:
            # fallback: 估算 (总行数 - NLOC = 注释行 + 空行)
            # 为了更准确，我们需要手动计算注释行
            comment_lines = self._count_comment_lines(code)
        
        return comment_lines / total_lines if total_lines > 0 else 0.0
    
    def _count_comment_lines(self, code: str) -> int:
        """
        手动计算注释行数（包括纯注释行和包含行尾注释的行）
        """
        comment_lines = 0
        lines = code.split('\n')
        in_multiline_comment = False
        
        for line in lines:
            stripped = line.strip()
            has_comment = False
            
            # 检查多行注释的开始
            if '/*' in stripped:
                in_multiline_comment = True
                has_comment = True
                # 检查是否在同一行结束
                if '*/' in stripped:
                    in_multiline_comment = False
            # 在多行注释中
            elif in_multiline_comment:
                has_comment = True
                # 检查多行注释的结束
                if '*/' in stripped:
                    in_multiline_comment = False
            # 检查单行注释（包括纯注释行和行尾注释）
            elif '//' in stripped:
                has_comment = True
            
            if has_comment:
                comment_lines += 1
        
        return comment_lines
    
    def _calculate_avg_complexity(self, lizard_result) -> float:
        """计算平均圈复杂度"""
        if not lizard_result.function_list:
            return 0.0
        
        total_complexity = sum(func.cyclomatic_complexity for func in lizard_result.function_list)
        return total_complexity / len(lizard_result.function_list)
    
    def _calculate_avg_function_length(self, lizard_result) -> float:
        """计算平均函数长度"""
        if not lizard_result.function_list:
            return 0.0
        
        total_length = sum(func.length for func in lizard_result.function_list)
        return total_length / len(lizard_result.function_list)
    
    def _calculate_halstead_metrics(self, code: str, lizard_result) -> Dict[str, float]:
        """
        手动计算Halstead指标
        基于代码tokenization和Lizard提供的信息
        
        Halstead指标：
        - n1: 不同操作符数量
        - n2: 不同操作数数量
        - N1: 操作符总数
        - N2: 操作数总数
        - Vocabulary = n1 + n2
        - Length = N1 + N2
        - Volume = Length * log2(Vocabulary)
        - Difficulty = (n1/2) * (N2/n2)
        - Effort = Difficulty * Volume
        """
        try:
            # 方法1: 基于Lizard的token_count（如果可用）
            total_tokens = 0
            for func in lizard_result.function_list:
                if hasattr(func, 'token_count'):
                    total_tokens += func.token_count
            
            if total_tokens > 0:
                # 使用token count进行估算
                return self._estimate_halstead_from_tokens(total_tokens, lizard_result)
            
            # 方法2: 手动tokenize代码
            return self._calculate_halstead_from_code(code)
            
        except Exception as e:
            # Fallback: 基于代码行数的粗略估算
            return self._estimate_halstead_from_loc(lizard_result.nloc)
    
    def _calculate_halstead_from_code(self, code: str) -> Dict[str, float]:
        """
        通过手动解析代码计算Halstead指标
        """
        # 移除注释和字符串
        clean_code = self._remove_strings_and_comments(code)
        
        # 提取操作符和操作数
        operators = Counter()
        operands = Counter()
        
        # 简化的token提取（使用正则表达式）
        # 提取操作符
        for op in sorted(self.cpp_operators, key=len, reverse=True):
            # 转义特殊字符
            escaped_op = re.escape(op)
            matches = re.findall(escaped_op, clean_code)
            if matches:
                operators[op] = len(matches)
                # 从代码中移除已匹配的操作符，避免重复计数
                clean_code = re.sub(escaped_op, ' ', clean_code)
        
        # 提取操作数（标识符和数字）
        # 标识符
        identifier_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        identifiers = re.findall(identifier_pattern, clean_code)
        for identifier in identifiers:
            if identifier not in self.cpp_keywords:
                operands[identifier] += 1
        
        # 数字
        number_pattern = r'\b\d+\.?\d*[fFlLuU]*\b'
        numbers = re.findall(number_pattern, clean_code)
        for number in numbers:
            operands[number] += 1
        
        # 计算Halstead指标
        n1 = len(operators)  # 不同操作符数量
        n2 = len(operands)   # 不同操作数数量
        N1 = sum(operators.values())  # 操作符总数
        N2 = sum(operands.values())   # 操作数总数
        
        vocabulary = n1 + n2
        length = N1 + N2
        
        # 避免log(0)
        volume = length * math.log2(vocabulary) if vocabulary > 0 else 0
        difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 else 0
        effort = difficulty * volume
        
        return {
            'volume': volume,
            'difficulty': difficulty,
            'effort': effort
        }
    
    def _estimate_halstead_from_tokens(self, total_tokens: int, lizard_result) -> Dict[str, float]:
        """
        基于Lizard的token count估算Halstead指标
        """
        # 估算唯一token数量（经验公式）
        unique_tokens = int(total_tokens ** 0.7)  # 经验值
        
        # 假设操作符和操作数比例为 4:6
        n1 = int(unique_tokens * 0.4)
        n2 = int(unique_tokens * 0.6)
        N1 = int(total_tokens * 0.4)
        N2 = int(total_tokens * 0.6)
        
        vocabulary = n1 + n2
        length = N1 + N2
        volume = length * math.log2(vocabulary) if vocabulary > 0 else 0
        difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 else 0
        effort = difficulty * volume
        
        return {
            'volume': volume,
            'difficulty': difficulty,
            'effort': effort
        }
    
    def _estimate_halstead_from_loc(self, nloc: int) -> Dict[str, float]:
        """
        基于代码行数的粗略Halstead估算（最后的fallback）
        """
        # 经验公式：基于实际C++项目的统计数据
        estimated_volume = nloc * 25.0  # 每行代码约25的体积
        estimated_difficulty = nloc * 1.2  # 每行代码约1.2的难度
        estimated_effort = estimated_volume * estimated_difficulty
        
        return {
            'volume': estimated_volume,
            'difficulty': estimated_difficulty,
            'effort': estimated_effort
        }
    
    def _remove_strings_and_comments(self, code: str) -> str:
        """
        移除字符串和注释（简化版）
        """
        result = []
        i = 0
        in_string = False
        string_char = None
        
        while i < len(code):
            # 处理单行注释
            if not in_string and i < len(code) - 1 and code[i:i+2] == '//':
                while i < len(code) and code[i] != '\n':
                    i += 1
                if i < len(code):
                    result.append('\n')
                    i += 1
                continue
            
            # 处理多行注释
            if not in_string and i < len(code) - 1 and code[i:i+2] == '/*':
                i += 2
                while i < len(code) - 1:
                    if code[i:i+2] == '*/':
                        i += 2
                        break
                    if code[i] == '\n':
                        result.append('\n')
                    i += 1
                continue
            
            # 处理字符串
            if code[i] in ['"', "'"]:
                if not in_string:
                    in_string = True
                    string_char = code[i]
                elif code[i] == string_char and (i == 0 or code[i-1] != '\\'):
                    in_string = False
                    string_char = None
                result.append(' ')
                i += 1
                continue
            
            if in_string:
                if code[i] == '\n':
                    result.append('\n')
                else:
                    result.append(' ')
            else:
                result.append(code[i])
            
            i += 1
        
        return ''.join(result)
    
    def analyze_code_quality_with_debug(
        self, code: str, debug: bool = False, source_name: Optional[str] = None
    ) -> CppQualityMetrics:
        """
        分析C++代码质量，带调试输出

        Args:
            code: 要分析的C++代码字符串
            debug: 是否输出调试信息
            source_name: 可选，用于 Lizard 结果中的文件名（如真实路径或 submodule id）
        Returns:
            CppQualityMetrics: 包含八个指标的结果
        """
        errors = []
        filename = source_name if source_name is not None else "temp.cpp"
        try:
            lizard_result = lizard.analyze_file.analyze_source_code(filename, code)
            
            if debug:
                print(f"\n=== Lizard 分析结果 ===")
                print(f"代码行数 (NLOC): {lizard_result.nloc}")
                print(f"函数数量: {len(lizard_result.function_list)}")
                if hasattr(lizard_result, 'comment_lines'):
                    print(f"注释行数: {lizard_result.comment_lines}")
                print(f"\n函数列表:")
                for i, func in enumerate(lizard_result.function_list, 1):
                    token_info = f", tokens={func.token_count}" if hasattr(func, 'token_count') else ""
                    print(f"{i}. {func.name} (复杂度={func.cyclomatic_complexity}, 长度={func.length}行{token_info})")
            
            lines_of_code = lizard_result.nloc
            function_count = len(lizard_result.function_list)
            comment_density = self._calculate_comment_density(code, lizard_result)
            avg_cyclomatic_complexity = self._calculate_avg_complexity(lizard_result)
            avg_function_length = self._calculate_avg_function_length(lizard_result)
            halstead_metrics = self._calculate_halstead_metrics(code, lizard_result)
            
            if debug:
                print(f"\n=== 计算指标 ===")
                print(f"平均圈复杂度: {avg_cyclomatic_complexity:.2f}")
                print(f"平均函数长度: {avg_function_length:.2f}")
                print(f"注释密度: {comment_density:.2f}")
                print(f"Halstead 体积: {halstead_metrics['volume']:.2f}")
                print(f"Halstead 难度: {halstead_metrics['difficulty']:.2f}")
                print(f"Halstead 工作量: {halstead_metrics['effort']:.2f}")
            
            return CppQualityMetrics(
                avg_cyclomatic_complexity=avg_cyclomatic_complexity,
                halstead_volume=halstead_metrics['volume'],
                halstead_effort=halstead_metrics['effort'],
                halstead_difficulty=halstead_metrics['difficulty'],
                lines_of_code=lines_of_code,
                function_count=function_count,
                comment_density=comment_density,
                avg_function_length=avg_function_length,
                has_errors=len(errors) > 0,
                errors=errors
            )
            
        except Exception as e:
            if debug:
                print(f"\n错误: {str(e)}")
                import traceback
                traceback.print_exc()
            
            errors.append(AnalysisError(
                error_type=AnalysisErrorType.PARSING_ERROR,
                message=f"代码解析错误: {str(e)}"
            ))
            return CppQualityMetrics(
                avg_cyclomatic_complexity=0.0,
                halstead_volume=0.0,
                halstead_effort=0.0,
                halstead_difficulty=0.0,
                lines_of_code=0,
                function_count=0,
                comment_density=0.0,
                avg_function_length=0.0,
                has_errors=True,
                errors=errors
            )


# ==================== 辅助函数 ====================

def evaluate_cpp_code_quality_standalone(code: str) -> CppQualityMetrics:
    """
    独立的C++代码质量评估函数
    
    Args:
        code: 要评估的C++代码字符串
        
    Returns:
        CppQualityMetrics: 包含八个评估指标的结果
    """
    analyzer = CppCodeAnalyzerByPackage()
    return analyzer.analyze_code_quality(code)


# ==================== 批量分析功能 ====================

def analyze_code_batch(code_dict: Dict[str, str], debug: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    批量分析多个C++代码片段的质量指标
    
    Args:
        code_dict: 字典，key为代码ID，value为对应的C++代码字符串
        debug: 是否输出调试信息
        
    Returns:
        字典，key为代码ID，value为包含八个质量指标的字典
    """
    analyzer = CppCodeAnalyzerByPackage()
    results = {}
    
    total = len(code_dict)
    for idx, (code_id, code) in enumerate(code_dict.items(), 1):
        if debug:
            print(f"\n[{idx}/{total}] 分析代码ID: {code_id}")
        
        try:
            metrics = analyzer.analyze_code_quality(code)
            
            # 将metrics对象转换为字典
            results[code_id] = {
                'avg_cyclomatic_complexity': metrics.avg_cyclomatic_complexity,
                'halstead_volume': metrics.halstead_volume,
                'halstead_effort': metrics.halstead_effort,
                'halstead_difficulty': metrics.halstead_difficulty,
                'lines_of_code': metrics.lines_of_code,
                'function_count': metrics.function_count,
                'comment_density': metrics.comment_density,
                'avg_function_length': metrics.avg_function_length,
                'has_errors': metrics.has_errors,
                'errors': [
                    {
                        'error_type': error.error_type.value,
                        'message': error.message,
                        'line_number': error.line_number,
                        'column': error.column
                    } for error in metrics.errors
                ] if metrics.has_errors else []
            }
            
            if debug:
                print(f"  ✓ 分析完成 - 函数数: {metrics.function_count}, "
                      f"代码行数: {metrics.lines_of_code}, "
                      f"平均复杂度: {metrics.avg_cyclomatic_complexity:.2f}")
                
        except Exception as e:
            if debug:
                print(f"  ✗ 分析失败: {str(e)}")
            results[code_id] = {
                'avg_cyclomatic_complexity': 0.0,
                'halstead_volume': 0.0,
                'halstead_effort': 0.0,
                'halstead_difficulty': 0.0,
                'lines_of_code': 0,
                'function_count': 0,
                'comment_density': 0.0,
                'avg_function_length': 0.0,
                'has_errors': True,
                'errors': [{
                    'error_type': AnalysisErrorType.PARSING_ERROR.value,
                    'message': f"分析异常: {str(e)}",
                    'line_number': None,
                    'column': None
                }]
            }
    
    return results


def analyze_json_file_refactored_modules(
    input_json_path: str, 
    output_json_path: str, 
    debug: bool = False
) -> Dict[str, Dict[str, Any]]:
    """
    从JSON文件中提取以'refactored'结尾的模块代码并进行批量分析
    
    Args:
        input_json_path: 输入JSON文件路径（包含nodes数组，每个node有id和code字段）
        output_json_path: 输出JSON文件路径（保存分析结果）
        debug: 是否输出调试信息
        
    Returns:
        分析结果字典
    """
    print(f"\n{'='*80}")
    print(f"从JSON文件分析refactored模块")
    print(f"{'='*80}")
    print(f"输入文件: {input_json_path}")
    print(f"输出文件: {output_json_path}")
    
    # 1. 读取JSON文件
    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到文件 {input_json_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"错误: JSON解析失败 - {str(e)}")
        return {}
    
    # 2. 提取以'refactored'结尾的模块
    code_dict = {}
    if 'nodes' in data:
        for node in data['nodes']:
            node_id = node.get('id', '')
            if node_id.endswith('refactored') or node_id.endswith('Refactored'):
                code = node.get('code', '')
                if code:
                    code_dict[node_id] = code
                    if debug:
                        print(f"\n提取模块: {node_id}")
                        print(f"  代码长度: {len(code)} 字符")
    
    if not code_dict:
        print("警告: 未找到任何以'refactored'结尾的模块")
        return {}
    
    print(f"\n找到 {len(code_dict)} 个refactored模块:")
    for node_id in code_dict.keys():
        print(f"  - {node_id}")
    
    # 3. 批量分析代码
    print(f"\n开始批量分析...")
    results = analyze_code_batch(code_dict, debug=debug)
    
    # 4. 保存结果到JSON文件
    try:
        import datetime
        # 构造输出数据结构
        output_data = {
            'metadata': {
                'input_file': input_json_path,
                'total_modules': len(results),
                'analysis_timestamp': datetime.datetime.now().isoformat()
            },
            'results': results
        }
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 分析完成！结果已保存到: {output_json_path}")
        
    except Exception as e:
        print(f"\n✗ 保存结果失败: {str(e)}")
    
    return results


def print_analysis_summary(results: Dict[str, Dict[str, Any]]):
    """
    打印分析结果摘要
    
    Args:
        results: 分析结果字典
    """
    print(f"\n{'='*80}")
    print("分析结果摘要")
    print(f"{'='*80}")
    
    for code_id, metrics in results.items():
        print(f"\n模块: {code_id}")
        print(f"  {'函数数量:':<25} {metrics['function_count']}")
        print(f"  {'代码行数:':<25} {metrics['lines_of_code']}")
        print(f"  {'平均函数长度:':<25} {metrics['avg_function_length']:.2f} 行")
        print(f"  {'平均圈复杂度:':<25} {metrics['avg_cyclomatic_complexity']:.2f}")
        print(f"  {'注释密度:':<25} {metrics['comment_density']:.4f}")
        print(f"  {'Halstead 体积:':<25} {metrics['halstead_volume']:.2f}")
        print(f"  {'Halstead 难度:':<25} {metrics['halstead_difficulty']:.2f}")
        print(f"  {'Halstead 工作量:':<25} {metrics['halstead_effort']:.2f}")
        
        if metrics['has_errors']:
            print(f"  {'状态:':<25} ⚠ 有错误")
            for error in metrics['errors']:
                print(f"    - {error['message']}")
        else:
            print(f"  {'状态:':<25} ✓ 正常")
    
    print(f"\n{'='*80}")


def analyze_file_list(
    file_list: List[str],
    base_path: str,
    output_json_path: str,
    debug: bool = False
) -> Dict[str, Dict[str, Any]]:
    """
    从文件列表中读取C++代码文件并进行批量分析
    
    Args:
        file_list: 文件路径列表，格式为 ["file:路径1", "file:路径2", ...]
        base_path: 基础路径，用于构造完整文件路径
        output_json_path: 输出JSON文件路径
        debug: 是否输出调试信息
        
    Returns:
        分析结果字典
        
    Example:
        file_list = [
            "file:managed_components/78__esp-wifi-connect/ssid_manager.cc",
            "file:managed_components/78__esp-wifi-connect/dns_server.cc"
        ]
        base_path = "D:/Download/github/xiaozhi-esp32"
        results = analyze_file_list(file_list, base_path, "output.json", debug=True)
    """
    print(f"\n{'='*80}")
    print(f"从文件列表分析C++代码")
    print(f"{'='*80}")
    print(f"基础路径: {base_path}")
    print(f"文件数量: {len(file_list)}")
    print(f"输出文件: {output_json_path}")
    
    # 1. 处理文件列表，读取代码
    code_dict = {}
    failed_files = []
    
    for file_path_str in file_list:
        # 去掉 "file:" 前缀
        if file_path_str.startswith("file:"):
            relative_path = file_path_str[5:]  # 去掉 "file:"
        else:
            relative_path = file_path_str
        
        # 构造完整路径
        full_path = os.path.join(base_path, relative_path)
        
        # 提取文件名作为ID（不含路径）
        file_name = os.path.basename(relative_path)
        
        if debug:
            print(f"\n处理文件: {file_name}")
            print(f"  相对路径: {relative_path}")
            print(f"  完整路径: {full_path}")
        
        # 读取文件内容
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            code_dict[file_name] = code
            
            if debug:
                print(f"  ✓ 读取成功 - 代码长度: {len(code)} 字符")
                
        except FileNotFoundError:
            print(f"  ✗ 错误: 文件不存在 - {full_path}")
            failed_files.append(file_name)
        except Exception as e:
            print(f"  ✗ 错误: 读取失败 - {str(e)}")
            failed_files.append(file_name)
    
    if not code_dict:
        print("\n警告: 没有成功读取任何文件")
        return {}
    
    print(f"\n成功读取 {len(code_dict)} 个文件:")
    for file_name in code_dict.keys():
        print(f"  - {file_name}")
    
    if failed_files:
        print(f"\n失败的文件 ({len(failed_files)}):")
        for file_name in failed_files:
            print(f"  - {file_name}")
    
    # 2. 批量分析代码
    print(f"\n开始批量分析...")
    results = analyze_code_batch(code_dict, debug=debug)
    
    # 3. 保存结果到JSON文件
    try:
        import datetime
        # 构造输出数据结构
        output_data = {
            'metadata': {
                'base_path': base_path,
                'total_files': len(file_list),
                'successful_files': len(code_dict),
                'failed_files': len(failed_files),
                'failed_file_list': failed_files,
                'analysis_timestamp': datetime.datetime.now().isoformat()
            },
            'file_paths': {
                file_name: file_list[idx] 
                for idx, file_name in enumerate(code_dict.keys())
            },
            'results': results
        }
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 分析完成！结果已保存到: {output_json_path}")
        
    except Exception as e:
        print(f"\n✗ 保存结果失败: {str(e)}")
    
    return results


# ==================== 测试函数 ====================

def test_with_real_files():
    """使用实际文件测试"""
    print("\n" + "="*80)
    print("使用Lizard测试实际文件")
    print("="*80)
    
    baseline_path = "baseline.cpp"
    ours_path = "ours.cpp"
    
    # 尝试多个可能的路径
    possible_paths = [
        ("baseline.cpp", "ours.cpp"),
        ("evox-server/src/core/rag/code/query/evaluator/baseline.cpp",
         "evox-server/src/core/rag/code/query/evaluator/ours.cpp"),
        ("D:\\Download\\github\\evox-ai\\evox-server\\src\\core\\rag\\code\\query\\evaluator\\baseline.cpp",
         "D:\\Download\\github\\evox-ai\\evox-server\\src\\core\\rag\\code\\query\\evaluator\\ours.cpp"),
    ]
    
    for base_p, ours_p in possible_paths:
        if os.path.exists(base_p):
            baseline_path = base_p
            ours_path = ours_p
            break
    
    if os.path.exists(baseline_path):
        print(f"\n=== 分析 Baseline.cpp ===")
        with open(baseline_path, 'r', encoding='utf-8') as f:
            baseline_code = f.read()
        
        analyzer = CppCodeAnalyzerByPackage()
        metrics = analyzer.analyze_code_quality_with_debug(baseline_code, debug=True)
        
        print(f"\n=== Baseline.cpp 最终结果 ===")
        print(f"函数数量: {metrics.function_count}")
        print(f"平均函数长度: {metrics.avg_function_length:.2f}行")
        print(f"平均圈复杂度: {metrics.avg_cyclomatic_complexity:.2f}")
        print(f"代码行数: {metrics.lines_of_code}")
        print(f"注释密度: {metrics.comment_density:.2f}")
        print(f"Halstead 体积: {metrics.halstead_volume:.2f}")
        print(f"Halstead 难度: {metrics.halstead_difficulty:.2f}")
        print(f"Halstead 工作量: {metrics.halstead_effort:.2f}")
    else:
        print(f"警告: 未找到 baseline.cpp")
    
    if os.path.exists(ours_path):
        print(f"\n=== 分析 Ours.cpp ===")
        with open(ours_path, 'r', encoding='utf-8') as f:
            ours_code = f.read()
        
        analyzer = CppCodeAnalyzerByPackage()
        metrics = analyzer.analyze_code_quality_with_debug(ours_code, debug=True)
        
        print(f"\n=== Ours.cpp 最终结果 ===")
        print(f"函数数量: {metrics.function_count}")
        print(f"平均函数长度: {metrics.avg_function_length:.2f}行")
        print(f"平均圈复杂度: {metrics.avg_cyclomatic_complexity:.2f}")
        print(f"代码行数: {metrics.lines_of_code}")
        print(f"注释密度: {metrics.comment_density:.2f}")
        print(f"Halstead 体积: {metrics.halstead_volume:.2f}")
        print(f"Halstead 难度: {metrics.halstead_difficulty:.2f}")
        print(f"Halstead 工作量: {metrics.halstead_effort:.2f}")
    else:
        print(f"警告: 未找到 ours.cpp")


def test_batch_analysis():
    """测试批量分析功能"""
    print("\n" + "="*80)
    print("测试批量分析功能")
    print("="*80)
    
    # 示例代码
    test_codes = {
        'simple_function': '''
int add(int a, int b) {
    return a + b;
}
''',
        'complex_function': '''
class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }
    
    int multiply(int a, int b) {
        int result = 0;
        for (int i = 0; i < b; i++) {
            result += a;
        }
        return result;
    }
};
'''
    }
    
    results = analyze_code_batch(test_codes, debug=True)
    print_analysis_summary(results)


def test_json_file_analysis():
    """测试JSON文件分析功能"""
    print("\n" + "="*80)
    print("测试JSON文件分析功能")
    print("="*80)
    
    # 尝试多个可能的路径
    possible_paths = [
        "evox-server/.rag/xiaozhi/designer_9_23/test_design_3.json",
        ".rag/xiaozhi/designer_9_23/test_design_3.json",
        "test_design_3.json"
    ]
    
    input_path = None
    for path in possible_paths:
        if os.path.exists(path):
            input_path = path
            break
    
    if input_path:
        output_path = "refactored_modules_analysis_results.json"
        results = analyze_json_file_refactored_modules(
            input_path, 
            output_path, 
            debug=True
        )
        
        if results:
            print_analysis_summary(results)
    else:
        print("警告: 未找到 test_design_3.json 文件")
        print("尝试过的路径:")
        for path in possible_paths:
            print(f"  - {path}")


def test_file_list_analysis():
    """测试文件列表分析功能"""
    print("\n" + "="*80)
    print("测试文件列表分析功能")
    print("="*80)
    
    # 示例文件列表和基础路径
    file_list = [
        "file:managed_components/78__esp-wifi-connect/ssid_manager.cc",
        "file:managed_components/78__esp-wifi-connect/dns_server.cc",
        "file:managed_components/78__esp-wifi-connect/wifi_configuration_ap.cc",
        "file:managed_components/78__esp-wifi-connect/wifi_station.cc"
    ]
    base_path = "D:/Download/github/xiaozhi-esp32"
    
    print(f"\n文件列表 ({len(file_list)} 个文件):")
    for f in file_list:
        print(f"  - {f}")
    print(f"\n基础路径: {base_path}")
    
    # 检查base_path是否存在
    if not os.path.exists(base_path):
        print(f"\n警告: 基础路径不存在: {base_path}")
        print("请修改test_file_list_analysis()中的base_path")
        return
    
    output_path = "file_list_analysis_results.json"
    
    results = analyze_file_list(
        file_list,
        base_path,
        output_path,
        debug=True
    )
    
    if results:
        print_analysis_summary(results)


def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'test':
            # 原有测试
            print("开始使用Lizard进行C++代码质量评估...")
            try:
                test_with_real_files()
                print("\n" + "="*80)
                print("测试完成!")
                print("="*80)
            except Exception as e:
                print(f"\n发生错误: {e}")
                import traceback
                traceback.print_exc()
        
        elif command == 'batch':
            # 测试批量分析
            test_batch_analysis()
        
        elif command == 'json':
            # 测试JSON文件分析
            test_json_file_analysis()
        
        elif command == 'file-list':
            # 测试文件列表分析
            test_file_list_analysis()
        
        elif command == 'analyze-json':
            # 直接分析JSON文件（需要提供输入和输出路径）
            if len(sys.argv) >= 4:
                input_path = sys.argv[2]
                output_path = sys.argv[3]
                debug = '--debug' in sys.argv
                
                results = analyze_json_file_refactored_modules(
                    input_path, 
                    output_path, 
                    debug=debug
                )
                
                if results:
                    print_analysis_summary(results)
            else:
                print("用法: python cpp_quality_analyzer_by_package.py analyze-json <input.json> <output.json> [--debug]")
        
        elif command == 'analyze-files':
            # 直接分析文件列表
            if len(sys.argv) >= 4:
                # 格式: analyze-files base_path output.json file1 file2 file3 ...
                base_path = sys.argv[2]
                output_path = sys.argv[3]
                file_list = sys.argv[4:]
                debug = '--debug' in file_list
                
                if debug:
                    file_list.remove('--debug')
                
                if not file_list:
                    print("错误: 请提供至少一个文件路径")
                    print("用法: python cpp_quality_analyzer_by_package.py analyze-files <base_path> <output.json> <file1> <file2> ... [--debug]")
                    return
                
                results = analyze_file_list(
                    file_list,
                    base_path,
                    output_path,
                    debug=debug
                )
                
                if results:
                    print_analysis_summary(results)
            else:
                print("用法: python cpp_quality_analyzer_by_package.py analyze-files <base_path> <output.json> <file1> <file2> ... [--debug]")
                print("\n示例:")
                print('  python cpp_quality_analyzer_by_package.py analyze-files "D:/path/to/project" output.json \\')
                print('    "file:src/module1.cc" "file:src/module2.cc" --debug')
        
        else:
            print(f"未知命令: {command}")
            print("可用命令: test, batch, json, file-list, analyze-json, analyze-files")
            print("\n命令说明:")
            print("  test         - 测试实际文件分析")
            print("  batch        - 测试批量分析功能")
            print("  json         - 测试JSON文件分析")
            print("  file-list    - 测试文件列表分析")
            print("  analyze-json - 分析JSON文件中的refactored模块")
            print("  analyze-files- 分析指定的文件列表")
    
    else:
        # 默认：测试JSON文件分析
        print("开始使用Lizard进行C++代码质量评估...")
        try:
            test_json_file_analysis()
            print("\n" + "="*80)
            print("测试完成!")
            print("="*80)
        except Exception as e:
            print(f"\n发生错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    #main()
    sample_code = """
#include <iostream>
#include <vector>

class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }
    int multiply(int a, int b) {
        return a * b;
    }
    
    double divide(double a, double b) {
        if (b == 0) {
            throw std::invalid_argument("Division by zero");
        }
        return a / b;
    }
};
"""
    quality_analyzer=CppCodeAnalyzerByPackage()
    metrics = quality_analyzer.analyze_code_quality(sample_code)
    print(metrics)

