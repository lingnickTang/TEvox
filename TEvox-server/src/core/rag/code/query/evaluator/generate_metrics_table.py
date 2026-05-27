#!/usr/bin/env python3
# evox-server/src/core/rag/code/query/evaluator/generate_metrics_table.py

"""
使用cpp_quality_analyzer_by_package.py生成详细的指标对比表格
"""

import os
from cpp_quality_analyzer_by_package import CppCodeAnalyzerByPackage


def generate_metrics_table():
    """生成八个指标的详细对比表格"""
    
    # 查找文件
    baseline_path = "baseline.cpp"
    ours_path = "ours.cpp"
    
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
    
    # 读取代码
    if not os.path.exists(baseline_path):
        print(f"错误: 未找到 {baseline_path}")
        return
    
    if not os.path.exists(ours_path):
        print(f"错误: 未找到 {ours_path}")
        return
    
    with open(baseline_path, 'r', encoding='utf-8') as f:
        baseline_code = f.read()
    
    with open(ours_path, 'r', encoding='utf-8') as f:
        ours_code = f.read()
    
    # 分析代码
    analyzer = CppCodeAnalyzerByPackage()
    
    print("正在分析 Baseline.cpp...")
    baseline_metrics = analyzer.analyze_code_quality(baseline_code)
    
    print("正在分析 Ours.cpp...")
    ours_metrics = analyzer.analyze_code_quality(ours_code)
    
    # 生成表格
    print("\n" + "="*100)
    print("C++ 代码质量指标对比表（使用 Lizard 分析器）")
    print("="*100)
    
    # 表头
    print(f"\n{'序号':<6} {'指标名称':<30} {'Baseline数值':<20} {'Ours数值':<20} {'差异':<20}")
    print("-" * 100)
    
    # 八个指标
    metrics_info = [
        (1, "平均圈复杂度", "avg_cyclomatic_complexity", True, "越低越好"),
        (2, "Halstead 体积", "halstead_volume", True, "越低越好"),
        (3, "Halstead 工作量", "halstead_effort", True, "越低越好"),
        (4, "Halstead 难度", "halstead_difficulty", True, "越低越好"),
        (5, "代码行数", "lines_of_code", False, "适中为好"),
        (6, "函数数量", "function_count", False, "适中为好"),
        (7, "注释密度", "comment_density", True, "越高越好"),
        (8, "平均函数长度", "avg_function_length", True, "适中为好"),
    ]
    
    for idx, name, attr, is_float, trend in metrics_info:
        baseline_val = getattr(baseline_metrics, attr)
        ours_val = getattr(ours_metrics, attr)
        
        # 计算差异
        if baseline_val == 0 and ours_val == 0:
            diff_str = "相同 (均为0)"
        elif baseline_val == 0:
            diff_str = "N/A (baseline为0)"
        else:
            diff_pct = ((ours_val - baseline_val) / baseline_val) * 100
            
            # 判断是改进还是退步
            if "越低越好" in trend:
                if diff_pct < 0:
                    status = "✓ 改进"
                elif diff_pct > 0:
                    status = "✗ 退步"
                else:
                    status = "相同"
            elif "越高越好" in trend:
                if diff_pct > 0:
                    status = "✓ 改进"
                elif diff_pct < 0:
                    status = "✗ 退步"
                else:
                    status = "相同"
            else:  # 适中为好
                status = ""
            
            diff_str = f"{diff_pct:+.1f}% {status}"
        
        # 格式化输出
        if is_float:
            baseline_str = f"{baseline_val:.2f}"
            ours_str = f"{ours_val:.2f}"
        else:
            baseline_str = f"{baseline_val}"
            ours_str = f"{ours_val}"
        
        print(f"{idx:<6} {name:<30} {baseline_str:<20} {ours_str:<20} {diff_str:<20}")
    
    print("-" * 100)
    
    # 详细分析
    print("\n" + "="*100)
    print("详细分析")
    print("="*100)
    
    print("\n【改进项】")
    improvements = []
    regressions = []
    
    # 分析每个指标
    if ours_metrics.avg_cyclomatic_complexity < baseline_metrics.avg_cyclomatic_complexity:
        improvements.append(f"✓ 平均圈复杂度降低了 {((baseline_metrics.avg_cyclomatic_complexity - ours_metrics.avg_cyclomatic_complexity) / baseline_metrics.avg_cyclomatic_complexity * 100):.1f}%")
    elif ours_metrics.avg_cyclomatic_complexity > baseline_metrics.avg_cyclomatic_complexity:
        regressions.append(f"✗ 平均圈复杂度增加了 {((ours_metrics.avg_cyclomatic_complexity - baseline_metrics.avg_cyclomatic_complexity) / baseline_metrics.avg_cyclomatic_complexity * 100):.1f}%")
    
    if ours_metrics.halstead_volume < baseline_metrics.halstead_volume:
        improvements.append(f"✓ Halstead体积降低了 {((baseline_metrics.halstead_volume - ours_metrics.halstead_volume) / baseline_metrics.halstead_volume * 100):.1f}%")
    elif ours_metrics.halstead_volume > baseline_metrics.halstead_volume:
        regressions.append(f"✗ Halstead体积增加了 {((ours_metrics.halstead_volume - baseline_metrics.halstead_volume) / baseline_metrics.halstead_volume * 100):.1f}%")
    
    if ours_metrics.halstead_effort < baseline_metrics.halstead_effort:
        improvements.append(f"✓ Halstead工作量降低了 {((baseline_metrics.halstead_effort - ours_metrics.halstead_effort) / baseline_metrics.halstead_effort * 100):.1f}%")
    elif ours_metrics.halstead_effort > baseline_metrics.halstead_effort:
        regressions.append(f"✗ Halstead工作量增加了 {((ours_metrics.halstead_effort - baseline_metrics.halstead_effort) / baseline_metrics.halstead_effort * 100):.1f}%")
    
    if ours_metrics.halstead_difficulty < baseline_metrics.halstead_difficulty:
        improvements.append(f"✓ Halstead难度降低了 {((baseline_metrics.halstead_difficulty - ours_metrics.halstead_difficulty) / baseline_metrics.halstead_difficulty * 100):.1f}%")
    elif ours_metrics.halstead_difficulty > baseline_metrics.halstead_difficulty:
        regressions.append(f"✗ Halstead难度增加了 {((ours_metrics.halstead_difficulty - baseline_metrics.halstead_difficulty) / baseline_metrics.halstead_difficulty * 100):.1f}%")
    
    if ours_metrics.comment_density > baseline_metrics.comment_density:
        improvements.append(f"✓ 注释密度提高了 {((ours_metrics.comment_density - baseline_metrics.comment_density) / baseline_metrics.comment_density * 100):.1f}%")
    elif ours_metrics.comment_density < baseline_metrics.comment_density:
        regressions.append(f"✗ 注释密度降低了 {((baseline_metrics.comment_density - ours_metrics.comment_density) / baseline_metrics.comment_density * 100):.1f}%")
    
    for item in improvements:
        print(f"  {item}")
    
    print("\n【退步项】")
    for item in regressions:
        print(f"  {item}")
    
    print("\n【其他变化】")
    print(f"  • 代码行数: {baseline_metrics.lines_of_code} → {ours_metrics.lines_of_code} ({((ours_metrics.lines_of_code - baseline_metrics.lines_of_code) / baseline_metrics.lines_of_code * 100):+.1f}%)")
    print(f"  • 函数数量: {baseline_metrics.function_count} → {ours_metrics.function_count} ({((ours_metrics.function_count - baseline_metrics.function_count) / baseline_metrics.function_count * 100):+.1f}%)")
    print(f"  • 平均函数长度: {baseline_metrics.avg_function_length:.2f} → {ours_metrics.avg_function_length:.2f} ({((ours_metrics.avg_function_length - baseline_metrics.avg_function_length) / baseline_metrics.avg_function_length * 100):+.1f}%)")
    
    # 总结
    print("\n" + "="*100)
    print("总结")
    print("="*100)
    improvement_count = len(improvements)
    regression_count = len(regressions)
    
    if improvement_count > regression_count:
        print(f"✓ 总体评价: 改进 ({improvement_count}项改进, {regression_count}项退步)")
    elif regression_count > improvement_count:
        print(f"✗ 总体评价: 退步 ({improvement_count}项改进, {regression_count}项退步)")
    else:
        print(f"≈ 总体评价: 持平 ({improvement_count}项改进, {regression_count}项退步)")
    
    print("="*100)
    print()


if __name__ == "__main__":
    generate_metrics_table()

