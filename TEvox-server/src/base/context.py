import json
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class MetaData(BaseModel):
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="The unique identifier of the context.",
    )
    source: Optional[str] = Field(description="The reference source of the context.")


class Context(BaseModel):
    metadata: Optional[MetaData] = Field(description="The metadata of the context.")
    content: str = Field(description="The content of the context.")

    def __str__(self):
        return f"Metadata: {self.metadata.model_dump(exclude={'id'})}\nContent: {self.content}"


class ContextManager:

    def __init__(self):
        self._ids = set()
        self._msgs = []

    def append_context(self, context: Context):
        if context.metadata.id:
            if context.metadata.id in self._ids:
                print(f"Context with id {context.metadata.id} already exists.")
                return
            self._ids.add(context.metadata.id)
        self._msgs.append(context)

    def remove_context(self, indices: List[int]):
        items = []
        for idx, item in enumerate(self._msgs):
            if idx in indices:
                if item.metadata.id:
                    self._ids.remove(item.metadata.id)
                continue
            items.append(item)
        self._msgs = items

    def __str__(self):
        return "\n\n".join(
            [f"<id={idx}>\n{item}\n</id={idx}>" for idx, item in enumerate(self._msgs)]
        )

    def __len__(self):
        return len(self._msgs)

    def save(self, path="./context.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [msg.model_dump() for msg in self._msgs],
                f,
                ensure_ascii=False,
                indent=4,
            )

    @classmethod
    def load(cls, path="./context.json"):
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        cm = cls()
        for msg_data in raw_data:
            context = Context.model_validate(msg_data)
            cm._msgs.append(context)
            if context.metadata and context.metadata.id:
                cm._ids.add(context.metadata.id)
        return cm


if __name__ == "__main__":
    context_manager = ContextManager()
    context_manager.append_context(
        Context(
            metadata=MetaData(id="1", source="test"), content="This is a test context."
        )
    )
    context_manager.append_context(
        Context(
            metadata=MetaData(id="2", source="test"),
            content="This is another test context.",
        )
    )
    print(context_manager)

    context_manager.remove_context([0])
    print(context_manager)

    context_manager.save()

    loaded_context_manager = ContextManager.load()
    print("Loaded context manager:")
    print(loaded_context_manager)
