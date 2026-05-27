from datasets import load_dataset, Dataset
from agent.dataset.prompt import DEFAULT_SYSTEM_PROMPT


def extract_answer(text: str) -> str | None:
    if "####" not in text:
        return None
    return text.split("####")[1].strip()


def get_gsm8k_prompts(system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> Dataset:
    ds = load_dataset("openai/gsm8k", "main")

    prompt = []
    if system_prompt:
        prompt.append(
            {
                "role": "system",
                "content": system_prompt,
            }
        )

    ds = ds.filter(lambda x: extract_answer(x["answer"]) is not None).map(
        lambda x: {
            "prompt": prompt
            + [
                {
                    "role": "user",
                    "content": x["question"],
                },
            ],
            "answer": extract_answer(x["answer"]),
        }
    )

    return ds
