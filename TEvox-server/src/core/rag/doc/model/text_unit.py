from typing import Optional, List
import uuid
from pydantic import BaseModel, Field


class TextUnit(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: dict = Field(default_factory=dict)
    path: Optional[str] = None
    source: Optional[str] = None
    document_id: str
    tokens: Optional[int] = None
    embedding: Optional[List[float]] = None
    score: Optional[float] = None  # for search result

    @property
    def llm_content(self):
        text = (
            f"Source: {self.path}\n"
            + self.metadata_str()
            + f"Content:\n {self.content}"
        )
        return text

    def metadata_str(self):
        if not self.metadata:
            return ""

        def key_map(key):
            if key.startswith("Header"):
                level = key.split(" ")[-1]
                return "#" * int(level) + ""
            return key + ": "

        values = self.metadata.values()
        values = [v for v in values if v]

        res = "Metadata:\n"
        res += "/".join(values) + "\n"
        res += "---\n"

        return res
