# evox-server/src/core/rag/code/agents/graph_prompt.py
"""
图构建相关 prompt

- functionality_decompose: 针对文件/模块，按 API 聚类拆解为子模块（关注接口与职责划分）。
- function_flow_decompose: 针对单个函数，按执行/控制流拆解为可复用的子流（关注控制流与复用率）。
"""

GRAPH_PROMPTS = {
   "functionality_decompose": """As a professional software engineer, please:

1. First judge: if the current file/module already constitutes a single, independent, well-defined functional unit (one clear responsibility, self-contained, no need to split), then output no nodes—use an empty list: nodes: [].
2. Otherwise, according to the Single Responsibility Principle, classify and list the function APIs and variables implemented by the current module based on their functionality, forming decoupled functional submodules of the current module.
3. For each functional submodule, construct it as a new node. The goal is to improve reusability by decomposing a single module into smaller, single-responsibility submodules that can stand alone.
4. In the output, include the list of functions_label that are involved in (referenced by) the decomposed submodules—i.e. which of the given function labels belong to or are assigned to which submodule.

functions_label: list of function names/symbols in this module (for reference when decomposing)
{functions_label}

file_content:
{file_content}

Please output your results in YAML format inside the ```yaml ``` mark.


nodes: node information for all sub-modules(except the current module). Use nodes: [] when the current module is already independent and needs no decomposition.
   - id: decomposed sub-node name
   - code: "line1\\nline2\\n..."  (the detailed API/variables and comments for this sub-node)
   - involved_functions: list of function labels from the input functions_label that are involved in the decomposition (only those actually referenced/assigned in the submodules)
""",

   "function_flow_decompose": """As a professional software engineer, please:

1. First judge: if the given function itself already constitutes a single, independent, well-defined control flow or data flow (one clear responsibility, self-contained), then output no nodes—use an empty list: nodes: [].
2. Otherwise, according to the Single Responsibility Principle, analyze the function and identify distinct execution/control-flow blocks that could be extracted as reusable sub-flows (e.g., validation, transformation, I/O, error handling). Focus on control flow and execution semantics, not API clustering.
3. Each decomposed flow MUST be a complete control flow or data flow—self-contained and usable as an independent, well-defined functionality (with clear inputs, outputs, and behavior). Do not output partial or fragmentary flows that depend on inlined context from the original function.
4. For each such flow, construct it as a new node. The goal is to improve reusability by decomposing a coupled function into smaller, single-responsibility flows that can stand alone.
5. In the output, include the list of outgoing_functions_label that are involved in (called by) each decomposed sub-flow—i.e. which of the given function labels are referenced/called in which sub-flow.

outgoing_functions_label: list of function names/symbols that may be called from this function (for reference when decomposing)
{outgoing_functions_label}

function_name: {function_name}
function_body:
{function_body}

Please output your results in YAML format inside the ```yaml ``` mark.
  - id: SubFlowName
  - code: "// comment\\n#if CONFIG_FOO\\n  do_something();\\n#endif"
  - involved_functions: list of function labels from the input outgoing_functions_label that are involved in this sub-flow (only those actually called/referenced in the sub-flow)
""",

    "graph_knowledge_extraction": """Based on the collected knowledge graph retrieval results and context, summarize the relevant knowledge graph information for the requirement.

Context:
{context}

Please extract and summarize: relevant nodes (functions/symbols), dependency relationships, and any implementation hints from the knowledge graph that can help implement the requirement.

Output format:
## Graph Knowledge Summary
### Relevant Nodes / Functions
- <node id or label with file>
### Dependency / Call Relationships
- <brief description>
### Implementation Hints
- <brief hints from graph context>
""",
}
