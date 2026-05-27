# C++ Quality Analyzer By Package

基于Lizard的C++代码质量分析器实现

## 概述

`cpp_quality_analyzer_by_package.py` 是使用Lizard库实现的C++代码质量分析器，与原始的`cpp_quality_analyzer.py`保持相同的接口和输出格式。

## 特性

- ✅ **单一依赖**: 仅需要Lizard一个Python包
- ✅ **完整指标**: 提供8个代码质量指标
- ✅ **兼容接口**: 与原始分析器API完全兼容
- ✅ **调试功能**: 提供详细的调试输出选项

## 安装依赖

```bash
pip install lizard
```

## 8个质量指标

1. **平均圈复杂度** (avg_cyclomatic_complexity)
   - 来源: Lizard直接提供
   - 说明: 衡量代码控制流复杂度

2. **代码行数** (lines_of_code)
   - 来源: Lizard的NLOC (Non-comment lines of code)
   - 说明: 非注释代码行数

3. **函数数量** (function_count)
   - 来源: Lizard直接提供
   - 说明: 代码中函数的总数

4. **平均函数长度** (avg_function_length)
   - 来源: Lizard直接提供
   - 说明: 每个函数的平均代码行数

5. **注释密度** (comment_density)
   - 来源: 基于Lizard的comment_lines计算
   - 说明: 注释行占总行数的比例

6. **Halstead体积** (halstead_volume)
   - 来源: 手动计算（基于代码tokenization）
   - 说明: 代码的信息量大小

7. **Halstead难度** (halstead_difficulty)
   - 来源: 手动计算
   - 说明: 代码理解的困难程度

8. **Halstead工作量** (halstead_effort)
   - 来源: 手动计算
   - 说明: 维护代码所需的工作量

## 使用方法

### 基本使用

```python
from cpp_quality_analyzer_by_package import evaluate_cpp_code_quality_standalone

# 分析C++代码
code = """
#include <iostream>
int main() {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}
"""

metrics = evaluate_cpp_code_quality_standalone(code)
print(f"代码行数: {metrics.lines_of_code}")
print(f"函数数量: {metrics.function_count}")
print(f"平均圈复杂度: {metrics.avg_cyclomatic_complexity:.2f}")
```

### 带调试输出

```python
from cpp_quality_analyzer_by_package import CppCodeAnalyzerByPackage

analyzer = CppCodeAnalyzerByPackage()
metrics = analyzer.analyze_code_quality_with_debug(code, debug=True)
```

### 直接运行测试

```bash
cd evox-server/src/core/rag/code/query/evaluator
python cpp_quality_analyzer_by_package.py
```

这将自动测试同目录下的`baseline.cpp`和`ours.cpp`文件（如果存在）。

## Halstead指标计算策略

代码实现了三层fallback策略来计算Halstead指标：

### 策略1: 基于代码Tokenization（首选）
- 手动解析代码，提取操作符和操作数
- 统计不同token和总token数量
- 使用标准Halstead公式计算

### 策略2: 基于Lizard Token Count
- 如果Lizard提供token_count信息
- 使用经验公式估算唯一token数量
- 假设操作符和操作数比例为4:6

### 策略3: 基于代码行数（最后备选）
- 基于实际C++项目的统计数据
- 使用经验公式：
  - Volume ≈ NLOC × 25
  - Difficulty ≈ NLOC × 1.2
  - Effort = Volume × Difficulty

## 与原始分析器的对比

| 特性 | cpp_quality_analyzer.py | cpp_quality_analyzer_by_package.py |
|------|------------------------|-----------------------------------|
| 依赖 | 无外部依赖 | Lizard |
| 函数识别 | 正则表达式 | Lizard AST |
| 圈复杂度 | 手动计算 | Lizard提供 |
| Halstead | 手动计算 | 手动计算 |
| 准确度 | 中等 | 高（函数识别更准确） |
| 速度 | 快 | 中等 |

## 输出格式

两个分析器使用相同的`CppQualityMetrics`数据类，确保输出格式一致：

```python
@dataclass
class CppQualityMetrics:
    avg_cyclomatic_complexity: float
    halstead_volume: float
    halstead_effort: float
    halstead_difficulty: float
    lines_of_code: int
    function_count: int
    comment_density: float
    avg_function_length: float
    has_errors: bool
    errors: List[AnalysisError]
```

## 注意事项

1. **Lizard版本**: 建议使用Lizard 1.17+版本
2. **C++标准**: Lizard支持C++11/14/17/20特性
3. **性能**: 对于大型文件（>10000行），Lizard可能需要几秒钟

## 故障排除

### ImportError: No module named 'lizard'
```bash
pip install lizard
```

### 函数数量为0
- 检查代码是否包含有效的C++函数定义
- Lizard需要函数有完整的函数体（包含大括号）

### Halstead指标为0
- 可能代码过于简单
- 检查是否正确移除了注释和字符串

## 示例输出

```
=== Lizard 分析结果 ===
代码行数 (NLOC): 233
函数数量: 13
注释行数: 12

函数列表:
1. ReminderManager (复杂度=1, 长度=3行)
2. AddReminder (复杂度=1, 长度=15行)
3. CancelReminder (复杂度=2, 长度=11行)
...

=== 计算指标 ===
平均圈复杂度: 3.15
平均函数长度: 18.08
注释密度: 0.05
Halstead 体积: 18234.56
Halstead 难度: 75.23
Halstead 工作量: 1371245.67

=== 最终结果 ===
函数数量: 13
平均函数长度: 18.08行
平均圈复杂度: 3.15
代码行数: 233
注释密度: 0.05
Halstead 体积: 18234.56
Halstead 难度: 75.23
Halstead 工作量: 1371245.67
```

## 贡献

如果发现任何问题或有改进建议，请提交Issue或Pull Request。

