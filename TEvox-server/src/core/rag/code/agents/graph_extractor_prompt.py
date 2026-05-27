GRAPH_EXTRACTOR_PROMPTS = {
    "decompose": """You are a code analysis agent. Based on SRP and the knowledge graph structure (file -> submodule -> function; function -> flow), decompose the requirement into two parts.

Context:
- target_file: {target_file}
- requirement: {requirement}
- description: {description}

System design (for reference when splitting steps and dependencies):
{system_design}

Instructions:
- Keep process_steps concise: use 3 to 6 steps at most; do not over-split (merge fine-grained steps into logical phases).
- Each step should be a meaningful phase of the implementation, not a single line of code.

Output in YAML:
1) process_steps: For the function to be completed, list the steps of the implementation flow. Each step has two fields:
   - step: short human-readable description of the step
   - retrieval: one short sentence for semantic retrieval (used to search flow-layer nodes in the graph)
2) dependency_modules: List of semantic descriptions of modules/capabilities this function depends on (used to search submodule-layer nodes).

```yaml
process_steps:
  - step: "<step description>"
    retrieval: "<short retrieval query for this step>"
  - step: "..."
    retrieval: "..."
dependency_modules:
  - "<module/capability description>"
  - "..."
```
""",

    "graph_collection_tool_planning": """You are a code analysis agent. Your task is to collect knowledge for a given requirement.
Current Context (may include decompose result with process_steps and dependency_modules):
{context}

Available Tools:
{tools_description}

Tool count: {tool_count}

You may use query_knowledge_graph with node_type "flow" or "submodule" to restrict retrieval to process or submodule layer.
First, based on the context, available tool descriptions, and the remaining number of tool invocations allowed, generate a list of tool usages you plan to perform (explicitly list tool name and intended args for each).
Then, analyze which reference functions are required to meet the user requirement, and specify for each which tool you intend to use.
Output your reasoning process.
Finally, output your decision in YAML format:

```yaml
plans:
    - tool_name: <tool_name>
      tool_args:
        <arg_name>: <arg_value>
    # ... (list of planned tool usages within allowed count)
```
""",

    "iterative_step_planning": """You are a code analysis agent. Your task is to collect knowledge from the SRP knowledge graph for a given requirement. You will do this iteratively: each round you see the current context (including any retrieval results so far), perform a brief flow/dependency decomposition based on SRP and the graph structure (file -> submodule -> function; function -> flow), then decide the single most needed retrieval for this round.

Current context (target_file, requirement, description, and previous retrieval results):
{context_summary}

Remaining tool invocations allowed this run: {remaining_count}

Available tool (you may only call this once per round):
{tools_description}

Instructions:
- Use the list of already-executed queries to avoid repeating the same retrieval and to decide what information is still missing; then choose the single most needed retrieval next.
- Based on the context, decide what information is most needed next: e.g. a flow-step semantic search (query + node_type "flow"), a dependency-module search (query + node_type "submodule"), or a 1-hop dataflow from the current function (node_id + neighbors_only=True, include_bodies=True).
- Output continue: true if you want to perform one query_knowledge_graph call this round; false if no more retrieval is needed.
- When continue is true, provide exactly one next_tool_call with tool_name "query_knowledge_graph" and tool_args (only query_knowledge_graph parameters: query (as hypothetical code!), node_type, node_id, neighbors_only, use_semantic, include_bodies).
- For the current function node to be completed, using neighbor nodes allows you to obtain all the nodes that call this function, but you cannot obtain the body of this function itself or the other nodes it depends on.
- To ensure fairness, the actual implementation or detailed steps of the current function have been hidden. You cannot retrieve them.

Queries already executed in this run. You need to decide what information is still missing (Since the same query return the same result, You MUST avoid repeating; You can use the list of already-executed queries to avoid repeating the same retrieval and to decide what information is still missing; then choose the single most needed retrieval next):
{issued_queries_summary}

Please first output the reasoning process of the query, then analyze the list of already-executed queries, if there is a repetition, modify the query above through reflection.
And then output the final query in YAML format:
```yaml
continue: true/false
next_tool_call:
  tool_name: query_knowledge_graph
  tool_args:
    query: "<query here>"
    node_type: "flow" | "submodule" | null
    node_id: "<optional; for neighbors_only>"
    neighbors_only: true/false
    use_semantic: true/false
    include_bodies: true/false
```
""",

    "a3_hypothetical_code": """Based on the requirement and description below, generate a short hypothetical code snippet (with comments) that could implement the function. This snippet will be used for semantic retrieval in a code knowledge graph; keep it under 30 lines.

Requirement: {requirement}
Description: {description}

Output in YAML with a single field "code" containing only the code snippet and comments, no explanation:
```yaml
code: |
  // your hypothetical code here
```
""",
}