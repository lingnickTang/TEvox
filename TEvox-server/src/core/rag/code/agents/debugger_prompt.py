"""
调试器 Agent 提示词模板
"""

DEBUGGER_PROMPTS = {
    "debug_task": """You are a debugging agent working on the following task:

Task: {task}

{context}

Available tools:
{tools_description}

You can:
1. Call a tool by outputting JSON: {{"tool_name": "tool_name", "tool_args": {{"arg1": "value1"}}}}
2. Finish by outputting: "task_complete: <summary>"

What would you like to do next? Output your decision in the format above.
""",

    "build_analysis": """Analyze the following build output and identify any errors or warnings:

Build Output:
{build_result}

Please provide your analysis in YAML format:
```yaml
success: true/false
fix_suggestions: |
  <suggestions for fixing errors, including what needs to be changed>
```
""",

    "extract_function_body": """Extract the relevant function code from the following file content according to the task description:

Task Description:
{task_description}

File Content:
{file_content}

Please provide the function code (the code related to the task description) in YAML format:
```yaml
function_code: |
  <The complete function code includes the signature and body>
```
""",

    "code_fix": """Based on the fix suggestions, generate a write_file tool call to fix the code.

Error Analysis and Fix Suggestions:
{fix_suggestions}

Original Code:
{code}

Task Description:
{task_description}

Please first generate the fixed code contained in the function body related to the task description, and then output the start and end line numbers of the original file to be replaced by the fixed code (if only one line is replaced, set start_line and end_line to the same line), and finally output the yaml format:
```yaml
start_line: <start_line_number> 
end_line: <end_line_number>
content: |
  <fixed_code_content> the content of which will replace the original content from the start line to the end line
```
"""
}

