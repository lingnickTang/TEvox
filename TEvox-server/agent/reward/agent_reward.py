import re
import json


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
    pattern = r"^<think>.*?</think>.*?<action>.*?</action>$"
    return re.match(pattern, text, re.DOTALL | re.MULTILINE)


def tag_count_reward(completions, **kwargs) -> list[float]:
    contents = [completion[0]["content"] for completion in completions]
    return [count_tags(c) for c in contents]


def format_reward(completions, **kwargs):
    completion_contents = [completion[0]["content"] for completion in completions]
    matches = [parse_format(content) for content in completion_contents]
    return [1.0 if match else 0.0 for match in matches]


def parse_json(json_str: str):
    pattern = r"```json(.*)```"
    matches = re.findall(pattern, json_str, re.DOTALL | re.MULTILINE)
    if not matches:
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
    if "tool_name" in extracted_action and "tool_args" in extracted_action:
        return extracted_action
    return None


def action_format_reward(completions, **kwargs):
    completion_contents = [completion[0]["content"] for completion in completions]
    actions = [extract_action(content) for content in completion_contents]
    return [1.0 if action else 0.0 for action in actions]
