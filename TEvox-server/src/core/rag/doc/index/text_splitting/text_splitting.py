from typing import List

from src.core.rag.doc.model import Document, TextUnit
from src.utils import logger, num_tokens

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


class TextUnitExtractor:
    def __init__(self, config: dict):
        self.config = config

    def langchain_markdown_splitting(self, doc: Document) -> List[str]:
        chunk_size = self.config.get("max_chunk_size", 600)
        min_chunk_size = self.config.get("min_chunk_size", 200)
        chunk_overlap = self.config.get("chunk_overlap", 100)
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on, strip_headers=False
        )
        md_header_splits = markdown_splitter.split_text(doc.content)
        # Char-level splits
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=num_tokens,
        )
        splits = text_splitter.split_documents(md_header_splits)

        # combine the splits by token length
        raw_splits = [
            TextUnit(
                content=t.page_content,
                document_id=doc.id,
                path=doc.metadata.get("file"),
                source=doc.metadata.get("source"),
                metadata=t.metadata,
                tokens=num_tokens(t.page_content),
            )
            for t in splits
        ]

        final_splits = []
        for i, split in enumerate(raw_splits):
            if i == 0:
                final_splits.append(split)
            else:
                prev_split = final_splits[-1]
                if prev_split.tokens + split.tokens < min_chunk_size:
                    prev_split.content += "\n\n" + split.content
                    prev_split.tokens += split.tokens
                else:
                    final_splits.append(split)

        return final_splits

    def run(self, inputs: List[Document] = None) -> List[TextUnit]:
        docs = [Document(**x) for x in inputs]
        text_units = []
        for doc in docs:
            text_units.extend(self.langchain_markdown_splitting(doc))
        logger.info(
            f"Successfully split {len(text_units)} text units from {len(docs)} documents"
        )
        return text_units
