import re
import json
from agent.dataset.prompt import format_feedback, tools, feedback_prompt
from src.base import ToolCall
from agent.reward.self_eval import self_eval
from src.utils import logger


def count_tags(text: str) -> float:
    count = 0.0
    if text.count("<think>") == 1:
        count += 0.25
    if text.count("</think>") == 1:
        count += 0.25
    if text.count("<action>") == 1:
        count += 0.25
    if text.count("</action>") == 1:
        count += 0.25
    return count


def parse_format(text: str):
    pattern = r"^<think>.*?</think>\s*<action>.*?</action>$"
    return re.match(pattern, text, re.DOTALL)


def parse_json(json_str: str):
    pattern = r"^```json(.*)```$"
    matches = re.findall(pattern, json_str, re.DOTALL)
    if not matches or len(matches) > 1:
        return None
    try:
        return json.loads(matches[-1])
    except Exception as e:
        return None


def extract_action(text: str) -> str | None:
    extracted_action = re.search(r"<action>(.*?)</action>", text, re.DOTALL)
    if not extracted_action:
        return None
    extracted_action = parse_json(extracted_action.group(1).strip())
    if not extracted_action:
        return None
    try:
        return ToolCall.model_validate(extracted_action)
    except Exception as e:
        return None


def feedback(prompts, completions, **kwargs):
    completion_contents = [completion[0]["content"] for completion in completions]
    rewards = []
    for prompt, completion in zip(prompts, completion_contents):
        # reward = {
        #     "reward": 0.0,
        #     "feedback": "",
        # }
        reward = {
            "reward": count_tags(completion),
            "feedback": "",
        }

        if not parse_format(completion):
            reward["feedback"] = format_feedback
            rewards.append(reward)
            continue
        else:
            reward["reward"] += 1.0

        action = extract_action(completion)
        if not action:
            reward["feedback"] = format_feedback
            rewards.append(reward)
            continue
        else:
            reward["reward"] += 1.0

        try:
            tools.execute_tool(action)
            reward["reward"] += 1.0
        except Exception as e:
            reward["feedback"] = str(e)
            rewards.append(reward)
            continue

        try:
            self_eval_reward = self_eval(prompt, completion)
            # reward["reward"] += min(max(0.0, self_eval_reward.reward), 1.0)
            reward["reward"] += min(max(0.0, self_eval_reward.reward), 10.0)
            reward["feedback"] = self_eval_reward.feedback
        except Exception as e:
            logger.error(f"Error in self_eval: {e}")

        rewards.append(reward)

    return rewards


def feedback_with_prompts_and_completions(prompts, completions, **kwargs):
    rewards = feedback(prompts, completions, **kwargs)
    feedbacks = []
    for i, reward in enumerate(rewards):
        if not reward["feedback"]:
            feedbacks.append(
                {
                    "reward": reward["reward"],
                    "feedback": "",
                }
            )
            continue
        feedbacks.append(
            {
                "reward": reward["reward"],
                "feedback": [
                    {
                        "role": "assistant",
                        "content": completions[i][0]["content"],
                    },
                    {
                        "role": "user",
                        "content": feedback_prompt.format(feedback=reward["feedback"]),
                    },
                ],
            }
        )
    return feedbacks


def feedback_with_real_number(prompts, completions, **kwargs):
    rewards = feedback(prompts, completions, **kwargs)
    feedbacks = [reward["reward"] for reward in rewards]
    return feedbacks
