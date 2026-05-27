# without-small_results_01_23_11_19.json 问题修复总结

## 发现的问题

### 1. JSON 文件格式不兼容
**问题描述**：
- `without-small_results_01_23_11_19.json` 使用数组格式（直接是结果列表）
- `local-small_results_01_26_17_48.json` 使用对象格式（包含 metadata, statistics, results）
- 原代码只支持对象格式，导致 `AttributeError: 'list' object has no attribute 'get'`

**修复方案**：
- 修改 `load_result_file()` 方法，支持两种格式：
  - 数组格式：直接转换为统一的对象格式
  - 对象格式：保持原有逻辑
- 修改 `test_show_benchmark.py` 中的 `analyze_result_file()` 函数，自动检测格式类型

### 2. 占位符格式多样化
**问题描述**：
- 文件中存在多种占位符格式：`"<none>"`, `"none"`, `"(none)"`
- 原代码只处理了 `"<none>"` 和 `"none"`，遗漏了 `"(none)"`

**修复方案**：
- 扩展 `filter_placeholders()` 函数，支持更多占位符格式：
  - `<none>`, `none`, `(none)`, `n/a`, `N/A`, `null`, `NULL`, `""`（空字符串）
- 使用集合进行快速匹配，提高效率

### 3. 测试脚本输出问题
**问题描述**：
- 在循环中每次迭代都打印 Summary，导致输出非常冗长（168 次重复输出）

**修复方案**：
- 将 Summary 打印移到循环外，只在最后打印一次

## 修复后的结果

### 文件分析结果
- **文件格式**: Array (direct results list)
- **总案例数**: 168
- **有效案例数**: 166
- **错误案例数**: 2（代码生成失败，正常情况）

### 平均统计结果

**定量评估**：
- **函数统计**：
  - 平均正确重用的函数数：1.70
  - 平均错误构造的函数数：4.78
  - 平均总参考函数数：6.48
  - 函数重用率：32.54%

- **变量统计**：
  - 平均正确重用的变量数：3.19
  - 平均错误构造的变量数：6.70
  - 平均总参考变量数：9.89
  - 变量重用率：39.63%

**定性评估**：
- 语义正确性：40.30/100
- 结构相似性：38.40/100
- 功能完整性：31.20/100
- 总体平均：36.64/100

## 与 local-small 结果对比

| 指标 | without-small | local-small | 差异 |
|------|---------------|-------------|------|
| 函数重用率 | 32.54% | 66.75% | -34.21% |
| 变量重用率 | 39.63% | 70.32% | -30.69% |
| 语义正确性 | 40.30 | 75.84 | -35.54 |
| 结构相似性 | 38.40 | 75.00 | -36.60 |
| 功能完整性 | 31.20 | 68.44 | -37.24 |
| 总体平均 | 36.64 | 73.09 | -36.45 |

**分析**：
- `without-small` 的结果明显低于 `local-small`
- 所有指标都显著下降，说明知识提取（knowledge extraction）对代码生成质量有重要影响

## 修复的文件

1. **evox-server/src/core/rag/code/show_benchmark.py**
   - 更新 `load_result_file()` 支持两种 JSON 格式
   - 扩展 `filter_placeholders()` 支持更多占位符格式

2. **evox-server/src/core/rag/code/test_show_benchmark.py**
   - 更新 `analyze_result_file()` 支持两种 JSON 格式
   - 扩展 `filter_placeholders()` 支持更多占位符格式
   - 修复 Summary 重复打印问题

## 错误案例说明

2 个错误案例都是代码生成失败：
- `OnWifiConnectTimeout(void *)()` - 文件写入错误：Document has been closed
- `DecodeHexString(const std::string &)()` - 文件写入错误：Document has been closed

这些是正常的运行时错误，代码已正确处理（跳过这些案例）。

## 使用建议

现在代码可以处理两种格式的结果文件：

```bash
# 分析对象格式文件
python src/core/rag/code/test_show_benchmark.py .rag/benchmark/local-small_results_01_26_17_48.json

# 分析数组格式文件
python src/core/rag/code/test_show_benchmark.py .rag/benchmark/without-small_results_01_23_11_19.json
```

两种格式都能正确解析和分析。


