import uuid
from pydantic import BaseModel, Field
from typing import Optional


class Entity(BaseModel):

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: Optional[str] = ""  # SEMANTIC, CODE
    type: Optional[str] = ""  # FUNCTION, TASK, ...
    name: str
    description: str
    embedding: Optional[list[float]] = []
    score: Optional[float] = 0.0  # for search result

    def __str__(self):
        return f"{self.name}({self.type}): {self.description}"
