from typing import List


from src.core.rag.doc.model import TextUnit
from src.core.rag.doc.query.nx_search import Retriever
from src.utils import get_llm, Agent
from src.base import DefaultConfig

select_text_units_prompt = """To efficiently complete the current task `{question}`, you have retrieved the following text units:
```
{context}
```

Please select the text units that are helpful to complete the task. For each selected text unit, provide the index number. Finally, output in a JSON list:
```json
[
    "The index numbers of the selected text units.",
]
```"""


# simple_qa_system_prompt = """\
# You are an expert in embedded system development. You task is to write a detailed tutorial to answer the question.

# -Steps-
# 1. Read the list of text units that are relavant to the question.
# 2. Write a detailed tutorial-style answer based on the text units.

# -Requirments-
# 1. The answer should be written in markdown format.
# 2. Each information you described can find the basis in Context, and you cannot fabricate. Mark the information with the index number of the text unit.
# e.g., "Person X is the owner of Company Y [15, 16] and subject to many allegations of wrongdoing [7]."

# -Question-
# {question}

# -Context-
# {context}

# ---------
# # Answer


def select_text_units(api_base=None, api_key=None, model_name=None, **kwargs):
    return Agent(
        llm=get_llm(
            base_url=api_base or DefaultConfig.search_api_base,
            api_key=api_key or DefaultConfig.search_api_key,
            model_name=model_name or DefaultConfig.search_model,
        ),
        msgs=[],
    ).invoke_with_structured_output(
        select_text_units_prompt.format(**kwargs),
        feedback="""```json
[
    "The index numbers of the selected text units.",
]
```""",
    )


class NxQueryEngine:
    def __init__(self, config: dict):
        self.config = config
        self.retriever = Retriever(config)

    def format_context(self, textunits: List[TextUnit]) -> str:
        return "\n\n".join(
            [
                f"<{i}>{textunit.llm_content}</{i}>"
                for i, textunit in enumerate(textunits)
            ]
        )

    def query(
        self,
        question: str,
        entry_limit=3,
        top_k=100,
    ):
        texts = []
        text_units = self.retriever.retrieve(question, entry_limit=entry_limit)
        if not text_units:
            return []
        if len(text_units) > top_k:
            text_units = text_units[:top_k]
        for i in select_text_units(
            api_base=self.config.get("SEARCH_API_BASE"),
            api_key=self.config.get("SEARCH_API_KEY"),
            model_name=self.config.get("SEARCH_MODEL"),
            question=question, 
            context=self.format_context(text_units)
        ):
            try:
                idx = int(i)
            except ValueError:
                continue
            if idx > len(text_units) or idx < 0:
                continue
            texts.append(text_units[int(i)])
        return texts


if __name__ == "__main__":
    config = {"root_path": ".rag"}
    query_engine = NxQueryEngine(config)
    query = "How to initialize the I2S master using ESP-IDF?"
    res = query_engine.query(query)
    print(res)
