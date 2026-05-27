#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对比脚本：对比设计文档中的refactored模块与实际代码文件的质量指标
"""

import sys
import os
import json
sys.path.insert(0, 'evox-server/src/core/rag/code/query/evaluator')

from cpp_quality_analyzer_by_package import analyze_file_list, analyze_json_file_refactored_modules

def load_json_results(filepath):
    """加载JSON结果文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('results', {})
    except FileNotFoundError:
        print(f"⚠️  文件不存在: {filepath}")
        return None
    except Exception as e:
        print(f"⚠️  读取文件失败: {e}")
        return None

def format_number(value, decimals=2):
    """格式化数字"""
    if isinstance(value, (int, float)):
        if decimals == 0:
            return f"{int(value)}"
        return f"{value:.{decimals}f}"
    return str(value)

def calculate_difference(actual, design, is_higher_better=False):
    """计算差异并返回状态"""
    try:
        diff = actual - design
        diff_pct = (diff / design * 100) if design != 0 else 0
        
        # 对于"越小越好"的指标（默认）
        if not is_higher_better:
            if diff < 0:  # 实际值更小，更好
                return diff, diff_pct, "✅ 改进"
            elif diff > 0:  # 实际值更大，更差
                return diff, diff_pct, "⚠️ 变差"
            else:
                return diff, diff_pct, "➡️ 相同"
        # 对于"越大越好"的指标
        else:
            if diff > 0:  # 实际值更大，更好
                return diff, diff_pct, "✅ 改进"
            elif diff < 0:  # 实际值更小，更差
                return diff, diff_pct, "⚠️ 变差"
            else:
                return diff, diff_pct, "➡️ 相同"
    except:
        return 0, 0, "❓ 无法对比"

def print_comparison_table(design_results, actual_results):
    """打印对比表格"""
    
    # 定义指标信息
    metrics_info = [
        ('avg_cyclomatic_complexity', '平均圈复杂度', False, 2),
        ('halstead_volume', 'Halstead体积', False, 2),
        ('halstead_effort', 'Halstead工作量', False, 2),
        ('halstead_difficulty', 'Halstead难度', False, 2),
        ('lines_of_code', '代码行数', False, 0),
        ('function_count', '函数数量', False, 0),
        ('comment_density', '注释密度', True, 4),
        ('avg_function_length', '平均函数长度', False, 2),
    ]
    
    # 建立映射关系（设计名称 -> 实际文件名）
    name_mapping = {
        'SSIDManagerRefactored': 'ssid_manager.cc',
        'DnsServerRefactored': 'dns_server.cc',
        'wifiConfigurationAPRefactored': 'wifi_configuration_ap.cc',
        'wifi_station_refactored': 'wifi_station.cc'
    }
    
    print("\n" + "="*120)
    print("设计文档 (Refactored) vs 实际代码 (Actual) - 质量指标对比")
    print("="*120)
    
    for design_name, actual_name in name_mapping.items():
        if design_name not in design_results:
            print(f"\n⚠️  设计文档中未找到: {design_name}")
            continue
        if actual_name not in actual_results:
            print(f"\n⚠️  实际代码中未找到: {actual_name}")
            continue
        
        design_metrics = design_results[design_name]
        actual_metrics = actual_results[actual_name]
        
        print(f"\n{'─'*120}")
        print(f"📊 对比组: {design_name} (设计) ←→ {actual_name} (实际)")
        print(f"{'─'*120}")
        
        # 表头
        print(f"{'指标':<20} | {'设计值':<15} | {'实际值':<15} | {'差异':<15} | {'百分比':<12} | {'状态'}")
        print(f"{'-'*20}-+-{'-'*15}-+-{'-'*15}-+-{'-'*15}-+-{'-'*12}-+-{'-'*10}")
        
        # 逐行对比指标
        for metric_key, metric_name, is_higher_better, decimals in metrics_info:
            design_val = design_metrics.get(metric_key, 0)
            actual_val = actual_metrics.get(metric_key, 0)
            
            diff, diff_pct, status = calculate_difference(actual_val, design_val, is_higher_better)
            
            # 特殊处理注释密度（显示为百分比）
            if metric_key == 'comment_density':
                design_display = f"{design_val*100:.2f}%"
                actual_display = f"{actual_val*100:.2f}%"
                diff_display = f"{diff*100:+.2f}%"
            else:
                design_display = format_number(design_val, decimals)
                actual_display = format_number(actual_val, decimals)
                diff_display = f"{diff:+{decimals+4}.{decimals}f}" if decimals > 0 else f"{int(diff):+d}"
            
            print(f"{metric_name:<20} | {design_display:>15} | {actual_display:>15} | {diff_display:>15} | {diff_pct:>10.1f}% | {status}")
    
    # 总体统计
    print(f"\n{'='*120}")
    print("总体统计对比")
    print(f"{'='*120}")
    
    design_total_loc = sum(m['lines_of_code'] for m in design_results.values())
    actual_total_loc = sum(m['lines_of_code'] for m in actual_results.values())
    
    design_total_funcs = sum(m['function_count'] for m in design_results.values())
    actual_total_funcs = sum(m['function_count'] for m in actual_results.values())
    
    design_avg_complexity = sum(m['avg_cyclomatic_complexity'] for m in design_results.values()) / len(design_results)
    actual_avg_complexity = sum(m['avg_cyclomatic_complexity'] for m in actual_results.values()) / len(actual_results)
    
    design_avg_comment = sum(m['comment_density'] for m in design_results.values()) / len(design_results)
    actual_avg_comment = sum(m['comment_density'] for m in actual_results.values()) / len(actual_results)
    
    print(f"\n{'指标':<30} | {'设计值':<15} | {'实际值':<15} | {'差异':<15} | {'状态'}")
    print(f"{'-'*30}-+-{'-'*15}-+-{'-'*15}-+-{'-'*15}-+-{'-'*10}")
    
    diff_loc = actual_total_loc - design_total_loc
    print(f"{'总代码行数':<30} | {design_total_loc:>15} | {actual_total_loc:>15} | {diff_loc:>+15} | {'⚠️ 增加' if diff_loc > 0 else '✅ 减少'}")
    
    diff_funcs = actual_total_funcs - design_total_funcs
    print(f"{'总函数数量':<30} | {design_total_funcs:>15} | {actual_total_funcs:>15} | {diff_funcs:>+15} | {'⚠️ 增加' if diff_funcs > 0 else '✅ 减少'}")
    
    diff_complexity = actual_avg_complexity - design_avg_complexity
    print(f"{'平均复杂度':<30} | {design_avg_complexity:>15.2f} | {actual_avg_complexity:>15.2f} | {diff_complexity:>+15.2f} | {'⚠️ 增加' if diff_complexity > 0 else '✅ 降低'}")
    
    diff_comment = actual_avg_comment - design_avg_comment
    print(f"{'平均注释密度':<30} | {design_avg_comment*100:>14.2f}% | {actual_avg_comment*100:>14.2f}% | {diff_comment*100:>+14.2f}% | {'✅ 增加' if diff_comment > 0 else '⚠️ 减少'}")
    
    # 质量评估
    print(f"\n{'='*120}")
    print("质量评估")
    print(f"{'='*120}")
    
    improvements = 0
    regressions = 0
    
    for design_name, actual_name in name_mapping.items():
        if design_name in design_results and actual_name in actual_results:
            design_m = design_results[design_name]
            actual_m = actual_results[actual_name]
            
            # 复杂度对比
            if actual_m['avg_cyclomatic_complexity'] < design_m['avg_cyclomatic_complexity']:
                improvements += 1
            elif actual_m['avg_cyclomatic_complexity'] > design_m['avg_cyclomatic_complexity']:
                regressions += 1
    
    print(f"\n对比结果:")
    print(f"  ✅ 复杂度改进: {improvements}/{len(name_mapping)} 个模块")
    print(f"  ⚠️  复杂度变差: {regressions}/{len(name_mapping)} 个模块")
    print(f"  ➡️  复杂度不变: {len(name_mapping)-improvements-regressions}/{len(name_mapping)} 个模块")
    
    if actual_avg_complexity < design_avg_complexity:
        print(f"\n🎉 总体评估: 实际代码质量优于设计（平均复杂度降低 {abs(diff_complexity):.2f}）")
    elif actual_avg_complexity > design_avg_complexity:
        print(f"\n⚠️  总体评估: 实际代码复杂度高于设计（平均复杂度增加 {diff_complexity:.2f}）")
    else:
        print(f"\n➡️  总体评估: 实际代码与设计基本一致")

def main():
    print("="*120)
    print("设计文档 vs 实际代码 - 质量指标对比工具")
    print("="*120)
    
    # 步骤1: 加载设计文档分析结果
    print("\n步骤1: 加载设计文档分析结果...")
    design_results_file = "refactored_modules_analysis_results.json"
    design_results = load_json_results(design_results_file)
    
    if not design_results:
        print(f"❌ 无法加载设计文档结果，请先运行: python test_refactored_analysis.py")
        return
    
    print(f"✅ 成功加载 {len(design_results)} 个设计模块")
    for name in design_results.keys():
        print(f"   - {name}")
    
    # 步骤2: 分析实际代码文件
    print("\n步骤2: 分析实际代码文件...")
    
    file_list = [
        "file:managed_components/78__esp-wifi-connect/ssid_manager.cc",
        "file:managed_components/78__esp-wifi-connect/dns_server.cc",
        "file:managed_components/78__esp-wifi-connect/wifi_configuration_ap.cc",
        "file:managed_components/78__esp-wifi-connect/wifi_station.cc"
    ]
    base_path = "D:/Download/github/xiaozhi-esp32"
    
    # 检查路径是否存在
    if not os.path.exists(base_path):
        print(f"⚠️  警告: 基础路径不存在: {base_path}")
        print(f"\n请修改脚本中的 base_path 为正确的项目路径，或者:")
        print(f"   1. 手动分析文件并保存结果")
        print(f"   2. 使用已有的分析结果文件")
        
        # 尝试使用已存在的结果文件
        actual_results_file = "file_list_analysis_results.json"
        if os.path.exists(actual_results_file):
            print(f"\n找到已有的分析结果文件: {actual_results_file}")
            actual_results = load_json_results(actual_results_file)
            if actual_results:
                print(f"✅ 成功加载 {len(actual_results)} 个实际文件")
                print_comparison_table(design_results, actual_results)
                return
        
        print(f"\n❌ 无法继续，请先:")
        print(f"   1. 修改 base_path 为正确路径")
        print(f"   2. 或运行: python test_file_list_analysis.py")
        return
    
    actual_results_file = "actual_code_analysis_results.json"
    
    print(f"基础路径: {base_path}")
    print(f"文件列表:")
    for f in file_list:
        print(f"   - {f}")
    
    # 分析实际文件
    actual_results = analyze_file_list(
        file_list,
        base_path,
        actual_results_file,
        debug=False
    )
    
    if not actual_results:
        print(f"❌ 实际代码分析失败")
        return
    
    print(f"✅ 成功分析 {len(actual_results)} 个实际文件")
    
    # 步骤3: 生成对比表格
    print("\n步骤3: 生成对比表格...")
    print_comparison_table(design_results, actual_results)
    
    # 保存对比结果
    comparison_data = {
        "comparison_timestamp": __import__('datetime').datetime.now().isoformat(),
        "design_source": design_results_file,
        "actual_source": actual_results_file,
        "design_results": design_results,
        "actual_results": actual_results
    }
    
    comparison_file = "comparison_results.json"
    with open(comparison_file, 'w', encoding='utf-8') as f:
        json.dump(comparison_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*120}")
    print(f"✅ 对比完成！对比数据已保存到: {comparison_file}")
    print(f"{'='*120}")

if __name__ == "__main__":
    main()


