from pydantic import BaseModel, Field


class Node(BaseModel):
    name: str = Field(description="The name of the task")
    spec: str = Field(description="The specification of the task")
    subtasks: list["Node"] = Field(
        default_factory=list, description="The subtasks of the task"
    )
    causality: str = Field(default="", description="The causality among the subtasks")


system_prompt = """You are an evaluator of the action taken by an autonomous agent.

### The task of the agent is as follows:
```
{task}
```

### The historical trajectories of the agent are as follows:
```
{context}
```"""

decision_prompt = """Now you are learning experiences from the planning and execution process of the task.

The refined planned task tree is as follows:
```
{refined_task_tree}
```

To attempt to complete the task `{task}`, evaluate whether breaking down the task into subtasks that have been executed is necessary based on the historical trajectories of the agent. If further decomposition to reduce complexity is necessary, return "YES". If further decomposition to reduce complexity is unnecessary, return "NO". Finally, output in JSON format:
```json
{{
    "decision": "YES | NO",
}}
```"""

expand_node_prompt = """Now you are learning experiences from the planning and execution process of the task.

The refined planned task tree is as follows:
```
{refined_task_tree}
```

To attempt to complete the task `{task}`, clarify the current task and summarize the helpful subtasks that have been executed based on the historical trajectories of the agent. Finally, output in JSON format:
```json
{{
    "name": "The name of the task",
    "spec": "The specification of the task",
    "subtasks": [
        {{
            "name": "The name of the subtask",
            "spec": "The specification of the subtask"
        }}
    ],
    "causality": "The causality among the subtasks"
}}
```"""

summarize_system_prompt = """You are an evaluator of the action taken by an autonomous agent.

### The historical trajectories of the agent are as follows:
```
{context}
```"""

summarize_node_prompt = """Now you are only learning experiences from the planning and execution process of the task.

The task tree is as follows:
```
{task_tree}
```

The current task you are reviewing is as follows:
```
{task}
```

To attempt to complete the current task, summarize a guide (including applicable scenarios, solution tutorials, knowledge indicies, causality explanation, etc.) to complete the task based on the historical trajectories. Finally, output concisely in natural language."""
