import re


def count_tags(text: str) -> float:
    count = 0.0
    if text.count("<think>") == 1:
        count += 0.25
    if text.count("</think>") == 1:
        count += 0.25
    if text.count("<answer>") == 1:
        count += 0.25
    if text.count("</answer>") == 1:
        count += 0.25
    return count


def extract_answer(text: str) -> str | None:
    extracted_answer = re.search(r"<answer>(.*?)</answer>", text, re.DOTALL)
    if extracted_answer:
        return extracted_answer.group(1).strip()
    return None


def accuracy_reward(completions, answer, **kwargs):
    contents = [completion[0]["content"] for completion in completions]
    return [2.0 if extract_answer(c) == a else 0.0 for c, a in zip(contents, answer)]


def format_reward(completions, **kwargs):
    pattern = r"^<think>.*?</think>.*?<answer>.*?</answer>$"
    completion_contents = [completion[0]["content"] for completion in completions]
    matches = [
        re.match(pattern, content, re.DOTALL | re.MULTILINE)
        for content in completion_contents
    ]
    return [1.0 if match else 0.0 for match in matches]


def tag_count_reward(completions, **kwargs) -> list[float]:
    contents = [completion[0]["content"] for completion in completions]
    return [count_tags(c) for c in contents]
