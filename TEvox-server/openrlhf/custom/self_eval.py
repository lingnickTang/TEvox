from pydantic import BaseModel, Field


from src.utils import get_llm, Agent


class Reward(BaseModel):
    reward: int = Field(ge=-10, le=10, description="The reward value for the action.")
    feedback: str = Field(description="The feedback to improve the action.")


pre_prompt = """You are an evaluator of the action taken by an autonomous agent.

### The historical trajectories of the agent are as follows:
```
{context}
```

### The current action taken by the agent is as follows:
```
{action}
```

### The evaluation criteria of the action is as follows:
```
1. First, evaluate whether it is necessary to execute any prerequisite actions before proceeding with the current action. If there are any prerequisite actions, give a negative reward and provide feedback to suggest executing the prerequisite actions.
2. If there are no prerequisite actions, then evaluate whether it is necessary to break down the current action into smaller actions to reduce complexity. If further decomposition is necessary, give a negative reward and provide feedback to suggest breaking down the current action.
3. If it is not necessary to break down the current action, then evaluate where the current action is specific and detailed to achieve the task. If the current action is not specific and detailed, give a negative reward and provide feedback to suggest making the current action more specific and detailed.
```

Finally, evaluate the action in JSON format:
```json
{{
    "reward": "The reward value for the action, between -10 and 10, positive for good actions and negative for bad actions, the higher the better.",
    "feedback": "The feedback to improve the action and explain why it is necessary.",
}}
```"""

post_prompt = """You are an evaluator of the action taken by an autonomous agent.

### The historical trajectories of the agent are as follows:
```
{context}
```

### The current action taken by the agent is as follows:
```
{action}
```

### The execution feedback of the current action is as follows:
```
{feedback}
```

### The evaluation criteria of the action is as follows:
```
1. First, evaluate whether it is necessary to execute any prerequisite actions before proceeding with the current action. If there are any prerequisite actions, give a negative reward and provide feedback to suggest executing the prerequisite actions.
2. If there are no prerequisite actions, then evaluate whether it is necessary to break down the current action into smaller actions to reduce complexity. If further decomposition is necessary, give a negative reward and provide feedback to suggest breaking down the current action.
3. If it is not necessary to break down the current action, then evaluate where the current action is specific and detailed to achieve the task. If the current action is not specific and detailed, give a negative reward and provide feedback to suggest making the current action more specific and detailed.
4. Based on the execution feedback, evaluate whether the current action helps to complete the task. If the action does not contribute to task completion, give a negative reward and provide feedback explaining why it's not helpful.
```

Finally, evaluate the action in JSON format:
```json
{{
    "reward": "The reward value for the action, between -10 and 10, positive for good actions and negative for bad actions, the higher the better.",
    "feedback": "The feedback to improve the action and explain why it is necessary."
}}
```"""


def pre_eval(prompts, completion):
    res = Agent(get_llm(), msgs=[]).invoke_with_structured_output_once(
        input=pre_prompt.format(
            context="\n\n".join([msg["content"] for msg in prompts]),
            action=completion,
        ),
        schema=Reward,
    )
    return res


def post_eval(prompts, completion, feedback):
    res = Agent(get_llm(), msgs=[]).invoke_with_structured_output_once(
        input=post_prompt.format(
            context="\n\n".join([msg["content"] for msg in prompts]),
            action=completion,
            feedback=feedback,
        ),
        schema=Reward,
    )
    return res
