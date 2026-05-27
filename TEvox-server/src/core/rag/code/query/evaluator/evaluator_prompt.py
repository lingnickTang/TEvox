# evox-server/src/core/rag/code/query/evaluator/evaluator_prompt.py

EVALUATOR_PROMPTS = {
    "context_blocks": """Suppose you are a professional embedded system software engineer. Evaluate the effectiveness of the given context code blocks for generating code to answer the query.

Query: {query}

Context code blocks:
{context_blocks}

Please analyze the relevance of each context code block to the query for code generation and return the result in the following JSON format:
```json
{{
    "effective_block_ids": ["list of effective context block IDs"]
}}
```

Evaluation criteria:
1. Context code blocks that contain functions, classes, or patterns directly related to the query's code generation requirements
2. Context code blocks that provide implementation examples or templates for the requested functionality
3. Context code blocks that contain relevant APIs, libraries, or frameworks needed for code generation
4. Context code blocks that demonstrate similar coding patterns or logic structures required by the query""",

    "query_relevance_scoring": """Suppose you are a professional embedded system software engineer. Evaluate how relevant each context code block is to answering the given query.

Query: {query}

Context code blocks:
{context_blocks}

Please evaluate each context block and provide a relevance score (1-10 scale) for query relevance.

Scoring guidelines:
- 9-10: Directly implements the requested functionality or provides essential patterns
- 7-8: Contains important supporting code, APIs, or related functionality
- 5-6: Provides some useful context or helper functions
- 3-4: Marginally relevant, contains some useful information
- 1-2: Not relevant or only tangentially related

Please return the result in the following JSON format:
```json
{{
    "block_scores": [
        {{
            "block_id": "block_id_1",
            "query_relevance": 8
        }},
        {{
            "block_id": "block_id_2",
            "query_relevance": 6
        }}
    ]
}}
```""",

    "code_relevance_scoring": """Suppose you are a professional embedded system software engineer. Evaluate how relevant each context code block is to the generated code.

Generated Code:
{generated_code}

Context code blocks:
{context_blocks}

Please evaluate each context block and provide a relevance score (1-10 scale) for code relevance.

Scoring guidelines:
- 9-10: Directly referenced or heavily used in the generated code
- 7-8: Provides important patterns, APIs, or structures used in generated code
- 5-6: Contains some elements that influenced the generated code
- 3-4: Marginally related to the generated code
- 1-2: Not related to the generated code

Please return the result in the following JSON format:
```json
{{
    "block_scores": [
        {{
            "block_id": "block_id_1",
            "code_relevance": 7
        }},
        {{
            "block_id": "block_id_2",
            "code_relevance": 9
        }}
    ]
}}
```""",

    "generate_answer": """Suppose you are a professional embedded system software engineer. Based on the following query and effective context code, generate the requested code:

Query: {query}

Effective context code:
{effective_context}

Please generate the code requested in the query based on the effective context code. The generated code should:
1. Implement the functionality requested in the query
2. Try to use patterns, APIs, and structures from the effective context code as reference
3. Include proper error handling, comments, and best practices shown in the context
4. Be complete, functional, and ready to use

Generated code:""",

    "function_novelty_scoring": """Suppose you are a professional embedded system software engineer. Evaluate the novelty of each function in the generated code compared to the provided context code blocks.

Generated Code:
{generated_code}

Context Code Blocks:
{context_blocks}

Please analyze each function in the generated code and provide a novelty score (1-10 scale) for each function.

Scoring guidelines:
- 9-10: Completely novel function, not found in context or significantly different
- 7-8: Mostly novel with some inspiration from context
- 5-6: Adapted from context with moderate changes
- 3-4: Heavily based on context with minor modifications
- 1-2: Directly copied or only slightly modified from context

Please return the result in the following JSON format:
```json
{{
    "function_scores": [
        {{
            "function_name": "main_function",
            "function_signature": "int main(int argc, char* argv[])",
            "novelty_score": 8
        }},
        {{
            "function_name": "error_handler",
            "function_signature": "void error_handler(int error_code)",
            "novelty_score": 3
        }}
    ]
}}
```""",
    
    "reuse_evaluation": """You are a C++ code analysis expert. Please analyze the code reuse between the generated code and the actual code.

Actual code:
```cpp
{actual_code}
```

Generated code:
```cpp
{generated_code}
```

Please complete the following steps:

1. Extract and output, one by one, the external functions/variables that the actual code depends on, in the following format:
{{
<function_or_variable_name>
}}

2. Extract and output, one by one, the external functions/variables that the generated code depends on, in the following format:
{{
<function_or_variable_name>
}}

3. Calculate the counts of TP/FP/FN:
   - TP (True Positive): Functions/variables from the actual code that are correctly reused in the generated code.
   - FP (False Positive): Functions/variables reused in the generated code that do not exist in the actual code.
   - FN (False Negative): Functions/variables in the actual code that are not reused in the generated code.

4. Finally, output the results in YAML format, as follows:
```yaml
tp: <count>
fp: <count>
fn: <count>
```
"""
}