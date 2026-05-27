# Benchmark 结果汇总脚本使用说明

## 功能说明

`aggregate_benchmark_results.py` 脚本用于：
1. 遍历 `evox-server/.rag/benchmark` 文件夹下的所有测试结果文件（`*_results_*.json`）
2. 分析每个结果文件，提取定量和定性评估统计
3. 将所有结果汇总到一个新的 JSON 文件中
4. 可选：打印汇总表格

## 使用方法

### 基本用法

```bash
# 从项目根目录运行
python src/core/rag/code/aggregate_benchmark_results.py
```

### 带参数运行

```bash
# 指定 benchmark 目录
python src/core/rag/code/aggregate_benchmark_results.py --benchmark-dir evox-server/.rag/benchmark

# 指定输出文件
python src/core/rag/code/aggregate_benchmark_results.py --output my_aggregated_results.json

# 打印汇总表格
python src/core/rag/code/aggregate_benchmark_results.py --print-table

# 组合使用
python src/core/rag/code/aggregate_benchmark_results.py --print-table --output aggregated_results.json
```

## 输出文件格式

生成的汇总文件包含以下结构：

```json
{
  "metadata": {
    "generated_at": "2026-01-26 21:33:21",
    "total_files": 9,
    "total_cases": 1512,
    "total_valid_cases": 1488,
    "benchmark_dir": "..."
  },
  "global_statistics": {
    "avg_function_reuse_rate": 58.91,
    "avg_variable_reuse_rate": 60.79,
    "avg_semantic_score": 66.83,
    "avg_structure_score": 62.79,
    "avg_completeness_score": 61.65,
    "avg_overall_score": 63.76
  },
  "statistics_by_test_type": {
    "local-small": { ... },
    "workflow": { ... },
    ...
  },
  "summaries": [
    {
      "file_name": "...",
      "test_type": "...",
      "total_cases": 168,
      "valid_cases": 167,
      "quantitative": { ... },
      "qualitative": { ... }
    },
    ...
  ],
  "detailed_analyses": {
    "file_name": { ... },
    ...
  }
}
```

## 输出示例

### 汇总表格

```
====================================================================================================
Summary Table
====================================================================================================
File Name                                Test Type            Func Reuse %    Var Reuse %     Semantic     Structure    Complete     Overall     
----------------------------------------------------------------------------------------------------
local-small_results_01_26_17_48.json     local-small                  66.75%         70.32%      75.84      75.00      68.44      73.09
workflow+sd+mi+rf_results_01_24_17_11.   workflow+sd+mi+rf            72.26%         73.09%      77.14      71.75      75.14      74.67
...
----------------------------------------------------------------------------------------------------
GLOBAL AVERAGE                                                        58.91%         60.79%      66.83      62.79      61.65      63.76
```

### 按测试类型统计

```
====================================================================================================
Statistics by Test Type
====================================================================================================
Test Type                      Count      Func Reuse %    Var Reuse %     Overall Score  
----------------------------------------------------------------------------------------------------
local                          1                  72.06%         70.72%         69.43
local-small                    1                  66.75%         70.32%         73.09
...
```

## 统计指标说明

### 定量评估（Quantitative）
- **Function Reuse Rate**: 函数重用率（正确重用的函数数 / 总参考函数数）
- **Variable Reuse Rate**: 变量重用率（正确重用的变量数 / 总参考变量数）
- **Average Functions/Variables**: 平均每个案例的函数/变量数量

### 定性评估（Qualitative）
- **Semantic Score**: 语义正确性分数（0-100）
- **Structure Score**: 结构相似性分数（0-100）
- **Completeness Score**: 功能完整性分数（0-100）
- **Overall Average**: 三项分数的平均值

## 特性

1. **自动文件发现**: 自动查找所有 `*_results_*.json` 文件
2. **格式兼容**: 支持对象格式和数组格式的 JSON 文件
3. **错误处理**: 自动跳过无法解析的文件，继续处理其他文件
4. **详细统计**: 提供全局统计、按测试类型统计和每个文件的详细分析
5. **独立运行**: 不依赖外部模块，可直接运行

## 注意事项

- 确保 benchmark 目录路径正确
- 输出文件会自动添加时间戳（如果未指定输出文件）
- 汇总文件可能较大，包含所有详细分析数据


