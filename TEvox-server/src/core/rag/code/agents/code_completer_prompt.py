"""
代码补全 Agent 提示词模板
"""

CODE_COMPLETER_PROMPTS = {
    "generate_function_code": """
Suppose you are an embedded system engineer. You are given a requirement and a file content. You need to generate the function code that implements the requirement.

Context:
{context}

First generate the analysis based on the context above, and then generate the function code(all the code needs to be included in the function body) inside the ```cpp ``` mark based on the following requirement:
{requirement}
""",

    "filter_module_interface": """
You are a context manager for a code development agent. The system design lists all module names in the current system.
System Design: {system_design}

Based on the user's requirement and the file content to be modified, determine which module interface information you need. Output only the names of the modules you require.

Requirement: {requirement}
File Content: {file_content}

Output the module names you need by comma separated without spaces.
""",

    "complete_function": """
Given the file content and the code to be written, analyze the start and end position of the function to be completed, and determine how to write the new code using the write_file tool.

File Path: {file_path}

Current File Content:
```
{file_content}
```

Code to Write:
```cpp
{code}
```
Determine the start and end line of the file to be replaced by the generated code:
- start_line: line number where to start (integer)
- end_line: line number where to end (integer, or -1 for end of file)

Output in YAML format:
```yaml
start_line: <integer>
end_line: <integer or -1>
```
""",

    "reflection_tool_planning": """You are a code reflection agent. Your task is to check the generated code for potential issues related to implicit relationships in embedded systems (e.g., constructing functions or variables that do not exist in the current repository, event dependencies, hardware resource conflicts, ISR interactions, timing constraints, message patterns, etc.).

Current Context:
{context}

Available Tools:
{tools_description}

Analyze what information you need to check the generated code.

Output in YAML format:
```yaml
continue: true
next_tool_call:
  tool_name: <tool_name>  # one of: find_references, find_in_files, get_directory_files
  tool_args:
    <arg_name>: <arg_value>
```
""",

    "refine_code_from_reflection": """Based on the information collected, refine the generated code to address the identified issues.

Context:
{context}

Please first analyze what problems there are in the generated function based on the information collected and finally regenerate the function that fix these problems above in the ```cpp ``` marks.
```cpp
# The function code related to the requirement: {requirement}
```
"""
}

