"""
知识提取 Agent 提示词模板
"""

KNOWLEDGE_EXTRACTOR_PROMPTS = {
    "SRP_KG": """
      The Single Responsibility Principle (SRP) Knowledge Graph architecture is designed to address high coupling and low reusability in embedded codebases by decomposing physical files into cohesive logical units. This framework follows a four-layer hierarchy: 
      the File Layer represents physical boundaries; 
      the Submodule Layer defines logical boundaries such as DeviceStateManager; 
      the Function Layer handles calling boundaries; 
      and the Flow Layer captures execution logic through fine-grained steps like InitializeWakenetModel. 
      Two core relationships govern this graph: "contains" denotes structural hierarchy, while "depends_on" maps logical and data dependencies. 
      By shifting from coarse file-level associations to precise submodule and flow-level interactions, the agent can perform granular code retrieval and impact analysis.
    """,
    # 仅包含 file 和 function 两层内容
    "KG": """ 
     The knowledge graph (KG) is a graph that contains file and function nodes. The file nodes are the physical boundaries of the codebase, and the function nodes are the calling boundaries of the codebase.
     Two core relationships govern this graph: "contains" denotes structural hierarchy, while "depends_on" maps logical and data dependencies.
    """,
    "system_design_extraction": """As a professional software engineer, analyze the following code files from the main directory and identify the system modules.

File list:
{file_paths}

Please identify the main modules/components in this system and their corresponding file paths.

Output in YAML format:
```yaml
modules:
  - name: module_name
    file_paths:
      - path/to/file1.cc
      - path/to/file1.h
  - name: another_module_name
    file_paths:
      - path/to/file2.cc
      - path/to/file2.h
```
""",
    "module_interface_extraction": """
As a professional software engineer, please extract the interface and give explanation of the provided code.

output example:
- virtual void ShowNotification(const std::string &notification, int duration_ms = 3000) - Display notification message (std::string version), default duration is 3 seconds
- ...

**INPUT PARAMETERS**:
Headers:
{headers}
""",
    "implementation_flow_analysis": """
Analyze the header files:
{header_files}

Identify reusable functions for the requirement:
{requirement}

Create a step-by-step and simple implementation flow with functions needed in each step

You need to output the implementation flow in the following format:
## Implementation Flow
### Step 1: <description>
- <function signature include parameters and return value> from <file_path>

### Step 2: <description>
...
""",
    "header_keyword_extraction": """
Assume you are an embedded software engineer. According to the current system design and file list, you think which modules are involved in the current system, for each module list the corresponding keywords, each keyword should appear in at least one file path. Directly output the keywords in YAML format:

System Design Knowledge:
{system_design}

File List:
{file_list}

```yaml
- keyword1
- keyword2
- keyword3
  ...
```
""",
    "knowledge_collection_tool_planning": """You are a code analysis agent. Your task is to collect knowledge for a given requirement.
Current Context:
{context}

Available Tools:
{tools_description}

Analyze what information you need to collect knowledge. If there is no more knowledge to collect, output false. Otherwise, output true and decide which tool to call next.
First, output your reasoning, then output your decision in YAML format:
```yaml
continue: true/false  # true if more tools need to be called, false if no more knowledge to collect
next_tool_call:
  tool_name: <tool_name>
  tool_args:
    <arg_name>: <arg_value>
```
""",

"similar_implementation_extraction": """Based on the collected information, extract similar implementation knowledge for the requirement.

Context:
{context}

Please extract and summarize similar implementation patterns, reusable code snippets, and relevant knowledge that can help implement the requirement.

Output format:
## Similar Implementation Knowledge
### Reusable Code Snippets:
```cpp
<code snippet>
```
""",
    "system_design_file_filter": """As a professional embedded software engineer, analyze the following file list and filter out header files (.h, .hpp) that will be used to implement the hardware platform "{hardware_type}" and xiaozhi AI software application.

File list:
{file_list}

Output in YAML format:
```yaml
- path/to/file1.h
- path/to/file2.h
- path/to/file3.hpp
```
""",
    "system_design_generation": """You are a professional embedded systems architect. Based on the following header file contents related to the hardware platform "{hardware_type}", generate a system design knowledge document.

File contents:
{file_contents}

Please generate the system design document in the following format:

## System Design Knowledge

### I. Hardware Layer

**Core Hardware Platform**: [Identify the main hardware platform from the code]

**Main Hardware Components**:
- [List the main hardware components identified from the code, such as audio systems, display systems, communication interfaces, etc.]

**Physical Resources**: [MCU internal resources]

---

### II. Hardware Abstraction Layer (HAL)

**Base Framework**: [Identify the base framework, such as ESP-IDF, FreeRTOS, etc.]

**Core Abstraction Modules**:
1. [Module 1 Name]: [Description]
2. [Module 2 Name]: [Description]
...

---

### III. Middleware Layer

**Core Protocol Stacks and Algorithm Libraries**:
1. [Middleware 1]: [Description]
2. [Middleware 2]: [Description]
...

---

### IV. Application Layer

**Core Business Logic**:
1. [Application Module 1]: [Description]
2. [Application Module 2]: [Description]
...

---

## Module Dependency Quick Reference

**Common Modules**:
- [Module Name]: Access through [Interface/Module]

**Example**: [Provide a simple usage example]

---

Requirements:
1. Base the content on actual code information, do not fabricate
2. Keep it concise, highlight the core architecture
3. If certain information cannot be determined from the code, mark it as "To be confirmed"
"""
}

