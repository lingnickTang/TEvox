import json

from src.utils import get_llm, OneRoundAgent
from src.base import DefaultConfig

system_prompt = """\
You are a helpful assistant responsible for generating a comprehensive summary of the data provided below.
Given one entity, and a list of types and descriptions, all related to the same entity. 
-Steps-
1. Please concatenate all of these into a single, comprehensive description. Make sure to include information collected from all the descriptions.
If the provided descriptions are contradictory, please resolve the contradictions and provide a single, coherent summary.
Make sure it is written in third person, and include the entity names so we the have full context.
2. Inference the correct entity type. (Must be one of the input types)
3. Output the result in the format: <ENTITY_TYPE>: <DESCRIPTION>

#######
-Data-
Entity: {{entity_name}}
Type with Description List:
{%- for description in description_list %}
{{ description }}
{%- endfor %}
#######
Output:
"""


def parse_summary_result(res):
    split_res = res.split(": ")
    res = {}
    if len(split_res) < 2:
        res = {"type": "", "description": split_res[0].strip()}
    else:
        res = {
            "type": split_res[0].strip(),
            "description": ": ".join(split_res[1:]).strip(),
        }
    return json.dumps(res)


def entity_summary_agent(api_base=None, api_key=None, model_name=None):
    """
    entity_name
    description_list: ["<ENTITY_TYPE>: <DESCRIPTION>", ...]
    
    Args:
        api_base: Optional API base URL. If None, uses DefaultConfig.rag_api_base
        api_key: Optional API key. If None, uses DefaultConfig.rag_api_key
        model_name: Optional model name. If None, uses DefaultConfig.rag_model
    """
    return OneRoundAgent(
        llm=get_llm(
            base_url=api_base or DefaultConfig.rag_api_base,
            api_key=api_key or DefaultConfig.rag_api_key,
            model_name=model_name or DefaultConfig.rag_model,
            temperature=0.5,
        ),
        prompt=system_prompt,
        postprocess_func=parse_summary_result,
        template_format="jinja2",
    )


if __name__ == "__main__":
    agent = entity_summary_agent()

    res = agent.invoke(
        {
            "entity_name": "on_conv_done",
            "description_list": [
                "DATA_TYPE: This is a public member of the adc_continuous_evt_cbs_t structure that represents the callback invoked when one conversion frame is completed.",
                "FUNCTION: This function is an event callback that is triggered when the ADC driver completes a conversion.",
            ],
        }
    )
    print(res)
