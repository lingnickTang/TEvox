"""
Benchmark 结果展示和比较工具

用于读取 workflow.py 运行出的结果 JSON 文件，进行定量和定性评估结果的展示和比较。

汇总用法说明：
  # 汇总 benchmark 目录下全部 *_results_*.json 文件，生成 aggregate_table.json
  python -m src.core.rag.code.show_benchmark --aggregate-all --benchmark-dir "evox-server/.rag/benchmark"

  # 仅汇总以 Desc 开头的结果文件，生成 aggregate_table_Desc.json
  python -m src.core.rag.code.show_benchmark --desc-aggregate --benchmark-dir "evox-server/.rag/benchmark"

  # 指定绝对路径
  python -m src.core.rag.code.show_benchmark --aggregate-all --benchmark-dir "D:/path/to/.rag/benchmark"

  # 将汇总结果额外保存到指定文件
  python -m src.core.rag.code.show_benchmark --aggregate-all --output my_aggregate.json
"""
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict
from datetime import datetime

from src.utils.log import logger


class BenchmarkShow:
    """
    用于展示和比较 benchmark 结果的类
    """
    
    def __init__(self, benchmark_dir: str = "evox-server/.rag/benchmark"):
        """
        初始化
        
        Args:
            benchmark_dir: benchmark 文件所在目录（支持相对路径或绝对路径）
        """
        bp = Path(benchmark_dir)
        if not bp.is_absolute():
            cwd = Path.cwd()
            candidates = [
                cwd / benchmark_dir,
                cwd / ".rag" / "benchmark" if cwd.name == "evox-server" else None,
                cwd / "evox-server" / ".rag" / "benchmark" if (cwd / "evox-server").exists() else None,
            ]
            for p in candidates:
                if p and p.exists():
                    bp = p
                    break
        self.benchmark_dir = bp
    
    def load_result_file(self, result_file_path: str) -> Dict[str, Any]:
        """
        加载结果 JSON 文件
        
        支持两种格式：
        1. 对象格式：包含 metadata, statistics, results 字段
        2. 数组格式：直接是结果列表
        
        Args:
            result_file_path: 结果文件路径
            
        Returns:
            结果数据字典（统一格式，包含 metadata 和 results）
        """
        file_path = Path(result_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Result file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 如果是数组格式，转换为统一的对象格式
        if isinstance(data, list):
            return {
                "metadata": {},
                "statistics": {},
                "results": data
            }
        elif isinstance(data, dict):
            # 确保有 results 字段
            if "results" not in data:
                # 如果整个字典就是结果列表的结构，尝试提取
                return {
                    "metadata": data.get("metadata", {}),
                    "statistics": data.get("statistics", {}),
                    "results": data.get("results", [])
                }
            return data
        else:
            raise ValueError(f"Unexpected data format: {type(data)}")
    
    def extract_quantitative_stats(self, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """
        从评估结果中提取定量统计信息
        
        Args:
            evaluation: 评估结果字典，包含 quantitative 字段
            
        Returns:
            定量统计信息
        """
        quantitative = evaluation.get("quantitative", {})
        if not quantitative:
            return {
                "correctly_reused_functions": 0,
                "correctly_reused_variables": 0,
                "incorrectly_constructed_functions": 0,
                "incorrectly_constructed_variables": 0,
                "total_reference_functions": 0,
                "total_reference_variables": 0,
                "function_reuse_rate": 0.0,
                "variable_reuse_rate": 0.0
            }
        
        correctly_reused = quantitative.get("correctly_reused", {})
        incorrectly_constructed = quantitative.get("incorrectly_constructed", {})
        
        correctly_functions = correctly_reused.get("functions", [])
        correctly_variables = correctly_reused.get("variables", [])
        incorrect_functions = incorrectly_constructed.get("functions", [])
        incorrect_variables = incorrectly_constructed.get("variables", [])
        
        # 过滤掉占位符值（如 "<none>", "none", "(none)" 等）
        def filter_placeholders(items):
            if not isinstance(items, list):
                return []
            filtered = []
            placeholder_values = {"<none>", "none", "(none)", "n/a", "N/A", "null", "NULL", ""}
            for item in items:
                if item is None:
                    continue
                # 如果是字符串，检查是否是占位符
                if isinstance(item, str):
                    item_lower = item.strip().lower()
                    if item and item_lower not in placeholder_values:
                        filtered.append(item)
                else:
                    # 非字符串类型（如字典）直接保留
                    filtered.append(item)
            return filtered
        
        correctly_functions = filter_placeholders(correctly_functions)
        correctly_variables = filter_placeholders(correctly_variables)
        incorrect_functions = filter_placeholders(incorrect_functions)
        incorrect_variables = filter_placeholders(incorrect_variables)
        
        # 计算总数
        total_reference_functions = quantitative.get("reference_functions_cnt", 0)
        total_reference_variables = quantitative.get("reference_variables_cnt", 0)
        
        # 计算重用率
        function_reuse_rate = (len(correctly_functions) / total_reference_functions * 100) if total_reference_functions > 0 else 0.0
        variable_reuse_rate = (len(correctly_variables) / total_reference_variables * 100) if total_reference_variables > 0 else 0.0
        
        return {
            "correctly_reused_functions": len(correctly_functions),
            "correctly_reused_variables": len(correctly_variables),
            "incorrectly_constructed_functions": len(incorrect_functions),
            "incorrectly_constructed_variables": len(incorrect_variables),
            "total_reference_functions": total_reference_functions,
            "total_reference_variables": total_reference_variables,
            "function_reuse_rate": function_reuse_rate,
            "variable_reuse_rate": variable_reuse_rate,
            "correctly_reused_functions_list": correctly_functions,
            "correctly_reused_variables_list": correctly_variables,
            "incorrectly_constructed_functions_list": incorrect_functions,
            "incorrectly_constructed_variables_list": incorrect_variables
        }
    
    def extract_qualitative_stats(self, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """
        从评估结果中提取定性统计信息
        
        Args:
            evaluation: 评估结果字典，包含 qualitative 字段
            
        Returns:
            定性统计信息
        """
        qualitative = evaluation.get("qualitative", {})
        if not qualitative:
            return {
                "semantic_score": 0,
                "structure_score": 0,
                "completeness_score": 0,
                "analysis": ""
            }
        
        return {
            "semantic_score": qualitative.get("semantic_score", 0),
            "structure_score": qualitative.get("structure_score", 0),
            "completeness_score": qualitative.get("completeness_score", 0),
            "analysis": qualitative.get("analysis", "")
        }
    
    def analyze_single_result(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析单个结果文件
        
        Args:
            result_data: 结果数据字典
            
        Returns:
            分析结果
        """
        metadata = result_data.get("metadata", {})
        results = result_data.get("results", [])
        
        # 统计信息
        quantitative_stats_list = []
        qualitative_stats_list = []
        
        # 按文件路径分组
        file_stats = defaultdict(lambda: {
            "quantitative": [],
            "qualitative": [],
            "queries": []
        })
        
        for result in results:
            evaluation = result.get("evaluation", {})
            # 跳过没有评估结果或包含错误的案例
            if not evaluation or "error" in evaluation:
                continue
            
            # 确保 evaluation 是字典类型
            if not isinstance(evaluation, dict):
                continue
            
            # 提取定量和定性统计
            quant_stats = self.extract_quantitative_stats(evaluation)
            qual_stats = self.extract_qualitative_stats(evaluation)
            
            quantitative_stats_list.append(quant_stats)
            qualitative_stats_list.append(qual_stats)
            
            # 按文件路径分组
            file_path = result.get("file_path", "unknown")
            file_stats[file_path]["quantitative"].append(quant_stats)
            file_stats[file_path]["qualitative"].append(qual_stats)
            file_stats[file_path]["queries"].append(result.get("query", ""))
        
        # 计算总体平均值
        avg_quantitative = self._calculate_avg_quantitative(quantitative_stats_list)
        avg_qualitative = self._calculate_avg_qualitative(qualitative_stats_list)
        
        # 计算每个文件的平均值
        file_averages = {}
        for file_path, stats in file_stats.items():
            file_averages[file_path] = {
                "quantitative": self._calculate_avg_quantitative(stats["quantitative"]),
                "qualitative": self._calculate_avg_qualitative(stats["qualitative"]),
                "query_count": len(stats["queries"])
            }
        
        return {
            "metadata": metadata,
            "total_cases": len(results),
            "valid_cases": len(quantitative_stats_list),
            "average_quantitative": avg_quantitative,
            "average_qualitative": avg_qualitative,
            "file_statistics": file_averages,
            "all_quantitative_stats": quantitative_stats_list,
            "all_qualitative_stats": qualitative_stats_list
        }
    
    def _calculate_avg_quantitative(self, stats_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算定量统计的平均值"""
        if not stats_list:
            return {}
        
        avg = {
            "correctly_reused_functions": 0.0,
            "correctly_reused_variables": 0.0,
            "incorrectly_constructed_functions": 0.0,
            "incorrectly_constructed_variables": 0.0,
            "total_reference_functions": 0.0,
            "total_reference_variables": 0.0,
            "function_reuse_rate": 0.0,
            "variable_reuse_rate": 0.0
        }
        
        for stats in stats_list:
            for key in avg.keys():
                if key in stats:
                    avg[key] += stats[key]
        
        for key in avg.keys():
            avg[key] /= len(stats_list)
        
        return avg
    
    def _calculate_avg_qualitative(self, stats_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算定性统计的平均值"""
        if not stats_list:
            return {}
        
        avg = {
            "semantic_score": 0.0,
            "structure_score": 0.0,
            "completeness_score": 0.0
        }
        
        for stats in stats_list:
            for key in avg.keys():
                if key in stats:
                    avg[key] += stats[key]
        
        for key in avg.keys():
            avg[key] /= len(stats_list)
        
        return avg
    
    def compare_results(self, result_files: List[str]) -> Dict[str, Any]:
        """
        比较多个结果文件
        
        Args:
            result_files: 结果文件路径列表
            
        Returns:
            比较结果
        """
        analyses = {}
        for result_file in result_files:
            result_data = self.load_result_file(result_file)
            analyses[result_file] = self.analyze_single_result(result_data)
        
        # 提取所有测试类型的元数据
        comparison = {
            "files": list(analyses.keys()),
            "analyses": analyses,
            "summary": {}
        }
        
        # 汇总比较
        if len(analyses) > 1:
            # 比较平均分
            comparison["summary"] = {
                "quantitative_comparison": {},
                "qualitative_comparison": {}
            }
            
            for file_path, analysis in analyses.items():
                file_name = Path(file_path).stem
                comparison["summary"]["quantitative_comparison"][file_name] = analysis["average_quantitative"]
                comparison["summary"]["qualitative_comparison"][file_name] = analysis["average_qualitative"]
        
        return comparison
    
    def print_analysis(self, analysis: Dict[str, Any], detailed: bool = False):
        """
        打印分析结果
        
        Args:
            analysis: 分析结果字典
            detailed: 是否打印详细信息
        """
        metadata = analysis.get("metadata", {})
        print(f"\n{'='*80}")
        print(f"Benchmark Analysis")
        print(f"{'='*80}")
        print(f"Test Type: {metadata.get('test_type', 'N/A')}")
        print(f"Date: {metadata.get('date', 'N/A')}")
        print(f"Model: {metadata.get('model_name', 'N/A')}")
        print(f"Total Cases: {analysis.get('total_cases', 0)}")
        print(f"Valid Cases: {analysis.get('valid_cases', 0)}")
        
        # 定量评估结果
        print(f"\n{'='*80}")
        print("Quantitative Evaluation (Average)")
        print(f"{'='*80}")
        avg_quant = analysis.get("average_quantitative", {})
        
        # 函数统计
        avg_correct_funcs = avg_quant.get('correctly_reused_functions', 0)
        avg_incorrect_funcs = avg_quant.get('incorrectly_constructed_functions', 0)
        avg_total_funcs = avg_quant.get('total_reference_functions', 0)
        avg_func_reuse_rate = avg_quant.get('function_reuse_rate', 0)
        
        print(f"\nFunctions:")
        print(f"  - Average Correctly Reused Functions: {avg_correct_funcs:.2f}")
        print(f"  - Average Incorrectly Constructed Functions: {avg_incorrect_funcs:.2f}")
        print(f"  - Average Total Reference Functions: {avg_total_funcs:.2f}")
        print(f"  - Function Reuse Rate: {avg_func_reuse_rate:.2f}%")
        
        # 变量统计
        avg_correct_vars = avg_quant.get('correctly_reused_variables', 0)
        avg_incorrect_vars = avg_quant.get('incorrectly_constructed_variables', 0)
        avg_total_vars = avg_quant.get('total_reference_variables', 0)
        avg_var_reuse_rate = avg_quant.get('variable_reuse_rate', 0)
        
        print(f"\nVariables:")
        print(f"  - Average Correctly Reused Variables: {avg_correct_vars:.2f}")
        print(f"  - Average Incorrectly Constructed Variables: {avg_incorrect_vars:.2f}")
        print(f"  - Average Total Reference Variables: {avg_total_vars:.2f}")
        print(f"  - Variable Reuse Rate: {avg_var_reuse_rate:.2f}%")
        
        # 总体统计
        print(f"\nOverall Statistics:")
        print(f"  - Average Total Functions per Case: {avg_total_funcs:.2f}")
        print(f"  - Average Total Variables per Case: {avg_total_vars:.2f}")
        print(f"  - Average Correct Functions per Case: {avg_correct_funcs:.2f}")
        print(f"  - Average Correct Variables per Case: {avg_correct_vars:.2f}")
        
        # 定性评估结果
        print(f"\n{'='*80}")
        print("Qualitative Evaluation (Average)")
        print(f"{'='*80}")
        avg_qual = analysis.get("average_qualitative", {})
        print(f"Semantic Score: {avg_qual.get('semantic_score', 0):.2f}/100")
        print(f"Structure Score: {avg_qual.get('structure_score', 0):.2f}/100")
        print(f"Completeness Score: {avg_qual.get('completeness_score', 0):.2f}/100")
        print(f"Overall Average: {(avg_qual.get('semantic_score', 0) + avg_qual.get('structure_score', 0) + avg_qual.get('completeness_score', 0)) / 3:.2f}/100")
        
        # 按文件统计
        if detailed:
            print(f"\n{'='*80}")
            print("Statistics by File")
            print(f"{'='*80}")
            file_stats = analysis.get("file_statistics", {})
            for file_path, stats in file_stats.items():
                print(f"\nFile: {file_path}")
                print(f"  Query Count: {stats.get('query_count', 0)}")
                quant = stats.get("quantitative", {})
                qual = stats.get("qualitative", {})
                
                # 函数统计
                print(f"  Functions:")
                print(f"    - Average Correctly Reused: {quant.get('correctly_reused_functions', 0):.2f}")
                print(f"    - Average Incorrectly Constructed: {quant.get('incorrectly_constructed_functions', 0):.2f}")
                print(f"    - Average Total Reference: {quant.get('total_reference_functions', 0):.2f}")
                print(f"    - Function Reuse Rate: {quant.get('function_reuse_rate', 0):.2f}%")
                
                # 变量统计
                print(f"  Variables:")
                print(f"    - Average Correctly Reused: {quant.get('correctly_reused_variables', 0):.2f}")
                print(f"    - Average Incorrectly Constructed: {quant.get('incorrectly_constructed_variables', 0):.2f}")
                print(f"    - Average Total Reference: {quant.get('total_reference_variables', 0):.2f}")
                print(f"    - Variable Reuse Rate: {quant.get('variable_reuse_rate', 0):.2f}%")
                
                # 定性评估
                print(f"  Qualitative Scores:")
                print(f"    - Semantic Score: {qual.get('semantic_score', 0):.2f}/100")
                print(f"    - Structure Score: {qual.get('structure_score', 0):.2f}/100")
                print(f"    - Completeness Score: {qual.get('completeness_score', 0):.2f}/100")
    
    def print_comparison(self, comparison: Dict[str, Any]):
        """
        打印比较结果
        
        Args:
            comparison: 比较结果字典
        """
        print(f"\n{'='*80}")
        print("Benchmark Comparison")
        print(f"{'='*80}")
        
        files = comparison.get("files", [])
        if len(files) <= 1:
            print("Need at least 2 files to compare")
            return
        
        # 定量比较
        print(f"\n{'='*80}")
        print("Quantitative Comparison")
        print(f"{'='*80}")
        quant_comp = comparison.get("summary", {}).get("quantitative_comparison", {})
        
        print(f"\n{'File':<40} {'Func Reuse %':<15} {'Var Reuse %':<15} {'Avg Func':<12} {'Avg Var':<12} {'Correct Func':<15} {'Incorrect Func':<15}")
        print("-" * 120)
        for file_name, stats in quant_comp.items():
            avg_funcs = stats.get('total_reference_functions', 0)
            avg_vars = stats.get('total_reference_variables', 0)
            print(f"{file_name[:40]:<40} {stats.get('function_reuse_rate', 0):>13.2f}% {stats.get('variable_reuse_rate', 0):>13.2f}% "
                  f"{avg_funcs:>10.2f} {avg_vars:>10.2f} "
                  f"{stats.get('correctly_reused_functions', 0):>13.2f} {stats.get('incorrectly_constructed_functions', 0):>13.2f}")
        
        # 定性比较
        print(f"\n{'='*80}")
        print("Qualitative Comparison")
        print(f"{'='*80}")
        qual_comp = comparison.get("summary", {}).get("qualitative_comparison", {})
        
        print(f"\n{'File':<40} {'Semantic':<12} {'Structure':<12} {'Completeness':<12} {'Average':<12}")
        print("-" * 100)
        for file_name, stats in qual_comp.items():
            avg = (stats.get('semantic_score', 0) + stats.get('structure_score', 0) + stats.get('completeness_score', 0)) / 3
            print(f"{file_name[:40]:<40} {stats.get('semantic_score', 0):>10.2f} {stats.get('structure_score', 0):>10.2f} "
                  f"{stats.get('completeness_score', 0):>10.2f} {avg:>10.2f}")
    
    def save_analysis(self, analysis: Dict[str, Any], output_file: str):
        """
        保存分析结果到文件
        
        Args:
            analysis: 分析结果字典
            output_file: 输出文件路径
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        logger.info(f"Analysis saved to {output_file}")
    
    def collect_cost_statistics(self) -> List[Dict[str, Any]]:
        """
        收集 benchmark 目录下所有测试结果的 token cost 和时间 cost
        
        Returns:
            包含每个测试结果 cost 统计的列表
        """
        cost_stats = []
        
        # 扫描 benchmark 目录下的所有 JSON 文件
        if not self.benchmark_dir.exists():
            logger.warning(f"Benchmark directory not found: {self.benchmark_dir}")
            return cost_stats
        
        # 查找所有结果 JSON 文件（排除 aggregate_table.json）
        json_files = list(self.benchmark_dir.glob("*_results_*.json"))
        
        for json_file in json_files:
            try:
                result_data = self.load_result_file(str(json_file))
                metadata = result_data.get("metadata", {})
                statistics = result_data.get("statistics", {})
                
                # 提取 token 统计
                tokens = statistics.get("tokens", {})
                # 提取时间统计
                timing = statistics.get("timing", {})
                
                # 检查是否有 token 或时间信息
                # 检查 tokens 是否有实际数据（非空字典且包含有效值）
                has_token_info = False
                if tokens and isinstance(tokens, dict):
                    for agent_stats in tokens.values():
                        if isinstance(agent_stats, dict) and agent_stats.get("total_tokens", 0) > 0:
                            has_token_info = True
                            break
                
                # 检查 timing 是否有实际数据
                has_timing_info = False
                if timing and isinstance(timing, dict):
                    timing_total = timing.get("total", {})
                    if timing_total and isinstance(timing_total, dict):
                        for duration in timing_total.values():
                            if isinstance(duration, (int, float)) and duration > 0:
                                has_timing_info = True
                                break
                
                # 如果没有 token cost 和时间 cost，跳过
                if not has_token_info and not has_timing_info:
                    continue
                
                # 计算总 token 数
                total_tokens = 0
                total_prompt_tokens = 0
                total_completion_tokens = 0
                total_cost = 0.0
                
                if tokens:
                    for agent_name, agent_stats in tokens.items():
                        if isinstance(agent_stats, dict):
                            total_tokens += agent_stats.get("total_tokens", 0)
                            total_prompt_tokens += agent_stats.get("prompt_tokens", 0)
                            total_completion_tokens += agent_stats.get("completion_tokens", 0)
                            total_cost += agent_stats.get("total_cost", 0.0)
                
                # 计算总时间
                total_time = 0.0
                avg_time = 0.0
                timing_breakdown = {}
                
                if timing:
                    timing_total = timing.get("total", {})
                    timing_avg = timing.get("average", {})
                    
                    if timing_total:
                        for module, duration in timing_total.items():
                            if isinstance(duration, (int, float)):
                                total_time += duration
                                timing_breakdown[module] = duration
                    
                    if timing_avg:
                        avg_time = sum(timing_avg.values()) if isinstance(timing_avg, dict) else 0.0
                
                # 获取测试用例数量
                results = result_data.get("results", [])
                test_case_count = len(results)
                
                cost_stat = {
                    "file_name": json_file.name,
                    "test_type": metadata.get("test_type", "unknown"),
                    "date": metadata.get("date", "unknown"),
                    "model_name": metadata.get("model_name", "unknown"),
                    "test_case_count": test_case_count,
                    "tokens": {
                        "total_tokens": total_tokens,
                        "total_prompt_tokens": total_prompt_tokens,
                        "total_completion_tokens": total_completion_tokens,
                        "total_cost": total_cost,
                        "avg_tokens_per_case": total_tokens / test_case_count if test_case_count > 0 else 0,
                        "avg_cost_per_case": total_cost / test_case_count if test_case_count > 0 else 0.0
                    },
                    "timing": {
                        "total_time": total_time,
                        "avg_time": avg_time,
                        "avg_time_per_case": total_time / test_case_count if test_case_count > 0 else 0.0,
                        "breakdown": timing_breakdown
                    }
                }
                
                cost_stats.append(cost_stat)
                
            except Exception as e:
                logger.warning(f"Failed to process {json_file}: {e}")
                continue
        
        return cost_stats
    
    def print_cost_statistics(self, cost_stats: List[Dict[str, Any]] = None):
        """
        打印 token cost 和时间 cost 统计表格
        
        Args:
            cost_stats: cost 统计列表，如果为 None 则自动收集
        """
        if cost_stats is None:
            cost_stats = self.collect_cost_statistics()
        
        if not cost_stats:
            print("\nNo cost statistics found in benchmark directory.")
            return
        
        print(f"\n{'='*120}")
        print("Token Cost and Time Cost Statistics")
        print(f"{'='*120}")
        
        # Token Cost 表格
        print(f"\n{'='*120}")
        print("Token Cost Statistics")
        print(f"{'='*120}")
        print(f"{'Test Type':<25} {'Model':<30} {'Test Cases':<12} {'Total Tokens':<15} {'Prompt Tokens':<15} "
              f"{'Completion Tokens':<18} {'Total Cost':<12} {'Avg Tokens/Case':<18} {'Avg Cost/Case':<15}")
        print("-" * 120)
        
        for stat in cost_stats:
            tokens = stat.get("tokens", {})
            test_type = stat.get("test_type", "unknown")
            model_name = stat.get("model_name", "unknown")
            test_case_count = stat.get("test_case_count", 0)
            total_tokens = tokens.get("total_tokens", 0)
            prompt_tokens = tokens.get("total_prompt_tokens", 0)
            completion_tokens = tokens.get("total_completion_tokens", 0)
            total_cost = tokens.get("total_cost", 0.0)
            avg_tokens = tokens.get("avg_tokens_per_case", 0)
            avg_cost = tokens.get("avg_cost_per_case", 0.0)
            
            # 格式化数字
            total_tokens_str = f"{total_tokens:,}" if total_tokens > 0 else "N/A"
            prompt_tokens_str = f"{prompt_tokens:,}" if prompt_tokens > 0 else "N/A"
            completion_tokens_str = f"{completion_tokens:,}" if completion_tokens > 0 else "N/A"
            total_cost_str = f"${total_cost:.4f}" if total_cost > 0 else "N/A"
            avg_tokens_str = f"{avg_tokens:,.0f}" if avg_tokens > 0 else "N/A"
            avg_cost_str = f"${avg_cost:.6f}" if avg_cost > 0 else "N/A"
            
            print(f"{test_type[:24]:<25} {model_name[:29]:<30} {test_case_count:<12} {total_tokens_str:<15} "
                  f"{prompt_tokens_str:<15} {completion_tokens_str:<18} {total_cost_str:<12} "
                  f"{avg_tokens_str:<18} {avg_cost_str:<15}")
        
        # Time Cost 表格
        print(f"\n{'='*120}")
        print("Time Cost Statistics")
        print(f"{'='*120}")
        print(f"{'Test Type':<25} {'Model':<30} {'Test Cases':<12} {'Total Time (s)':<15} {'Avg Time (s)':<15} "
              f"{'Avg Time/Case (s)':<18} {'Knowledge Ext (s)':<18} {'Code Gen (s)':<15} "
              f"{'Debugging (s)':<15} {'Evaluation (s)':<15}")
        print("-" * 120)
        
        for stat in cost_stats:
            timing = stat.get("timing", {})
            test_type = stat.get("test_type", "unknown")
            model_name = stat.get("model_name", "unknown")
            test_case_count = stat.get("test_case_count", 0)
            total_time = timing.get("total_time", 0.0)
            avg_time = timing.get("avg_time", 0.0)
            avg_time_per_case = timing.get("avg_time_per_case", 0.0)
            breakdown = timing.get("breakdown", {})
            
            knowledge_ext = breakdown.get("knowledge_extraction", 0.0)
            code_gen = breakdown.get("code_generation", 0.0)
            debugging = breakdown.get("debugging", 0.0)
            evaluation = breakdown.get("evaluation", 0.0)
            
            # 格式化时间
            total_time_str = f"{total_time:.2f}" if total_time > 0 else "N/A"
            avg_time_str = f"{avg_time:.2f}" if avg_time > 0 else "N/A"
            avg_time_per_case_str = f"{avg_time_per_case:.2f}" if avg_time_per_case > 0 else "N/A"
            knowledge_ext_str = f"{knowledge_ext:.2f}" if knowledge_ext > 0 else "N/A"
            code_gen_str = f"{code_gen:.2f}" if code_gen > 0 else "N/A"
            debugging_str = f"{debugging:.2f}" if debugging > 0 else "N/A"
            evaluation_str = f"{evaluation:.2f}" if evaluation > 0 else "N/A"
            
            print(f"{test_type[:24]:<25} {model_name[:29]:<30} {test_case_count:<12} {total_time_str:<15} "
                  f"{avg_time_str:<15} {avg_time_per_case_str:<18} {knowledge_ext_str:<18} "
                  f"{code_gen_str:<15} {debugging_str:<15} {evaluation_str:<15}")
        
        print(f"\n{'='*120}")
        print(f"Total test results: {len(cost_stats)}")
        print(f"{'='*120}")
    
    def extract_cost_from_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        从指定的文件列表中提取 cost 统计
        
        Args:
            file_paths: 结果文件路径列表
            
        Returns:
            包含每个文件 cost 统计的列表
        """
        cost_stats = []
        
        for file_path in file_paths:
            try:
                # 如果文件路径是相对路径，尝试在 benchmark_dir 中查找
                file_path_obj = Path(file_path)
                if not file_path_obj.is_absolute():
                    # 尝试在 benchmark_dir 中查找
                    potential_path = self.benchmark_dir / file_path_obj
                    if potential_path.exists():
                        file_path_obj = potential_path
                    elif file_path_obj.exists():
                        pass  # 使用原始路径
                    else:
                        logger.warning(f"File not found: {file_path}")
                        continue
                elif not file_path_obj.exists():
                    logger.warning(f"File not found: {file_path}")
                    continue
                
                result_data = self.load_result_file(str(file_path_obj))
                metadata = result_data.get("metadata", {})
                statistics = result_data.get("statistics", {})
                
                # 提取 token 统计
                tokens = statistics.get("tokens", {})
                # 提取时间统计
                timing = statistics.get("timing", {})
                
                # 计算总 token 数
                total_tokens = 0
                total_prompt_tokens = 0
                total_completion_tokens = 0
                total_cost = 0.0
                
                if tokens:
                    for agent_name, agent_stats in tokens.items():
                        if isinstance(agent_stats, dict):
                            total_tokens += agent_stats.get("total_tokens", 0)
                            total_prompt_tokens += agent_stats.get("prompt_tokens", 0)
                            total_completion_tokens += agent_stats.get("completion_tokens", 0)
                            total_cost += agent_stats.get("total_cost", 0.0)
                
                # 计算总时间
                total_time = 0.0
                avg_time = 0.0
                timing_breakdown = {}
                
                if timing:
                    timing_total = timing.get("total", {})
                    timing_avg = timing.get("average", {})
                    
                    if timing_total:
                        for module, duration in timing_total.items():
                            if isinstance(duration, (int, float)):
                                total_time += duration
                                timing_breakdown[module] = duration
                    
                    if timing_avg:
                        avg_time = sum(timing_avg.values()) if isinstance(timing_avg, dict) else 0.0
                
                # 获取测试用例数量
                results = result_data.get("results", [])
                test_case_count = len(results)
                
                cost_stat = {
                    "file_name": file_path_obj.name,
                    "file_path": str(file_path_obj),
                    "test_type": metadata.get("test_type", "unknown"),
                    "date": metadata.get("date", "unknown"),
                    "model_name": metadata.get("model_name", "unknown"),
                    "test_case_count": test_case_count,
                    "tokens": {
                        "total_tokens": total_tokens,
                        "total_prompt_tokens": total_prompt_tokens,
                        "total_completion_tokens": total_completion_tokens,
                        "total_cost": total_cost,
                        "avg_tokens_per_case": total_tokens / test_case_count if test_case_count > 0 else 0,
                        "avg_cost_per_case": total_cost / test_case_count if test_case_count > 0 else 0.0,
                        "by_agent": tokens if tokens else {}
                    },
                    "timing": {
                        "total_time": total_time,
                        "avg_time": avg_time,
                        "avg_time_per_case": total_time / test_case_count if test_case_count > 0 else 0.0,
                        "breakdown": timing_breakdown
                    }
                }
                
                cost_stats.append(cost_stat)
                
            except Exception as e:
                logger.warning(f"Failed to process {file_path}: {e}")
                continue
        
        return cost_stats
    
    def save_cost_statistics_to_file(self, cost_stats: List[Dict[str, Any]], output_file: str):
        """
        将 cost 统计保存到文本文件
        
        Args:
            cost_stats: cost 统计列表
            output_file: 输出文件路径
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 120 + "\n")
            f.write("Token Cost and Time Cost Statistics\n")
            f.write("=" * 120 + "\n\n")
            
            # Token Cost 表格
            f.write("=" * 120 + "\n")
            f.write("Token Cost Statistics\n")
            f.write("=" * 120 + "\n")
            f.write(f"{'Test Type':<25} {'Model':<30} {'Test Cases':<12} {'Total Tokens':<15} {'Prompt Tokens':<15} "
                    f"{'Completion Tokens':<18} {'Total Cost':<12} {'Avg Tokens/Case':<18} {'Avg Cost/Case':<15}\n")
            f.write("-" * 120 + "\n")
            
            for stat in cost_stats:
                tokens = stat.get("tokens", {})
                test_type = stat.get("test_type", "unknown")
                model_name = stat.get("model_name", "unknown")
                test_case_count = stat.get("test_case_count", 0)
                total_tokens = tokens.get("total_tokens", 0)
                prompt_tokens = tokens.get("total_prompt_tokens", 0)
                completion_tokens = tokens.get("total_completion_tokens", 0)
                total_cost = tokens.get("total_cost", 0.0)
                avg_tokens = tokens.get("avg_tokens_per_case", 0)
                avg_cost = tokens.get("avg_cost_per_case", 0.0)
                
                # 格式化数字
                total_tokens_str = f"{total_tokens:,}" if total_tokens > 0 else "N/A"
                prompt_tokens_str = f"{prompt_tokens:,}" if prompt_tokens > 0 else "N/A"
                completion_tokens_str = f"{completion_tokens:,}" if completion_tokens > 0 else "N/A"
                total_cost_str = f"${total_cost:.4f}" if total_cost > 0 else "N/A"
                avg_tokens_str = f"{avg_tokens:,.0f}" if avg_tokens > 0 else "N/A"
                avg_cost_str = f"${avg_cost:.6f}" if avg_cost > 0 else "N/A"
                
                f.write(f"{test_type[:24]:<25} {model_name[:29]:<30} {test_case_count:<12} {total_tokens_str:<15} "
                        f"{prompt_tokens_str:<15} {completion_tokens_str:<18} {total_cost_str:<12} "
                        f"{avg_tokens_str:<18} {avg_cost_str:<15}\n")
            
            # Time Cost 表格
            f.write("\n" + "=" * 120 + "\n")
            f.write("Time Cost Statistics\n")
            f.write("=" * 120 + "\n")
            f.write(f"{'Test Type':<25} {'Model':<30} {'Test Cases':<12} {'Total Time (s)':<15} {'Avg Time (s)':<15} "
                    f"{'Avg Time/Case (s)':<18} {'Knowledge Ext (s)':<18} {'Code Gen (s)':<15} "
                    f"{'Debugging (s)':<15} {'Evaluation (s)':<15}\n")
            f.write("-" * 120 + "\n")
            
            for stat in cost_stats:
                timing = stat.get("timing", {})
                test_type = stat.get("test_type", "unknown")
                model_name = stat.get("model_name", "unknown")
                test_case_count = stat.get("test_case_count", 0)
                total_time = timing.get("total_time", 0.0)
                avg_time = timing.get("avg_time", 0.0)
                avg_time_per_case = timing.get("avg_time_per_case", 0.0)
                breakdown = timing.get("breakdown", {})
                
                knowledge_ext = breakdown.get("knowledge_extraction", 0.0)
                code_gen = breakdown.get("code_generation", 0.0)
                debugging = breakdown.get("debugging", 0.0)
                evaluation = breakdown.get("evaluation", 0.0)
                
                # 格式化时间
                total_time_str = f"{total_time:.2f}" if total_time > 0 else "N/A"
                avg_time_str = f"{avg_time:.2f}" if avg_time > 0 else "N/A"
                avg_time_per_case_str = f"{avg_time_per_case:.2f}" if avg_time_per_case > 0 else "N/A"
                knowledge_ext_str = f"{knowledge_ext:.2f}" if knowledge_ext > 0 else "N/A"
                code_gen_str = f"{code_gen:.2f}" if code_gen > 0 else "N/A"
                debugging_str = f"{debugging:.2f}" if debugging > 0 else "N/A"
                evaluation_str = f"{evaluation:.2f}" if evaluation > 0 else "N/A"
                
                f.write(f"{test_type[:24]:<25} {model_name[:29]:<30} {test_case_count:<12} {total_time_str:<15} "
                        f"{avg_time_str:<15} {avg_time_per_case_str:<18} {knowledge_ext_str:<18} "
                        f"{code_gen_str:<15} {debugging_str:<15} {evaluation_str:<15}\n")
            
            # 详细信息
            f.write("\n" + "=" * 120 + "\n")
            f.write("Detailed Information\n")
            f.write("=" * 120 + "\n\n")
            
            for stat in cost_stats:
                f.write(f"File: {stat.get('file_name', 'unknown')}\n")
                f.write(f"  Test Type: {stat.get('test_type', 'unknown')}\n")
                f.write(f"  Model: {stat.get('model_name', 'unknown')}\n")
                f.write(f"  Date: {stat.get('date', 'unknown')}\n")
                f.write(f"  Test Cases: {stat.get('test_case_count', 0)}\n\n")
                
                # Token 详细信息
                tokens = stat.get("tokens", {})
                tokens_by_agent = tokens.get("by_agent", {})
                if tokens_by_agent:
                    f.write("  Token Statistics by Agent:\n")
                    for agent_name, agent_stats in tokens_by_agent.items():
                        if isinstance(agent_stats, dict):
                            f.write(f"    {agent_name}:\n")
                            f.write(f"      Total Tokens: {agent_stats.get('total_tokens', 0):,}\n")
                            f.write(f"      Prompt Tokens: {agent_stats.get('prompt_tokens', 0):,}\n")
                            f.write(f"      Completion Tokens: {agent_stats.get('completion_tokens', 0):,}\n")
                            f.write(f"      Cost: ${agent_stats.get('total_cost', 0.0):.4f}\n")
                    f.write("\n")
                
                # 时间详细信息
                timing = stat.get("timing", {})
                breakdown = timing.get("breakdown", {})
                if breakdown:
                    f.write("  Time Breakdown:\n")
                    for module, duration in breakdown.items():
                        f.write(f"    {module}: {duration:.2f} seconds\n")
                    f.write("\n")
                
                f.write("-" * 120 + "\n\n")
            
            f.write(f"Total test results: {len(cost_stats)}\n")
        
        logger.info(f"Cost statistics saved to {output_file}")
    
    def find_all_result_files(self, must_contain: Optional[str] = None, filter_list: List[str] = None) -> List[Path]:
        """
        查找 benchmark 目录下所有结果数据文件
        
        匹配 *_results_*.json，排除 aggregate_table*.json 等汇总文件
        
        Returns:
            结果文件路径列表
        """
        if not self.benchmark_dir.exists():
            logger.warning(f"Benchmark directory not found: {self.benchmark_dir}")
            return []
        
        result_files = []
        for f in self.benchmark_dir.glob("*_results_*.json"):
            if f.name.startswith("aggregate_table") or f.name.startswith("aggregated_results"):
                continue
            if must_contain and must_contain not in f.name:
                continue
            if filter_list and not any(filter_item in f.name for filter_item in filter_list):
                continue
            result_files.append(f)
        result_files.sort()
        return result_files
    
    def find_desc_result_files(self) -> List[Path]:
        """
        查找 benchmark 目录下以 Desc 开头的结果数据文件
        
        Returns:
            以 Desc 开头的结果文件路径列表
        """
        if not self.benchmark_dir.exists():
            logger.warning(f"Benchmark directory not found: {self.benchmark_dir}")
            return []
        
        # 匹配 Desc 开头且包含 _results_ 的 JSON 文件
        result_files = list(self.benchmark_dir.glob("Desc*_results_*.json"))
        result_files.sort()
        return result_files
    
    def aggregate_all_results(self, output_base: str = "aggregate_table", must_contain: str = None, filter_list: List[str] = None) -> Dict[str, Any]:
        """
        分析与汇总 benchmark 目录下所有结果数据文件，生成 aggregate_table
        
        Args:
            output_base: 输出文件基础名（不含扩展名），将生成 {output_base}.json
            must_contain: 必须包含的字符串，用于过滤结果文件
            filter_list: 过滤列表，用于过滤结果文件
        Returns:
            汇总结果字典
        """
        result_files = self.find_all_result_files(must_contain=must_contain, filter_list=filter_list)
        
        if not result_files:
            logger.warning(f"No result files found in {self.benchmark_dir}")
            return {}
        
        logger.info(f"Found {len(result_files)} result files:")
        for f in result_files:
            logger.info(f"  - {f.name}")
        
        return self._do_aggregate(result_files, output_base, filter_name=None)
    
    def aggregate_desc_results(self, output_base: str = "aggregate_table_Desc") -> Dict[str, Any]:
        """
        分析与汇总以 Desc 开头的数据文件，生成 aggregate_table
        
        Args:
            output_base: 输出文件基础名（不含扩展名），将生成 {output_base}.json
            
        Returns:
            汇总结果字典
        """
        result_files = self.find_desc_result_files()
        
        if not result_files:
            logger.warning(f"No Desc-prefixed result files found in {self.benchmark_dir}")
            return {}
        
        logger.info(f"Found {len(result_files)} Desc result files:")
        for f in result_files:
            logger.info(f"  - {f.name}")
        
        return self._do_aggregate(result_files, output_base, filter_name="Desc")
    
    def _extract_cost_from_result(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """从单个结果文件中提取 token 和时间统计"""
        statistics = result_data.get("statistics", {})
        tokens_raw = statistics.get("tokens", {})
        timing_raw = statistics.get("timing", {})
        results = result_data.get("results", [])
        test_case_count = len(results)
        
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost = 0.0
        if tokens_raw and isinstance(tokens_raw, dict):
            for agent_stats in tokens_raw.values():
                if isinstance(agent_stats, dict):
                    total_tokens += agent_stats.get("total_tokens", 0)
                    total_prompt_tokens += agent_stats.get("prompt_tokens", 0)
                    total_completion_tokens += agent_stats.get("completion_tokens", 0)
                    total_cost += agent_stats.get("total_cost", 0.0)
        
        total_time = 0.0
        timing_breakdown = {}
        if timing_raw and isinstance(timing_raw, dict):
            timing_total = timing_raw.get("total", {})
            if timing_total and isinstance(timing_total, dict):
                for module, duration in timing_total.items():
                    if isinstance(duration, (int, float)):
                        total_time += duration
                        timing_breakdown[module] = duration
        
        return {
            "tokens": {
                "total_tokens": total_tokens,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_cost": total_cost,
                "avg_tokens_per_case": total_tokens / test_case_count if test_case_count > 0 else 0,
                "avg_cost_per_case": total_cost / test_case_count if test_case_count > 0 else 0.0,
            },
            "timing": {
                "total_time": total_time,
                "avg_time_per_case": total_time / test_case_count if test_case_count > 0 else 0.0,
                "breakdown": timing_breakdown,
            },
            "test_case_count": test_case_count,
        }
    
    def _do_aggregate(
        self,
        result_files: List[Path],
        output_base: str,
        filter_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """内部方法：对结果文件列表进行汇总"""
        all_summaries = []
        all_analyses = {}
        
        for result_file in result_files:
            try:
                result_data = self.load_result_file(str(result_file))
                analysis = self.analyze_single_result(result_data)
                cost_info = self._extract_cost_from_result(result_data)
                
                file_name = result_file.stem
                all_analyses[file_name] = analysis
                
                metadata = analysis.get("metadata", {})
                avg_quant = analysis.get("average_quantitative", {})
                avg_qual = analysis.get("average_qualitative", {})
                
                summary = {
                    "file_name": result_file.name,
                    "test_type": metadata.get("test_type", "unknown"),
                    "date": metadata.get("date", "unknown"),
                    "model_name": metadata.get("model_name", "unknown"),
                    "total_cases": analysis.get("total_cases", 0),
                    "valid_cases": analysis.get("valid_cases", 0),
                    "tokens": cost_info["tokens"],
                    "timing": cost_info["timing"],
                    "quantitative": {
                        "function_reuse_rate": avg_quant.get("function_reuse_rate", 0),
                        "variable_reuse_rate": avg_quant.get("variable_reuse_rate", 0),
                        "avg_correctly_reused_functions": avg_quant.get("correctly_reused_functions", 0),
                        "avg_incorrectly_constructed_functions": avg_quant.get("incorrectly_constructed_functions", 0),
                        "avg_total_reference_functions": avg_quant.get("total_reference_functions", 0),
                        "avg_correctly_reused_variables": avg_quant.get("correctly_reused_variables", 0),
                        "avg_incorrectly_constructed_variables": avg_quant.get("incorrectly_constructed_variables", 0),
                        "avg_total_reference_variables": avg_quant.get("total_reference_variables", 0),
                    },
                    "qualitative": {
                        "semantic_score": avg_qual.get("semantic_score", 0),
                        "structure_score": avg_qual.get("structure_score", 0),
                        "completeness_score": avg_qual.get("completeness_score", 0),
                        "overall_average": (
                            avg_qual.get("semantic_score", 0)
                            + avg_qual.get("structure_score", 0)
                            + avg_qual.get("completeness_score", 0)
                        ) / 3 if avg_qual else 0,
                    },
                }
                all_summaries.append(summary)
                
            except Exception as e:
                logger.warning(f"Failed to analyze {result_file.name}: {e}")
                continue
        
        if not all_summaries:
            logger.warning("No valid summaries generated")
            return {}
        
        total_cases = sum(s["total_cases"] for s in all_summaries)
        total_valid_cases = sum(s["valid_cases"] for s in all_summaries)
        
        by_test_type = defaultdict(list)
        for summary in all_summaries:
            by_test_type[summary["test_type"]].append(summary)
        
        def _sum_tokens(s_list):
            return sum(s.get("tokens", {}).get("total_tokens", 0) for s in s_list)

        def _sum_cost(s_list):
            return sum(s.get("tokens", {}).get("total_cost", 0.0) for s in s_list)

        def _sum_time(s_list):
            return sum(s.get("timing", {}).get("total_time", 0.0) for s in s_list)

        def _sum_cases(s_list):
            return sum(s.get("total_cases", 0) for s in s_list)

        type_averages = {}
        for test_type, summaries in by_test_type.items():
            if summaries:
                type_cases = _sum_cases(summaries)
                type_tokens = _sum_tokens(summaries)
                type_time = _sum_time(summaries)
                type_cost = _sum_cost(summaries)
                type_averages[test_type] = {
                    "count": len(summaries),
                    "avg_function_reuse_rate": sum(s["quantitative"]["function_reuse_rate"] for s in summaries) / len(summaries),
                    "avg_variable_reuse_rate": sum(s["quantitative"]["variable_reuse_rate"] for s in summaries) / len(summaries),
                    "avg_correctly_reused_functions": sum(s["quantitative"].get("avg_correctly_reused_functions", 0) for s in summaries) / len(summaries),
                    "avg_correctly_reused_variables": sum(s["quantitative"].get("avg_correctly_reused_variables", 0) for s in summaries) / len(summaries),
                    "avg_incorrectly_constructed_functions": sum(s["quantitative"].get("avg_incorrectly_constructed_functions", 0) for s in summaries) / len(summaries),
                    "avg_incorrectly_constructed_variables": sum(s["quantitative"].get("avg_incorrectly_constructed_variables", 0) for s in summaries) / len(summaries),
                    "avg_semantic_score": sum(s["qualitative"]["semantic_score"] for s in summaries) / len(summaries),
                    "avg_structure_score": sum(s["qualitative"]["structure_score"] for s in summaries) / len(summaries),
                    "avg_completeness_score": sum(s["qualitative"]["completeness_score"] for s in summaries) / len(summaries),
                    "avg_overall_score": sum(s["qualitative"]["overall_average"] for s in summaries) / len(summaries),
                    "total_tokens": type_tokens,
                    "total_cost": type_cost,
                    "total_time": type_time,
                    "avg_tokens_per_case": type_tokens / type_cases if type_cases > 0 else 0,
                    "avg_time_per_case": type_time / type_cases if type_cases > 0 else 0,
                }
        
        total_tokens_all = _sum_tokens(all_summaries)
        total_cost_all = _sum_cost(all_summaries)
        total_time_all = _sum_time(all_summaries)
        n = len(all_summaries)
        global_averages = {
            "avg_function_reuse_rate": sum(s["quantitative"]["function_reuse_rate"] for s in all_summaries) / n,
            "avg_variable_reuse_rate": sum(s["quantitative"]["variable_reuse_rate"] for s in all_summaries) / n,
            "avg_correctly_reused_functions": sum(s["quantitative"].get("avg_correctly_reused_functions", 0) for s in all_summaries) / n,
            "avg_correctly_reused_variables": sum(s["quantitative"].get("avg_correctly_reused_variables", 0) for s in all_summaries) / n,
            "avg_incorrectly_constructed_functions": sum(s["quantitative"].get("avg_incorrectly_constructed_functions", 0) for s in all_summaries) / n,
            "avg_incorrectly_constructed_variables": sum(s["quantitative"].get("avg_incorrectly_constructed_variables", 0) for s in all_summaries) / n,
            "avg_semantic_score": sum(s["qualitative"]["semantic_score"] for s in all_summaries) / n,
            "avg_structure_score": sum(s["qualitative"]["structure_score"] for s in all_summaries) / n,
            "avg_completeness_score": sum(s["qualitative"]["completeness_score"] for s in all_summaries) / n,
            "avg_overall_score": sum(s["qualitative"]["overall_average"] for s in all_summaries) / n,
            "total_tokens": total_tokens_all,
            "total_cost": total_cost_all,
            "total_time": total_time_all,
            "avg_tokens_per_case": total_tokens_all / total_cases if total_cases > 0 else 0,
            "avg_time_per_case": total_time_all / total_cases if total_cases > 0 else 0,
        }
        
        metadata_filter = {"filter": filter_name} if filter_name else {}
        aggregated_result = {
            "metadata": {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_files": len(result_files),
                "total_cases": total_cases,
                "total_valid_cases": total_valid_cases,
                "total_tokens": total_tokens_all,
                "total_cost": total_cost_all,
                "total_time": total_time_all,
                "benchmark_dir": str(self.benchmark_dir.absolute()),
                **metadata_filter,
            },
            "global_statistics": global_averages,
            "statistics_by_test_type": type_averages,
            "summaries": all_summaries,
            "detailed_analyses": all_analyses,
        }
        
        output_json = self.benchmark_dir / f"{output_base}.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(aggregated_result, f, ensure_ascii=False, indent=2)
        logger.info(f"Aggregate table saved to {output_json}")
        
        return aggregated_result


def _print_aggregate_table(aggregated: Dict[str, Any], title: str = "Aggregate Summary Table"):
    """打印汇总表格"""
    summaries = aggregated.get("summaries", [])
    if not summaries:
        return
    print(f"\n{'='*110}")
    print(title)
    print(f"{'='*110}")
    header = f"{'File Name':<45} {'Test Type':<18} {'Func Reuse %':<14} {'Var Reuse %':<14} {'Semantic':<10} {'Structure':<10} {'Complete':<10} {'Overall':<10}"
    print(header)
    print("-" * 110)
    for s in summaries:
        print(f"{s['file_name'][:43]:<45} {s['test_type'][:16]:<18} "
              f"{s['quantitative']['function_reuse_rate']:>12.2f}% "
              f"{s['quantitative']['variable_reuse_rate']:>12.2f}% "
              f"{s['qualitative']['semantic_score']:>8.2f} "
              f"{s['qualitative']['structure_score']:>8.2f} "
              f"{s['qualitative']['completeness_score']:>8.2f} "
              f"{s['qualitative']['overall_average']:>8.2f}")
    gs = aggregated.get("global_statistics", {})
    if gs:
        print("-" * 110)
        print(f"{'GLOBAL AVERAGE':<45} {'':<18} "
              f"{gs.get('avg_function_reuse_rate', 0):>12.2f}% "
              f"{gs.get('avg_variable_reuse_rate', 0):>12.2f}% "
              f"{gs.get('avg_semantic_score', 0):>8.2f} "
              f"{gs.get('avg_structure_score', 0):>8.2f} "
              f"{gs.get('avg_completeness_score', 0):>8.2f} "
              f"{gs.get('avg_overall_score', 0):>8.2f}")

    # 正确/错误复用统计表格
    print(f"\n{'='*110}")
    print("正确/错误复用统计 (Correct/Incorrect Reuse Averages)")
    print(f"{'='*110}")
    reuse_hdr = (f"{'File Name':<45} {'Test Type':<18} {'Corr Func':<12} {'Corr Var':<12} "
                 f"{'Incorr Func':<12} {'Incorr Var':<12}")
    print(reuse_hdr)
    print("-" * 110)
    for s in summaries:
        q = s.get("quantitative", {})
        corr_f = q.get("avg_correctly_reused_functions", 0)
        corr_v = q.get("avg_correctly_reused_variables", 0)
        inc_f = q.get("avg_incorrectly_constructed_functions", 0)
        inc_v = q.get("avg_incorrectly_constructed_variables", 0)
        print(f"{s['file_name'][:43]:<45} {s['test_type'][:16]:<18} "
              f"{corr_f:>10.2f} {corr_v:>10.2f} {inc_f:>10.2f} {inc_v:>10.2f}")
    if gs:
        print("-" * 110)
        print(f"{'GLOBAL AVERAGE':<45} {'':<18} "
              f"{gs.get('avg_correctly_reused_functions', 0):>10.2f} "
              f"{gs.get('avg_correctly_reused_variables', 0):>10.2f} "
              f"{gs.get('avg_incorrectly_constructed_functions', 0):>10.2f} "
              f"{gs.get('avg_incorrectly_constructed_variables', 0):>10.2f}")

    # Token 与时间统计表格
    print(f"\n{'='*110}")
    print("Token 与时间统计 (Token & Time Statistics)")
    print(f"{'='*110}")
    thdr = f"{'File Name':<45} {'Test Type':<18} {'Total Tokens':<16} {'Total Cost':<14} {'Total Time(s)':<16} {'Tokens/Case':<14} {'Time/Case(s)':<14}"
    print(thdr)
    print("-" * 110)
    for s in summaries:
        tok = s.get("tokens", {})
        tim = s.get("timing", {})
        total_tok = tok.get("total_tokens", 0)
        total_cost = tok.get("total_cost", 0.0)
        total_time = tim.get("total_time", 0.0)
        tok_per = tok.get("avg_tokens_per_case", 0)
        time_per = tim.get("avg_time_per_case", 0.0)
        total_tok_str = f"{total_tok:,}" if total_tok else "N/A"
        total_cost_str = f"${total_cost:.4f}" if total_cost else "N/A"
        total_time_str = f"{total_time:.1f}" if total_time else "N/A"
        tok_per_str = f"{tok_per:,.0f}" if tok_per else "N/A"
        time_per_str = f"{time_per:.2f}" if time_per else "N/A"
        print(f"{s['file_name'][:43]:<45} {s['test_type'][:16]:<18} {total_tok_str:<16} {total_cost_str:<14} "
              f"{total_time_str:<16} {tok_per_str:<14} {time_per_str:<14}")
    if gs:
        total_tok = gs.get("total_tokens", 0)
        total_cost = gs.get("total_cost", 0.0)
        total_time = gs.get("total_time", 0.0)
        tok_per = gs.get("avg_tokens_per_case", 0)
        time_per = gs.get("avg_time_per_case", 0.0)
        print("-" * 110)
        print(f"{'GLOBAL TOTAL/AVG':<45} {'':<18} "
              f"{(f'{total_tok:,}' if total_tok else 'N/A'):<16} "
              f"{(f'${total_cost:.4f}' if total_cost else 'N/A'):<14} "
              f"{(f'{total_time:.1f}' if total_time else 'N/A'):<16} "
              f"{(f'{tok_per:,.0f}' if tok_per else 'N/A'):<14} "
              f"{(f'{time_per:.2f}' if time_per else 'N/A'):<14}")

    meta = aggregated.get("metadata", {})
    total_tok_meta = meta.get("total_tokens", 0)
    total_time_meta = meta.get("total_time", 0)
    total_cost_meta = meta.get("total_cost", 0.0)
    tok_info = f", 总 Token: {total_tok_meta:,}" if total_tok_meta else ""
    time_info = f", 总耗时: {total_time_meta:.1f}s" if total_time_meta else ""
    cost_info = f", 总成本: ${total_cost_meta:.4f}" if total_cost_meta else ""
    print(f"\n汇总说明: 共 {meta.get('total_files', 0)} 个文件, {meta.get('total_cases', 0)} 个用例, "
          f"{meta.get('total_valid_cases', 0)} 个有效用例{tok_info}{time_info}{cost_info}")


def main():
    """主函数：展示 benchmark 结果"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Show and compare benchmark results")
    parser.add_argument("result_files", nargs="*", help="Result JSON files to analyze")
    parser.add_argument("--compare", action="store_true", help="Compare multiple result files")
    parser.add_argument("--detailed", action="store_true", help="Show detailed statistics")
    parser.add_argument("--output", type=str, help="Output file path for analysis results")
    parser.add_argument("--benchmark-dir", type=str, default="evox-server/.rag/benchmark",
                        help="Benchmark directory")
    parser.add_argument("--cost-stats", action="store_true", 
                        help="Show token cost and time cost statistics for all results in benchmark directory")
    parser.add_argument("--extract-cost", action="store_true",
                        help="Extract cost statistics from specified result files and save to output file")
    parser.add_argument("--desc-aggregate", action="store_true",
                        help="Analyze and aggregate Desc-prefixed result files, save to aggregate_table_Desc.json")
    parser.add_argument("--aggregate-all", action="store_true",
                        help="Aggregate ALL result files in benchmark directory, save to aggregate_table.json")
    parser.add_argument("--keyword", type=str, help="Keyword to filter result files")
    args = parser.parse_args()
    
    show = BenchmarkShow(benchmark_dir=args.benchmark_dir)
    
    filter_list = None
    filter_list = [
        # without 96
        "02_28_14_31", "02_28_14_50",
        # without 168
        "02_25_21_44", "02_25_14_58",
        # tools 96
        "02_28_03_17", "02_28_01_23",
        # tools 168
        "02_27_09_10", "02_27_06_07",
        # local 96
        "02_27_22_08", "02_27_21_48",
        # local 168
        "02_26_16_17", "02_27_00_06",
        # eg 96
        "02_27_23_04", "02_27_22_32",
        # eg 168
        "02_27_20_32", "02_27_19_28",
        # a3 96
        "03_01_19_31", "02_27_15_27",
        # a3 168
        "02_27_01_24", "02_26_23_18",
        # SRP 96
        "03_01_17_37", "03_01_16_12",
        # SRP 168
        "03_01_21_51", "03_01_20_13",
    ]
    # filter_list = [
    #     "02_27_22_08",
    #     "02_28_03_17",
    #     "02_27_23_04",
    #     "02_24_12_48",
    #     "02_27_21_48",
    #     "02_28_01_23",
    #     "02_27_22_32",
    #     "02_24_16",
    # ]
    # 如果指定了 --aggregate-all，汇总 benchmark 目录下全部结果文件
    if args.aggregate_all and args.keyword:
        aggregated = show.aggregate_all_results(output_base=f"aggregate_table_{args.keyword}", must_contain=args.keyword)

        if aggregated:
            _print_aggregate_table(aggregated, title=f"{args.keyword} Results Aggregate Summary")
            if args.output:
                show.save_analysis(aggregated, f"{args.output}_{args.keyword}.json")
        return
    if args.aggregate_all:
        aggregated = show.aggregate_all_results(output_base="aggregate_table", filter_list=filter_list)
        if aggregated:
            _print_aggregate_table(aggregated, title="Aggregate Summary Table")
            if args.output:
                show.save_analysis(aggregated, args.output)
        return
    
    # 如果指定了 --desc-aggregate，分析并汇总 Desc 开头的数据文件
    if args.desc_aggregate:
        aggregated = show.aggregate_desc_results(output_base="aggregate_table_Desc")
        if aggregated:
            _print_aggregate_table(aggregated, title="Desc Aggregate Summary Table")
            if args.output:
                show.save_analysis(aggregated, args.output)
        return
    
    # 如果指定了 --extract-cost，提取指定文件的 cost 统计
    if args.extract_cost:
        if not args.result_files:
            logger.error("Please specify result files to extract cost statistics from")
            parser.print_help()
            return
        
        if not args.output:
            logger.error("Please specify output file with --output")
            parser.print_help()
            return
        
        cost_stats = show.extract_cost_from_files(args.result_files)
        if cost_stats:
            show.print_cost_statistics(cost_stats)
            show.save_cost_statistics_to_file(cost_stats, args.output)
            # 同时保存 JSON 格式
            json_output = Path(args.output)
            if json_output.suffix != '.json':
                json_output = json_output.with_suffix('.json')
            show.save_analysis({"cost_statistics": cost_stats}, str(json_output))
        else:
            logger.warning("No cost statistics extracted from specified files")
        return
    
    # 如果指定了 --cost-stats，显示 cost 统计
    if args.cost_stats:
        cost_stats = show.collect_cost_statistics()
        show.print_cost_statistics(cost_stats)
        
        if args.output:
            show.save_analysis({"cost_statistics": cost_stats}, args.output)
        return
    
    # 如果没有提供 result_files，提示用户
    if not args.result_files:
        parser.print_help()
        return
    
    if args.compare and len(args.result_files) > 1:
        # 比较多个文件
        comparison = show.compare_results(args.result_files)
        show.print_comparison(comparison)
        
        if args.output:
            show.save_analysis(comparison, args.output)
    else:
        # 分析单个或多个文件（不比较）
        for result_file in args.result_files:
            result_data = show.load_result_file(result_file)
            analysis = show.analyze_single_result(result_data)
            show.print_analysis(analysis, detailed=args.detailed)
            
            if args.output:
                output_path = Path(args.output)
                if len(args.result_files) > 1:
                    # 多个文件时，为每个文件生成单独的输出
                    output_path = output_path.parent / f"{output_path.stem}_{Path(result_file).stem}{output_path.suffix}"
                show.save_analysis(analysis, str(output_path))


if __name__ == "__main__":
    main()

