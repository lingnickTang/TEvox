import os
from typing import List

import glob


from src.core.rag.doc.model import Document
from src.utils import logger


class DocumentLoader:
    def __init__(self, config: dict):
        self.config = config
        self.root_path = config.get("root_path")
        self.input_path = os.path.join(self.root_path, "input")

    def get_files(self, path: str, suffix: str) -> List[str]:
        return glob.glob(os.path.join(path, f"**/[!.]*{suffix}"), recursive=True)

    def get_documents(self) -> List[Document]:
        documents = []
        for file in self.get_files(self.input_path, "md"):
            with open(file, "r", encoding="utf-8") as f:
                source = os.path.relpath(file, self.input_path).split(os.sep)[0]
                documents.append(
                    Document(
                        content=f.read(), metadata={"source": source, "file": file}
                    )
                )
        return documents

    def run(self, inputs=None) -> List[Document]:
        documents = self.get_documents()
        logger.info(
            f"Successfully parsed {len(documents)} documents: \n {[doc.metadata for doc in documents]}"
        )
        return documents
