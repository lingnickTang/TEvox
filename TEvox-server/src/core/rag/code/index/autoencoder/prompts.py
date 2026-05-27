"""
AutoEncoder Agent Prompts
包含所有用于自编码器代理的提示模板
"""

# 从全局变量生成文档的提示词
generate_document_from_global_variable_prompt = """
You are a code analysis expert. Analyze the following global variable and provide a structured description.

Global Variable Name: {variable_name}
File Path: {file_path}
Definition: {definition}
Number of References: {references_count}
Number of Referencing Files: {referencing_files_count}

Please describe:
1. What is the purpose of this global variable? (what)
2. How is it defined and used in the codebase? (how)

Note that the description of what and how must be in the form of strings
Output in JSON format:
```json
{{
    "what": "the purpose of this global variable",
    "how": "How is it defined and used in the codebase"
}}
```
"""

# 从文档生成全局变量的提示词
generate_global_variable_from_document_prompt = """
You are a code generation expert. Based on the following description, recreate a global variable implementation.

Description:
What: {what_description}
How: {how_description}

Please generate appropriate global variable declaration based on the description.
Output the generated code in the following format:
```
[Generated code here]
```
"""

# 决定是否需要重新生成全局变量文档的提示词
decide_global_variable_regeneration_or_stop_prompt = """
You are a quality control expert. Compare the original global variable information with the regenerated information to determine if we need to regenerate the document.

Original Global Variable:
Name: {original_variable_name}
File: {original_file_path}
Definition: {original_definition}

Regenerated Information:
{regenerated_variable_info}

Please decide: Should we regenerate the document? Why?

Format your response as JSON with 'action' ('regenerate' or 'stop') and 'reason'.
Output in JSON format:
```json
{{
    "action": "regenerate" | "stop",
    "reason": "Explain the comparison result and why you decide to regenerate or stop, considering both functional and implementation aspects"
}}
```
"""

# 基于全局变量信息重新生成文档的提示词
regenerate_document_from_global_variable_prompt = """
You are an experienced software engineer. Improve the documentation for a global variable based on the differences between the original information and the regenerated information.

Original Global Variable:
Name: {original_variable_name}
File: {original_file_path}
Definition: {original_definition}

Current Documentation:
What: {current_what}
How: {current_how}

Regenerated Information:
{regenerated_variable_info}

Please improve the documentation by updating the 'what' and 'how' descriptions.
Note that the description of what and how must be in the form of strings
Output in JSON format:
```json
{{
    "what": "the purpose of this global variable",
    "how": "How is it defined and used in the codebase"
}}
```
"""

# 原有的基础prompt
generate_document_from_code_prompt = """
The target code to be analyzed is as follows:
```
{target_code}
```

The context information for this code (including function calls and dependencies) is as follows:
'''
{context}
'''

Based on the target code and its context, generate comprehensive documentation that includes both functional descriptions (WHAT) and implementation details (HOW). The documentation should be detailed enough that the code functionality can be fully reproduced.

Please provide your response in JSON format with two fields:
- "what": Describe WHAT the code does - the functional purpose, responsibilities, and behavior, considering the context
- "how": Describe HOW the code works - the implementation details, algorithms, data structures, and technical approaches used

Note that the description of what and how must be in the form of strings
Output in JSON format:
```json
{{
    "what": "Functional description of what the code does, including its purpose, responsibilities, and how it fits within the given context",
    "how": "Implementation details of how the code works, including algorithms, data structures, technical approaches, and interaction patterns with other components"
}}
```
"""

generate_code_from_document_prompt = """
The documentation describing the code includes both functional descriptions (WHAT) and implementation details (HOW):

WHAT (Functional Description):
'''
{what_description}
'''

HOW (Implementation Details):
'''
{how_description}
'''

Based on both the functional descriptions (WHAT) and implementation details (HOW), generate the actual code that implements the described functionality. The generated code should accurately reflect both the purpose described in the WHAT section and the technical implementation approach described in the HOW section.

Output the generated code in the following format:
```
[Generated code here]
```
"""

regenerate_document_from_code_prompt = """
The target code to be reproduced is as follows:
```
{target_code}
```
The current documentation with WHAT and HOW is as follows:
WHAT (Functional Description):
'''
{current_what}
'''
HOW (Implementation Details):
'''
{current_how}
'''
The code regenerated from the documentation is as follows:
'''
{regenerated_code}
'''

First, compare the target code with the regenerated code to identify any differences in procedural abstraction regardless of the implementation language. Then, improve both the WHAT (functional description) and HOW (implementation details) so that the functionality of target code can be fully reproduced, ensuring alignment with its procedural abstraction.
Note that the description of what and how must be in the form of strings
Output the improved documentation in JSON format:
```json
{{
    "what": "Improved functional description of what the code does, addressing any missing or incorrect elements",
    "how": "Improved implementation details of how the code works, addressing any missing or incorrect technical aspects"
}}
```
"""

decide_regenerate_or_stop_from_code_prompt = """
The target code to be reproduced is as follows:
```
{target_code}
```
The current documentation with WHAT and HOW is as follows:
WHAT (Functional Description):
'''
{current_what}
'''
HOW (Implementation Details):
'''
{current_how}
'''
The code regenerated from the documentation is as follows:
'''
{regenerated_code}
'''

Please compare the target code with the regenerated code to identify any differences in procedural abstraction regardless of the implementation language. Evaluate whether the current WHAT and HOW documentation accurately captures the target code's functionality and implementation. 

If the regenerated code's function and implementation approach match the target code, return "stop". If there are significant differences in functionality, logic, or implementation details, return "regenerate".

Output in JSON format:
```json
{{
    "action": "regenerate" | "stop",
    "reason": "Explain the comparison result and why you decide to regenerate or stop, considering both functional and implementation aspects"
}}
```
"""

# 结构化信息提取相关的prompt
extract_structured_info_from_file_prompt = """
The target file content to be analyzed is as follows:
```
{file_content}
```

The functional descriptions for each function in the file are as follows:
'''
{function_descriptions}
'''

Based on the file content and the provided function descriptions, extract and organize the structured information about the file. Analyze the file's overall organization, structure, and the role of each component within the file architecture.

Output in the following format:
```
FILE_STRUCTURE_ANALYSIS:
- File: {filename}
  Purpose: Overall purpose and responsibility of this file
  Architecture: How the file is organized and structured

STRUCTURED_ELEMENTS:
- Function: function_name(param1: type, param2: type) -> return_type
  Purpose: Functional description from the provided descriptions
  Role: How this function fits within the file's overall architecture
- Class: ClassName
  Purpose: Description of the class purpose and responsibility
  Methods: list of method signatures with their purposes
  Attributes: list of attributes with types and purposes
  Role: How this class fits within the file's overall architecture
- [Additional elements...]

DEPENDENCIES_AND_RELATIONSHIPS:
- Internal: relationships between functions/classes within this file
- External: dependencies on external modules or files
- Data Flow: how data flows between different components

ARCHITECTURAL_PATTERNS:
- Pattern: identified design patterns or architectural approaches
- Implementation: how these patterns are implemented in the file
```
"""

generate_document_from_file_prompt = """
The structured information extracted from the target code is as follows:
'''
{structured_info}
'''

Based on this structured information, generate comprehensive documentation that includes both functional descriptions (WHAT) and implementation details (HOW). The documentation should be detailed enough that an LLM could regenerate the original structured elements (functions, classes, etc.) with the same signatures and functionality.

Please provide your response in JSON format with two fields:
- "what": Describe WHAT the code does - the functional purpose, responsibilities, and behavior of each element
- "how": Describe HOW the code works - the implementation details, algorithms, data structures, and technical approaches used

Output in JSON format:
```json
{{
    "what": "Functional description of what the code does, including the purpose and responsibilities of each structured element (functions, classes, etc.)",
    "how": "Implementation details of how the code works, including algorithms, data structures, technical approaches, and interaction patterns between elements"
}}
```
"""

generate_file_from_document_prompt = """
The documentation describing the code structure includes both functional descriptions (WHAT) and implementation details (HOW):

WHAT (Functional Description):
'''
{what_description}
'''

HOW (Implementation Details):
'''
{how_description}
'''

Based on both the functional descriptions (WHAT) and implementation details (HOW), extract and regenerate the structured elements (functions, classes, structs, etc.) that should exist in the code. Use the WHAT to understand the purpose and responsibilities, and the HOW to understand the technical implementation details. Provide the same format as the original structured information extraction. Output in the following format:
```
STRUCTURED_ELEMENTS:
- Function: function_name(param1: type, param2: type) -> return_type
  Description: Brief description of what the function does
- Class: ClassName
  Description: Brief description of the class purpose
  Methods: list of method signatures
  Attributes: list of attributes with types
- [Additional elements...]
```
"""

regenerate_document_from_file_prompt = """
The original structured information is as follows:
'''
{original_structured_info}
'''
The current documentation with WHAT and HOW is as follows:
WHAT (Functional Description):
'''
{current_what}
'''
HOW (Implementation Details):
'''
{current_how}
'''
The regenerated structured information from the documentation is as follows:
'''
{regenerated_structured_info}
'''

Compare the original and regenerated structured information to identify any missing or incorrect elements. Then, improve both the WHAT (functional description) and HOW (implementation details) so that they can accurately reproduce all the original structured elements. 

Output the improved documentation in JSON format:
```json
{{
    "what": "Improved functional description of what the code does, addressing any missing or incorrect elements",
    "how": "Improved implementation details of how the code works, addressing any missing or incorrect technical aspects"
}}
```
"""

decide_regenerate_or_stop_from_file_prompt = """
The original structured information is as follows:
'''
{original_structured_info}
'''
The regenerated structured information from documentation is as follows:
'''
{regenerated_structured_info}
'''

Compare these two structured information sets to determine if they match in terms of function signatures, class definitions, method signatures, and overall structural elements. If the regenerated information accurately captures all the original structured elements, return "stop". If there are missing functions, incorrect signatures, or structural differences, return "regenerate". Output in JSON format:
```json
{{
    "action": "regenerate" | "stop",
    "reason": "Explain the comparison result and why you decide to regenerate or stop"
}}
```
"""

generate_document_from_directory_tree_prompt = """
The directory tree analysis is as follows:
'''
{directory_tree_info}
'''

Based on this directory tree analysis, generate comprehensive documentation that includes both functional descriptions (WHAT) and implementation details (HOW). The documentation should be detailed enough that someone could understand the project structure and recreate a similar directory organization.

Please provide your response in JSON format with two fields:
- "what": Describe WHAT the project does - the overall purpose, responsibilities, key components, and how the project is organized
- "how": Describe HOW the project is structured - the implementation details, directory organization principles, file relationships, and architectural patterns used

Output in JSON format:
```json
{{
    "what": "Functional description of what the project does, including overall purpose, key components, module responsibilities, and organizational principles",
    "how": "Implementation details of how the project is structured, including directory organization, file relationships, architectural patterns, and development workflow"
}}
```
"""

generate_directory_tree_from_document_prompt = """
The project documentation describing the directory structure includes both functional descriptions (WHAT) and implementation details (HOW):

WHAT (Functional Description):
'''
{what_description}
'''

HOW (Implementation Details):
'''
{how_description}
'''

Based on both the functional descriptions (WHAT) and implementation details (HOW), regenerate the directory tree structure analysis that should represent the project. Use the WHAT to understand the project purpose and organization, and the HOW to understand the technical structure and patterns. Provide the same format as the original directory tree analysis.

Output in the following format:
```
DIRECTORY_STRUCTURE_ANALYSIS:
- Root: project_name
  Description: Brief description of the project
- Directory: directory_name/
  Description: Purpose and contents of this directory
  Files: list of important files and their types
  Subdirectories: list of subdirectories
- [Additional directories...]

ARCHITECTURAL_PATTERNS:
- Pattern: pattern_name
  Description: How this pattern is implemented in the directory structure
- [Additional patterns...]

PROJECT_ORGANIZATION:
- Component: component_name
  Location: path/to/component
  Purpose: what this component does
- [Additional components...]
```
"""

regenerate_document_from_directory_tree_prompt = """
The original directory tree analysis is as follows:
'''
{original_directory_tree_info}
'''
The current project documentation with WHAT and HOW is as follows:
WHAT (Functional Description):
'''
{current_what}
'''
HOW (Implementation Details):
'''
{current_how}
'''
The regenerated directory tree analysis from the documentation is as follows:
'''
{regenerated_directory_tree_info}
'''

Compare the original and regenerated directory tree analyses to identify any missing directories, incorrect descriptions, or structural differences. Then, improve both the WHAT (functional description) and HOW (implementation details) so that they can accurately reproduce all the original directory structure and organization.

Output the improved documentation in JSON format:
```json
{{
    "what": "Improved functional description of what the project does, addressing any missing or incorrect organizational elements",
    "how": "Improved implementation details of how the project is structured, addressing any missing or incorrect structural aspects"
}}
```
"""

decide_regenerate_or_stop_from_directory_tree_prompt = """
The original directory tree analysis is as follows:
'''
{original_directory_tree_info}
'''
The regenerated directory tree analysis from documentation is as follows:
'''
{regenerated_directory_tree_info}
'''

Compare these two directory tree analyses to determine if they match in terms of directory structure, file organization, architectural patterns, and project components. If the regenerated analysis accurately captures all the original directory structure and organization, return "stop". If there are missing directories, incorrect descriptions, or structural differences, return "regenerate". Output in JSON format:
```json
{{
    "action": "regenerate" | "stop",
    "reason": "Explain the comparison result and why you decide to regenerate or stop"
}}
```
""" 