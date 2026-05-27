#!/usr/bin/env python3
# evox-server/src/core/rag/code/query/evaluator/compare_analyzers.py

"""
对比cpp_quality_analyzer.py和cpp_quality_analyzer_by_package.py的分析结果
用于验证两个分析器的准确性和一致性
"""

import os
import sys
from pathlib import Path

# 导入两个分析器
try:
    from cpp_quality_analyzer import CppCodeAnalyzer
    has_original = True
except ImportError:
    print("警告: 无法导入 cpp_quality_analyzer")
    has_original = False

try:
    from cpp_quality_analyzer_by_package import CppCodeAnalyzerByPackage
    has_package = True
except ImportError:
    print("警告: 无法导入 cpp_quality_analyzer_by_package (需要安装 lizard)")
    has_package = False


def compare_metrics(code: str, code_name: str = "代码"):
    """
    比较两个分析器对同一代码的分析结果
    """
    print(f"\n{'='*80}")
    print(f"分析: {code_name}")
    print(f"{'='*80}")
    
    results = {}
    
    # 使用原始分析器
    if has_original:
        print("\n--- 原始分析器 (cpp_quality_analyzer.py) ---")
        try:
            analyzer1 = CppCodeAnalyzer()
            metrics1 = analyzer1.analyze_code_quality(code)
            results['original'] = metrics1
            
            print(f"函数数量: {metrics1.function_count}")
            print(f"代码行数: {metrics1.lines_of_code}")
            print(f"平均圈复杂度: {metrics1.avg_cyclomatic_complexity:.2f}")
            print(f"平均函数长度: {metrics1.avg_function_length:.2f}")
            print(f"注释密度: {metrics1.comment_density:.2f}")
            print(f"Halstead 体积: {metrics1.halstead_volume:.2f}")
            print(f"Halstead 难度: {metrics1.halstead_difficulty:.2f}")
            print(f"Halstead 工作量: {metrics1.halstead_effort:.2f}")
        except Exception as e:
            print(f"错误: {e}")
    
    # 使用Lizard分析器
    if has_package:
        print("\n--- Lizard分析器 (cpp_quality_analyzer_by_package.py) ---")
        try:
            analyzer2 = CppCodeAnalyzerByPackage()
            metrics2 = analyzer2.analyze_code_quality(code)
            results['package'] = metrics2
            
            print(f"函数数量: {metrics2.function_count}")
            print(f"代码行数: {metrics2.lines_of_code}")
            print(f"平均圈复杂度: {metrics2.avg_cyclomatic_complexity:.2f}")
            print(f"平均函数长度: {metrics2.avg_function_length:.2f}")
            print(f"注释密度: {metrics2.comment_density:.2f}")
            print(f"Halstead 体积: {metrics2.halstead_volume:.2f}")
            print(f"Halstead 难度: {metrics2.halstead_difficulty:.2f}")
            print(f"Halstead 工作量: {metrics2.halstead_effort:.2f}")
        except Exception as e:
            print(f"错误: {e}")
    
    # 对比结果
    if 'original' in results and 'package' in results:
        print(f"\n--- 差异对比 ---")
        m1, m2 = results['original'], results['package']
        
        metrics_to_compare = [
            ('函数数量', 'function_count', False),
            ('代码行数', 'lines_of_code', False),
            ('平均圈复杂度', 'avg_cyclomatic_complexity', True),
            ('平均函数长度', 'avg_function_length', True),
            ('注释密度', 'comment_density', True),
            ('Halstead 体积', 'halstead_volume', True),
            ('Halstead 难度', 'halstead_difficulty', True),
            ('Halstead 工作量', 'halstead_effort', True),
        ]
        
        for name, attr, is_float in metrics_to_compare:
            v1 = getattr(m1, attr)
            v2 = getattr(m2, attr)
            
            if v1 == 0 and v2 == 0:
                diff_str = "相同 (均为0)"
            elif v1 == 0:
                diff_str = f"∞% (原始为0)"
            else:
                diff_pct = ((v2 - v1) / v1) * 100
                diff_str = f"{diff_pct:+.1f}%"
            
            if is_float:
                print(f"{name:20s}: {v1:10.2f} vs {v2:10.2f}  差异: {diff_str}")
            else:
                print(f"{name:20s}: {v1:10d} vs {v2:10d}  差异: {diff_str}")
    
    return results


def test_simple_code():
    """测试简单代码"""
    code = """
#include <iostream>

int add(int a, int b) {
    return a + b;
}

int main() {
    int result = add(5, 3);
    std::cout << result << std::endl;
    return 0;
}
"""
    compare_metrics(code, "简单示例代码")


def test_complex_code():
    """测试复杂代码"""
    code = """
#include <iostream>
#include <vector>

class Calculator {
private:
    int value;
    
public:
    Calculator(int v) : value(v) {}
    
    int add(int a, int b) {
        if (a < 0 || b < 0) {
            throw std::invalid_argument("Negative numbers not allowed");
        }
        return a + b;
    }
    
    int multiply(int a, int b) {
        int result = 0;
        for (int i = 0; i < b; i++) {
            result += a;
        }
        return result;
    }
    
    int factorial(int n) {
        if (n <= 1) return 1;
        return n * factorial(n - 1);
    }
};

int main() {
    Calculator calc(10);
    std::cout << calc.add(5, 3) << std::endl;
    std::cout << calc.multiply(4, 3) << std::endl;
    std::cout << calc.factorial(5) << std::endl;
    return 0;
}
"""
    compare_metrics(code, "复杂示例代码")


def test_real_files():
    """测试实际文件"""
    file_paths = [
        ("baseline.cpp", "Baseline.cpp"),
        ("ours.cpp", "Ours.cpp"),
    ]
    
    # 尝试多个可能的路径
    base_dirs = [
        ".",
        "evox-server/src/core/rag/code/query/evaluator",
        "D:\\Download\\github\\evox-ai\\evox-server\\src\\core\\rag\\code\\query\\evaluator",
    ]
    
    for filename, display_name in file_paths:
        found = False
        for base_dir in base_dirs:
            filepath = os.path.join(base_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    code = f.read()
                compare_metrics(code, display_name)
                found = True
                break
        
        if not found:
            print(f"\n警告: 未找到文件 {filename}")


def main():
    """主函数"""
    print("C++ 代码质量分析器对比工具")
    print("="*80)
    
    if not has_original and not has_package:
        print("错误: 两个分析器都无法导入")
        return
    
    if not has_original:
        print("警告: 原始分析器不可用，仅测试Lizard分析器")
    
    if not has_package:
        print("警告: Lizard分析器不可用 (请运行: pip install lizard)")
        print("       仅测试原始分析器")
    
    # 运行测试
    test_simple_code()
    test_complex_code()
    test_real_files()
    
    print(f"\n{'='*80}")
    print("对比完成!")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

