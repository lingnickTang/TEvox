import html
import json
import re

from src.utils import get_llm, OneRoundAgent
from src.base import DefaultConfig


system_prompt = """\
You are a embedded system developer skilled in domain specific customization. You are knowledgeable about general domain knowledge about RTOS, MCU, etc.

-Goal-
Given a technical document, first identify all entities followed by the defined types. For each entity, extract the entity name, type, document relationship and description.

-Steps-
1. Identify all code entities. A code entity means a precise name or symbol of a C code element, such as a function name, a struct name, a macro name, or an enum name in the software, and a pin name, register name in the hardware:
- entity_name: The literal name mentioned in the document. Must be exactly the same as the name in the document.
- entity_type: Suggest the categories for the entity, one of ["FUNCTION", "STRUCT", "MACRO", "ENUM", "FILE_NAME", "PIN", "REGISTER_NAME", "DATA_TYPE", "UNKNOWN_NAME"].
- document_relation: The relationship between the entity and the document, one of ["DEFINE", "USE"].
- entity_description: The summarized content of the piece of knowledge, each piece of knowledge should be complete sentences.
Format each entity as ("code"<|><entity_name><|><entity_type><|><document_relation><|><entity_description>)

2. Identify all semantic concept entities. A semantic concept entity means a concept or a task that is not literally a keyword in the document, but a domain specific concept such as an operation, a task or a module:
- entity_name: A noun phrase or a verb phrase that represents a concept or a task. (MUST be differentiated)
- entity_type: Suggest the categories for the entity, one of ["TASK", "SYSTEM_MODULE", "OTHER"].
- document_relation: The relationship between the entity and the document, one of ["DEFINE", "USE"].
- entity_description: The summarized content of the piece of knowledge, each piece of knowledge should be complete sentences.
Format each entity as ("semantic"<|><entity_name><|><entity_type><|><document_relation><|><entity_description>)

3. Return output in English as a single list of all the entities and relationships identified in steps 1. Use ## as the list delimiter. If you have to translate, just translate the descriptions, nothing else!

4. When finished, output <|COMPLETE|>

####################
-Example 1-
####################
input document:
esp_err_t esp_spp_init(esp_spp_mode_t mode)
This function is called to init SPP module. When the operation is completed, the callback function will be called with ESP_SPP_INIT_EVT. This function should be called after esp_bluedroid_enable() completes successfully.

Parameters
mode -- [in] Choose the mode of SPP, ESP_SPP_MODE_CB or ESP_SPP_MODE_VFS.

Returns
ESP_OK: success
other: failed
####################
output:
("code"<|>esp_spp_init<|>FUNCTION<|>DEFINE<|>This is a function called to initialize the SPP module.)##
("code"<|>esp_spp_mode_t<|>DATA_TYPE<|>USE<|>This is a type that defines the mode for the SPP operation, either ESP_SPP_MODE_CB or ESP_SPP_MODE_VFS.)##
("code"<|>ESP_SPP_INIT_EVT<|>DATA_TYPE<|>USE<|>This is an event that the callback function will receive once the SPP initialization operation is completed.)##
("code"<|>esp_bluedroid_enable<|>FUNCTION<|>USE<|>This is a function used to enable bluedroid.)##
("code"<|>esp_err_t<|>DATA_TYPE<|>USE<|>This data type indicates the error code.)##
("semantic"<|>Initializing SPP module<|>TASK<|>USE<|>This represents the process of initializing the SPP module.)##
<|COMPLETE|>

####################
-Example 2-
####################
input document:
Reset Reason
ESP-IDF applications can be started or restarted due to a variety of reasons. To get the last reset reason, call esp_reset_reason() function. See description of esp_reset_reason_t for the list of possible reset reasons.
####################
output:
("code"<|>esp_reset_reason<|>FUNCTION<|>USE<|>This function is called to retrieve the last reset reason of the ESP-IDF application.)##
("code"<|>esp_reset_reason_t<|>DATA_TYPE<|>USE<|>This is a type that describes the possible reasons for resetting the ESP-IDF application.)##
("semantic"<|>Getting Reset Reason<|>TASK<|>DEFINE<|>This is a task that describes how to get the last reset reason of the ESP-IDF application.)##
<|COMPLETE|>

####################
-Real Data-
####################
input document: {input}
####################
output:
"""


def entity_extraction_agent(api_base=None, api_key=None, model_name=None):
    """Create an agent for entity extraction.
    
    Args:
        api_base: Optional API base URL. If None, uses DefaultConfig.rag_api_base
        api_key: Optional API key. If None, uses DefaultConfig.rag_api_key
        model_name: Optional model name. If None, uses DefaultConfig.rag_model
    """
    print(api_base, api_key, model_name)
    # exit(0)
    return OneRoundAgent(
        llm=get_llm(
            base_url=api_base or DefaultConfig.rag_api_base,
            api_key=api_key or DefaultConfig.rag_api_key,
            model_name=model_name or DefaultConfig.rag_model,
            temperature=0.3,
        ),
        prompt=system_prompt,
        postprocess_func=parse_entity_extraction_result,
    )


def parse_entity_extraction_result(result: str):
    record_delimiter = "##"
    tuple_delimiter = "<|>"
    records = [r.strip() for r in result.split(record_delimiter)]

    entity_list = []

    for record in records:
        record = re.sub(r"^\(|\)$", "", record.strip())
        record_attributes = record.split(tuple_delimiter)

        if (
            record_attributes[0].find("code") != -1
            or record_attributes[0].find("semantic") != -1
        ) and len(record_attributes) >= 5:
            # add this record as a node in the G
            kind = clean_str(record_attributes[0].upper())  # code or semantic
            name = clean_str(record_attributes[1])  # entity name
            type = clean_str(
                record_attributes[2].upper()
            )  # entity type, e.g. FUNCTION, DATA_TYPE, TASK
            document_relation = clean_str(record_attributes[3].upper())  # DEFINE or USE
            description = clean_str(record_attributes[4])
            entity_list.append(
                {
                    "kind": kind,
                    "name": name,
                    "type": type,
                    "document_relation": document_relation,
                    "description": description,
                }
            )
    json_str = json.dumps(entity_list, ensure_ascii=False)
    return json_str


def clean_str(input) -> str:
    """Clean an input string by removing HTML escapes, control characters, and other unwanted characters."""
    # If we get non-string input, just give it back
    if not isinstance(input, str):
        return input

    result = html.unescape(input.strip())
    # https://stackoverflow.com/questions/4324790/removing-control-characters-from-a-string-in-python
    result = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", result)

    # strip leading and trailing " and '
    result = result.strip("\"'")
    return result


if __name__ == "__main__":
    api_base = "https://xiaoai.plus/v1"
    api_key = "sk-lfQ208tKi0Ghq1bnJdrmmVwMjfPlxJaySgqFLxMKggfRy4SR"
    api_model = "gpt-4o-mini"
    agent = entity_extraction_agent(api_base, api_key, api_model)
    text = """\
path:
Analog to Digital Converter (ADC) Continuous Mode Driver {#analog-to-digital-converter-(adc)-continuous-mode-driver}/Functional Overview {#functional-overview}
---
content:
## Functional Overview {#functional-overview}  
The following sections of this document cover the typical steps to install the ADC continuous mode driver, and read ADC conversion results from a group of ADC channels continuously:  
* Resource Allocation: covers which parameters should be set up to initialize the ADC continuous mode driver and how to deinitialize it.
* ADC Configurations: describes how to configure the ADC(s) to make it work under continuous mode.
* ADC Control: describes ADC control functions.
* Register Event Callbacks: describes how to hook user-specific code to an ADC continuous mode event callback function.
* Read Conversion Result: covers how to get ADC conversion result.
* Hardware Limitations: describes the ADC-related hardware limitations.
* Power Management: covers power management-related information.
* IRAM Safe: covers the IRAM safe functions.
* Thread Safety: lists which APIs are guaranteed to be thread-safe by the driver.
"""
    from langchain_community.callbacks import get_openai_callback

    with get_openai_callback() as cb:
        result = agent.invoke(
            {
                "input": text,
            }
        )
        # print(result)
        # get all attributes of the cb object except unserializable ones
        cb_dict = {k: v for k, v in cb.__dict__.items() if not k.startswith("_")}
        print(json.dumps(cb_dict, indent=2))

"""
("code"<|>ledc_timer_config<|>FUNCTION<|>DEFINE<|>This function is called to configure the LEDC timer settings.)##
("code"<|>ledc_timer_config_t<|>DATA_TYPE<|>USE<|>This is a data structure that contains the configuration settings for the LEDC timer.)##
("code"<|>ledc_mode_t<|>DATA_TYPE<|>USE<|>This is a type that defines the speed mode for the LEDC timer.)##
("code"<|>ledc_timer_t<|>DATA_TYPE<|>USE<|>This is a type that represents the timer number for the LEDC configuration.)##
("code"<|>ledc_clk_cfg_t<|>DATA_TYPE<|>USE<|>This is a type that describes the source clock configuration for the LEDC.)##
("code"<|>ledc_find_suitable_duty_resolution<|>FUNCTION<|>USE<|>This function is a helper that finds the maximum possible resolution for the timer based on the source clock frequency and the desired PWM signal frequency.)##
("semantic"<|>Configuring LEDC Timer<|>TASK<|>DEFINE<|>This is a task that describes the process of setting up the LEDC timer using the configuration structure.)##
("semantic"<|>Deconfiguring LEDC Timer<|>TASK<|>DEFINE<|>This is a task that outlines how to deconfigure the LEDC timer when it is no longer needed.)##
<|COMPLETE|>
"""
