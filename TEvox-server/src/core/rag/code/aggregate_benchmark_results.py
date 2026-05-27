"""
汇总所有 benchmark 结果文件

遍历 evox-server/.rag/benchmark 文件夹下的所有测试结果文件，
分析每个文件并将汇总结果保存到新文件中。

独立脚本，不依赖外部模块。
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from collections import defaultdict


def find_all_result_files(benchmark_dir: str = "evox-server/.rag/benchmark") -> List[Path]:
    """
    查找所有结果文件
    
    Args:
        benchmark_dir: benchmark 文件夹路径
        
    Returns:
        结果文件路径列表
    """
    # 先尝试从当前工作目录
    cwd = Path.cwd()
    benchmark_path = cwd / benchmark_dir
    if not benchmark_path.exists():
        # 如果当前目录是 evox-server，尝试直接使用 .rag/benchmark
        if cwd.name == "evox-server":
            benchmark_path = cwd / ".rag" / "benchmark"
        # 如果当前目录是项目根目录，使用 evox-server/.rag/benchmark
        elif (cwd / "evox-server").exists():
            benchmark_path = cwd / "evox-server" / ".rag" / "benchmark"
        # 尝试从脚本所在目录向上查找
        if not benchmark_path.exists():
            script_dir = Path(__file__).parent
            # 从 src/core/rag/code 向上到项目根目录
            for _ in range(4):
                script_dir = script_dir.parent
                test_path = script_dir / benchmark_dir
                if test_path.exists():
                    benchmark_path = test_path
                    break
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Benchmark directory not found: {benchmark_dir}. Current dir: {cwd}")
    
    # 查找所有 *_results_*.json 文件
    result_files = list(benchmark_path.glob("*_results_*.json"))
    
    # 按文件名排序
    result_files.sort()
    
    return result_files


def filter_placeholders(items):
    """过滤掉占位符值"""
    if not isinstance(items, list):
        return []
    filtered = []
    placeholder_values = {"<none>", "none", "(none)", "n/a", "N/A", "null", "NULL", ""}
    for item in items:
        if item is None:
            continue
        if isinstance(item, str):
            item_lower = item.strip().lower()
            if item and item_lower not in placeholder_values:
                filtered.append(item)
        else:
            filtered.append(item)
    return filtered


def extract_quantitative_stats(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """从评估结果中提取定量统计信息"""
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
    
    correctly_functions = filter_placeholders(correctly_reused.get("functions", []))
    correctly_variables = filter_placeholders(correctly_reused.get("variables", []))
    incorrect_functions = filter_placeholders(incorrectly_constructed.get("functions", []))
    incorrect_variables = filter_placeholders(incorrectly_constructed.get("variables", []))
    
    total_reference_functions = len(correctly_functions) + len(incorrect_functions)
    total_reference_variables = len(correctly_variables) + len(incorrect_variables)
    
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
        "variable_reuse_rate": variable_reuse_rate
    }


def extract_qualitative_stats(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """从评估结果中提取定性统计信息"""
    qualitative = evaluation.get("qualitative", {})
    if not qualitative:
        return {
            "semantic_score": 0,
            "structure_score": 0,
            "completeness_score": 0
        }
    
    return {
        "semantic_score": qualitative.get("semantic_score", 0),
        "structure_score": qualitative.get("structure_score", 0),
        "completeness_score": qualitative.get("completeness_score", 0)
    }


def load_result_file(result_file_path: str) -> Dict[str, Any]:
    """加载结果 JSON 文件，支持两种格式"""
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
        return {
            "metadata": data.get("metadata", {}),
            "statistics": data.get("statistics", {}),
            "results": data.get("results", [])
        }
    else:
        raise ValueError(f"Unexpected data format: {type(data)}")


def analyze_single_result(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """分析单个结果文件"""
    metadata = result_data.get("metadata", {})
    results = result_data.get("results", [])
    
    quantitative_stats_list = []
    qualitative_stats_list = []
    
    for result in results:
        evaluation = result.get("evaluation", {})
        if not evaluation or "error" in evaluation or not isinstance(evaluation, dict):
            continue
        
        quant_stats = extract_quantitative_stats(evaluation)
        qual_stats = extract_qualitative_stats(evaluation)
        
        quantitative_stats_list.append(quant_stats)
        qualitative_stats_list.append(qual_stats)
    
    # 计算平均值
    def calc_avg_quant(stats_list):
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
    
    def calc_avg_qual(stats_list):
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
    
    return {
        "metadata": metadata,
        "total_cases": len(results),
        "valid_cases": len(quantitative_stats_list),
        "average_quantitative": calc_avg_quant(quantitative_stats_list),
        "average_qualitative": calc_avg_qual(qualitative_stats_list)
    }


def aggregate_all_results(benchmark_dir: str = "evox-server/.rag/benchmark", 
                         output_file: str = None) -> Dict[str, Any]:
    """
    汇总所有结果文件
    
    Args:
        benchmark_dir: benchmark 文件夹路径
        output_file: 输出文件路径，如果为 None 则自动生成
        
    Returns:
        汇总结果字典
    """
    result_files = find_all_result_files(benchmark_dir)
    
    if not result_files:
        print(f"No result files found in {benchmark_dir}")
        return {}
    
    print(f"Found {len(result_files)} result files:")
    for f in result_files:
        print(f"  - {f.name}")
    
    all_analyses = {}
    all_summaries = []
    
    # 分析每个文件
    for result_file in result_files:
        print(f"\n{'='*80}")
        print(f"Analyzing: {result_file.name}")
        print(f"{'='*80}")
        
        try:
            result_data = load_result_file(str(result_file))
            analysis = analyze_single_result(result_data)
            
            # 保存分析结果
            file_name = result_file.stem
            all_analyses[file_name] = analysis
            
            # 提取汇总信息
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
                        avg_qual.get("semantic_score", 0) + 
                        avg_qual.get("structure_score", 0) + 
                        avg_qual.get("completeness_score", 0)
                    ) / 3 if avg_qual else 0
                }
            }
            
            all_summaries.append(summary)
            
            # 打印简要信息
            print(f"  Test Type: {summary['test_type']}")
            print(f"  Total Cases: {summary['total_cases']}, Valid Cases: {summary['valid_cases']}")
            print(f"  Function Reuse Rate: {summary['quantitative']['function_reuse_rate']:.2f}%")
            print(f"  Variable Reuse Rate: {summary['quantitative']['variable_reuse_rate']:.2f}%")
            print(f"  Overall Average Score: {summary['qualitative']['overall_average']:.2f}/100")
            
        except Exception as e:
            print(f"  ERROR: Failed to analyze {result_file.name}: {e}")
            continue
    
    # 计算总体统计
    if all_summaries:
        total_cases = sum(s["total_cases"] for s in all_summaries)
        total_valid_cases = sum(s["valid_cases"] for s in all_summaries)
        
        # 按测试类型分组
        by_test_type = defaultdict(list)
        for summary in all_summaries:
            test_type = summary["test_type"]
            by_test_type[test_type].append(summary)
        
        # 计算各测试类型的平均值
        type_averages = {}
        for test_type, summaries in by_test_type.items():
            if summaries:
                type_averages[test_type] = {
                    "count": len(summaries),
                    "avg_function_reuse_rate": sum(s["quantitative"]["function_reuse_rate"] for s in summaries) / len(summaries),
                    "avg_variable_reuse_rate": sum(s["quantitative"]["variable_reuse_rate"] for s in summaries) / len(summaries),
                    "avg_semantic_score": sum(s["qualitative"]["semantic_score"] for s in summaries) / len(summaries),
                    "avg_structure_score": sum(s["qualitative"]["structure_score"] for s in summaries) / len(summaries),
                    "avg_completeness_score": sum(s["qualitative"]["completeness_score"] for s in summaries) / len(summaries),
                    "avg_overall_score": sum(s["qualitative"]["overall_average"] for s in summaries) / len(summaries),
                }
        
        # 计算全局平均值
        global_averages = {
            "avg_function_reuse_rate": sum(s["quantitative"]["function_reuse_rate"] for s in all_summaries) / len(all_summaries),
            "avg_variable_reuse_rate": sum(s["quantitative"]["variable_reuse_rate"] for s in all_summaries) / len(all_summaries),
            "avg_semantic_score": sum(s["qualitative"]["semantic_score"] for s in all_summaries) / len(all_summaries),
            "avg_structure_score": sum(s["qualitative"]["structure_score"] for s in all_summaries) / len(all_summaries),
            "avg_completeness_score": sum(s["qualitative"]["completeness_score"] for s in all_summaries) / len(all_summaries),
            "avg_overall_score": sum(s["qualitative"]["overall_average"] for s in all_summaries) / len(all_summaries),
        }
    else:
        total_cases = 0
        total_valid_cases = 0
        by_test_type = {}
        type_averages = {}
        global_averages = {}
    
    # 构建汇总结果
    aggregated_result = {
        "metadata": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_files": len(result_files),
            "total_cases": total_cases,
            "total_valid_cases": total_valid_cases,
            "benchmark_dir": str(Path(benchmark_dir).absolute())
        },
        "global_statistics": global_averages,
        "statistics_by_test_type": type_averages,
        "summaries": all_summaries,
        "detailed_analyses": all_analyses
    }
    
    # 保存到文件
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(benchmark_dir) / f"aggregated_results_{timestamp}.json"
    else:
        output_file = Path(output_file)
    
    # 确保输出目录存在
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(aggregated_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print(f"Aggregation completed!")
    print(f"Results saved to: {output_file}")
    print(f"{'='*80}")
    
    return aggregated_result


def print_summary_table(aggregated_result: Dict[str, Any]):
    """
    打印汇总表格
    
    Args:
        aggregated_result: 汇总结果字典
    """
    summaries = aggregated_result.get("summaries", [])
    if not summaries:
        print("No summaries to display")
        return
    
    print(f"\n{'='*100}")
    print("Summary Table")
    print(f"{'='*100}")
    
    # 表头
    header = f"{'File Name':<40} {'Test Type':<20} {'Func Reuse %':<15} {'Var Reuse %':<15} {'Semantic':<12} {'Structure':<12} {'Complete':<12} {'Overall':<12}"
    print(header)
    print("-" * 100)
    
    # 数据行
    for summary in summaries:
        file_name = summary["file_name"][:38]
        test_type = summary["test_type"][:18]
        func_reuse = summary["quantitative"]["function_reuse_rate"]
        var_reuse = summary["quantitative"]["variable_reuse_rate"]
        semantic = summary["qualitative"]["semantic_score"]
        structure = summary["qualitative"]["structure_score"]
        complete = summary["qualitative"]["completeness_score"]
        overall = summary["qualitative"]["overall_average"]
        
        print(f"{file_name:<40} {test_type:<20} {func_reuse:>13.2f}% {var_reuse:>13.2f}% "
              f"{semantic:>10.2f} {structure:>10.2f} {complete:>10.2f} {overall:>10.2f}")
    
    # 全局平均值
    global_stats = aggregated_result.get("global_statistics", {})
    if global_stats:
        print("-" * 100)
        print(f"{'GLOBAL AVERAGE':<40} {'':<20} "
              f"{global_stats.get('avg_function_reuse_rate', 0):>13.2f}% "
              f"{global_stats.get('avg_variable_reuse_rate', 0):>13.2f}% "
              f"{global_stats.get('avg_semantic_score', 0):>10.2f} "
              f"{global_stats.get('avg_structure_score', 0):>10.2f} "
              f"{global_stats.get('avg_completeness_score', 0):>10.2f} "
              f"{global_stats.get('avg_overall_score', 0):>10.2f}")
    
    # 按测试类型分组显示
    type_averages = aggregated_result.get("statistics_by_test_type", {})
    if type_averages:
        print(f"\n{'='*100}")
        print("Statistics by Test Type")
        print(f"{'='*100}")
        print(f"{'Test Type':<30} {'Count':<10} {'Func Reuse %':<15} {'Var Reuse %':<15} {'Overall Score':<15}")
        print("-" * 100)
        
        for test_type, stats in sorted(type_averages.items()):
            print(f"{test_type[:28]:<30} {stats['count']:<10} "
                  f"{stats['avg_function_reuse_rate']:>13.2f}% "
                  f"{stats['avg_variable_reuse_rate']:>13.2f}% "
                  f"{stats['avg_overall_score']:>13.2f}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Aggregate all benchmark result files")
    parser.add_argument("--benchmark-dir", type=str, default="evox-server/.rag/benchmark",
                        help="Benchmark directory path")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file path (default: auto-generated)")
    parser.add_argument("--print-table", action="store_true",
                        help="Print summary table after aggregation")
    
    args = parser.parse_args()
    
    # 汇总所有结果
    aggregated_result = aggregate_all_results(
        benchmark_dir=args.benchmark_dir,
        output_file=args.output
    )
    
    # 打印汇总表格
    if args.print_table:
        print_summary_table(aggregated_result)


if __name__ == "__main__":
    main()

