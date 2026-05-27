import json
from pydantic import BaseModel
from typing import List
from datasets import IterableDataset, Dataset


class Sample(BaseModel):
    id: str
    prompt: List[dict]
    workspace: str
    branch: str
    commit: str


def read_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            yield data


if __name__ == "__main__":
    # ds = Dataset.from_json("src/dataset/custom.json")
    # print(ds[0])

    from agent.dataset.prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT, tools

    data = [
        {
            "id": "",
            "prompt": [
                {
                    "role": "system",
                    "content": AGENT_SYSTEM_PROMPT.format(
                        task="The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements. The deliverables include comprehensive documentation (design documents, API references) and code (implementation code, test code). Note: The development environment has been set up successfully using PlatformIO, along with ESP-IDF framework.",
                        tools=tools,
                    ),
                },
                {
                    "role": "user",
                    "content": AGENT_USER_PROMPT,
                },
            ],
            "workspace": "",
            "branch": "",
            "commit": "",
        }
    ] * 128

    with open("agent/dataset/custom.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
