from typing import List
from pydantic import BaseModel, Field

from src.utils import get_llm, Agent
from src.base import DefaultConfig


system_prompt = """\
You are a embedded system developer skilled in domain specific customization. You are knowledgeable about general domain knowledge about RTOS, MCU, etc.

-Goal-
Given a list of technical documents (each is an API Rerference or Datasheet for a specific module) and a user query, first identify which documents may contain the answer to the query. Then, write a subquery for each candicate document to find the answer to the user query.

####################
- Example -
Document List:
["stm32_api_reference", "DHT11_datasheet", "OLED_datasheet"]

User Query:
How to read the temperature of DHT11 sensor through GPIO?

- Output -
```json
{{
    "candidate_documents": ["stm32_api_reference", "DHT11_datasheet"],
    "sub_queries": [
        {{
            "document": "stm32_api_reference",
            "sub_query": "How to read data from a GPIO pin?"
        }},
        {{
            "document": "DHT11_datasheet",
            "sub_query": "How to read the temperature data from the sensor?"
        }}
    ]
}}
```

####################
-Real Data-
####################
Document List:
{document_list}

User Query:
{user_query}
"""


class SubQuery(BaseModel):
    """The subquery for a candidate document."""

    document: str = Field(description="The title of the candidate document.")
    sub_query: str = Field(
        description="The subquery for the candidate document. (Do not include common words in this document like the document title.)"
    )


class DecomposedResult(BaseModel):
    """Decomposed queries for each candidate document."""

    candidate_documents: List[str] = Field(
        description="The list of candidate documents (titles)."
    )
    sub_queries: List[SubQuery] = Field(
        description="The subqueries for each candidate document."
    )


def query_seperation_agent(api_base=None, api_key=None, model_name=None, **kwargs):
    return Agent(
        llm=get_llm(
            base_url=api_base or DefaultConfig.search_api_base,
            api_key=api_key or DefaultConfig.search_api_key,
            model_name=model_name or DefaultConfig.search_model,
        ),
        msgs=[],
    ).invoke_with_structured_output(
        system_prompt.format(**kwargs), schema=DecomposedResult
    )


if __name__ == "__main__":
    document_list = ["esp32s3", "Motor_DRV10866", "rp2350", "stm32f103", "OLED_HS96L03"]

    user_query = "How to set the contrast ratio of the HS96L03 OLED on the esp32s3 platform via I2C?"

    from langchain_community.callbacks import get_openai_callback

    with get_openai_callback() as cb:
        result = query_seperation_agent(
            document_list=document_list, user_query=user_query
        )

        # result = agent.invoke(
        #     {
        #         "document_list": document_list,
        #         "user_query": user_query,
        #     }
        # )

        print(result)
        print(cb)

"""
{
    "candidate_documents": ["esp32s3", "Motor_DRV10866"],
    "sub_queries": [
        {
            "document": "esp32s3",
            "sub_query": "How to configure a PWM pin on the ESP32S3 to work with an external motor driver like DRV10866?",
        },
        {
            "document": "Motor_DRV10866",
            "sub_query": "What are the steps to initialize the PWM input pin on the DRV10866 motor driver?",
        }
    ]
}
"""
