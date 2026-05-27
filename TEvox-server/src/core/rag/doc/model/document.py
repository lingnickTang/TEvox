import uuid
from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: dict = Field(default_factory=dict)
