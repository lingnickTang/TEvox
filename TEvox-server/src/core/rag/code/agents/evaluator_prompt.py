"""
评估器 Agent 提示词模板
"""

EVALUATOR_PROMPTS = {
    "extract_references": """Extract all function calls and variables used in the following code.

Code:
```cpp
{code}
```

Task Query: {query}

Please extract:
1. **Functions called**: All function/method calls (e.g., `audio_service_.PlaySound()`, `ESP_ERROR_CHECK()`)
2. **Variables used**: All variables and member variables (e.g., `audio_service_`, `sound`)

Output in YAML format:
```yaml
functions:
  - <function call 1>
  - <function call 2>
  ...
variables:
  - <variable 1>
  - <variable 2>
  ...
```
""",

    "quantitative_evaluation": """Compare the generated code with the reference functions and variables extracted from ground truth.

Task Query: {query}

Generated Code:
```cpp
{generated_code}
```

Reference Functions (from ground truth):
{reference_functions}

Reference Variables (from ground truth):
{reference_variables}

Please identify:
1. **Correctly reused**: Functions and variables that are correctly used in the generated code(which means that it exists in both the generated code and the reference functions/variables)
2. **Incorrectly constructed**: Functions and variables that are wrong or missing

Output in YAML format:
```yaml
correctly_reused:
  functions:
    - <correctly used function 1>
    - <correctly used function 2>
    ...
  variables:
    - <correctly used variable 1>
    - <correctly used variable 2>
    ...
incorrectly_constructed:
  functions:
    - <wrong or missing function 1>
    - <wrong or missing function 2>
    ...
  variables:
    - <wrong or missing variable 1>
    - <wrong or missing variable 2>
    ...
```
""",

    "qualitative_evaluation": """Evaluate the quality of the generated code by comparing it with the ground truth.

Task Query: {query}

Ground Truth Code:
```cpp
{ground_truth}
```

Generated Code:
```cpp
{generated_code}
```

Please evaluate on three dimensions (each scored 0-100):

1. **Semantic Correctness** (0-100): Does the generated code have the same semantic meaning and logical flow as the ground truth?

2. **Structure Similarity** (0-100): How similar is the code structure (function signatures, control flow, API calls, etc.)?

3. **Functional Completeness** (0-100): Does the generated code cover all key functionalities present in the ground truth?

Output in YAML format:
```yaml
semantic_score: <0-100>
structure_score: <0-100>
completeness_score: <0-100>
analysis: |
  <Detailed analysis of the comparison>
```
"""
}

