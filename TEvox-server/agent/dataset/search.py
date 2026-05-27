import uuid
from pydantic import BaseModel, Field
from typing import List
from datasets import IterableDataset


class Sample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: List[dict]
    workspace: str
    branch: str
    commit: str


class DynamicDataset(IterableDataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        for item in self.data:
            yield item.model_dump()

    def append(self, item):
        self.data.append(item)

    def remove(self, id):
        for i, item in enumerate(self.data):
            if item.id == id:
                self.data.pop(i)
                break


from agent.dataset.prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT, tools

sample = Sample(
    prompt=[
        {
            "role": "system",
            "content": AGENT_SYSTEM_PROMPT.format(
                task="The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements. Note: The development environment has been set up successfully using PlatformIO, along with ESP-IDF framework.",
                tools=tools,
            ),
        },
        {
            "role": "user",
            "content": AGENT_USER_PROMPT,
        },
    ],
    workspace="",
    branch="",
    commit="",
)

search_dataset = DynamicDataset([sample])


if __name__ == "__main__":
    from agent.dataset.prompt import AGENT_SYSTEM_PROMPT, AGENT_USER_PROMPT, tools

    sample = Sample(
        prompt=[
            {
                "role": "system",
                "content": AGENT_SYSTEM_PROMPT.format(
                    task="The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements. Note: The development environment has been set up successfully using PlatformIO, along with ESP-IDF framework.",
                    tools=tools,
                ),
            },
            {
                "role": "user",
                "content": AGENT_USER_PROMPT,
            },
        ],
        workspace="",
        branch="",
        commit="",
    )

    dataset = DynamicDataset([sample])
    print(next(iter(dataset)))

    dataset.append(sample)
    print(next(iter(dataset)))
