import html
import json
import re

from src.utils import get_llm, OneRoundAgent
from src.base import DefaultConfig


system_prompt = """\
You are a embedded system developer skilled in domain specific customization. You are knowledgeable about general domain knowledge about RTOS, MCU, etc.

-Goal-
Given a technical document with a set of entities, identify the dependencies between the entities and return the output.

-Schema-
There are two types of entities: code entities and semantic entities. Code entities are code elements such as functions, structs, macros, enums, or header files in the C language, and pins, registers in the hardware datasheet. Semantic entities are semantic concepts such as tasks or system modules.

The dependency types include:
- USE: <code> -USE-> <code>: A code entity uses another code entity. For example, a function uses a data type, a function call another function, a struct contains a member of another struct, etc. 
- CONTAIN: <semantic> -CONTAIN-> <sementic>: A system module contains some submodules, a task decomposed into subtasks, etc.
- IMPLEMENT: <semantic> -IMPLEMENT-> <code>: A task is implemented by a function, a system module is implemented by a set of functions, etc.

-Steps-
1. Identify all dependencies between the entities following the schema.
- source: The source entity name of the dependency.
- relationship: The relationship between the source and target entities, one of ["USE", "CONTAIN", "IMPLEMENT"].
- target: The target entity name of the dependency.
Format each dependency as (<source><|><relationship><|><target>)

2. Return output in English as a single list of all the entities and relationships identified in steps 1, 2. Use ## as the list delimiter. If you have to translate, just translate the descriptions, nothing else!

3. When finished, output <|COMPLETE|>

####################
-Example 1-
####################
-Input Document-
esp_err_t esp_spp_init(esp_spp_mode_t mode)
This function is called to init SPP module. When the operation is completed, the callback function will be called with ESP_SPP_INIT_EVT. This function should be called after esp_bluedroid_enable() completes successfully.

Parameters
mode -- [in] Choose the mode of SPP, ESP_SPP_MODE_CB or ESP_SPP_MODE_VFS.

Returns
ESP_OK: success
other: failed

-Entity Set-
(code<|>esp_spp_init<|>FUNCTION<|>This is a function called to initialize the SPP module.)##
(code<|>esp_spp_mode_t<|>DATA_TYPE<|>This is a type that defines the mode for the SPP operation, either ESP_SPP_MODE_CB or ESP_SPP_MODE_VFS.)##
(code<|>ESP_SPP_INIT_EVT<|>DATA_TYPE<|>This is an event that the callback function will receive once the SPP initialization operation is completed.)##
(code<|>esp_bluedroid_enable<|>FUNCTION<|>This is a function used to enable bluedroid.)##
(code<|>esp_err_t<|>DATA_TYPE<|>This data type indicates the error code.)##
(semantic<|>Initializing SPP module<|>TASK<|>This represents the process of initializing the SPP module.)##

####################
output:
(esp_spp_init<|>USE<|>esp_spp_mode_t)##
(esp_spp_init<|>USE<|>esp_err_t)##
(Initializing SPP module<|>IMPLEMENT<|>esp_spp_init)##
<|COMPLETE|>

####################
-Real Data-
####################
-Input Document-
{document}
-Entity Set-
{entity_set}
####################
output:
"""


def dependency_extraction_agent(api_base=None, api_key=None, model_name=None):
    """Extract dependencies between entities in a technical document.
    input:
        document: str
        entity_set: str ({kind}<|>{name}<|>{type}<|>{description})##...
    output:
        json_str: [{"source": str, "relationship": str, "target": str}, ...]
        
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
            temperature=0.3,
        ),
        prompt=system_prompt,
        postprocess_func=parse_dependency_extraction_result,
    )


def parse_dependency_extraction_result(result: str):
    record_delimiter = "##"
    tuple_delimiter = "<|>"
    records = [r.strip() for r in result.split(record_delimiter)]

    relation_list = []

    for record in records:
        record = re.sub(r"^\(|\)$", "", record.strip())
        record_attributes = record.split(tuple_delimiter)

        if len(record_attributes) >= 3:
            source = clean_str(record_attributes[0])
            relation = clean_str(record_attributes[1].upper())
            target = clean_str(record_attributes[2])

            relation_list.append(
                {
                    "source": source,
                    "relationship": relation,
                    "target": target,
                }
            )
    json_str = json.dumps(relation_list, ensure_ascii=False)
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
    agent = dependency_extraction_agent()
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

    entity_set = """\
("semantic"<|>Installing ADC Continuous Mode Driver<|>TASK<|>This task describes the typical steps to install the ADC continuous mode driver.)##                                                 
("semantic"<|>Reading ADC Conversion Results<|>TASK<|>This task explains how to read ADC conversion results from a group of ADC channels continuously.)##                                        
("semantic"<|>Resource Allocation<|>SYSTEM_MODULE<|>This module covers the parameters that should be set up to initialize and deinitialize the ADC continuous mode driver.)##                       
("semantic"<|>ADC Configurations<|>SYSTEM_MODULE<|>This module describes how to configure the ADC(s) to operate in continuous mode.)##                                                              
("semantic"<|>ADC Control<|>SYSTEM_MODULE<|>This module describes the functions used to control the ADC.)##                                                                                         
("semantic"<|>Register Event Callbacks<|>SYSTEM_MODULE<|>This module explains how to hook user-specific code to an ADC continuous mode event callback function.)##                                  
("semantic"<|>Getting ADC Conversion Result<|>TASK<|>This task covers how to obtain the ADC conversion result.)##                                                                                   
("semantic"<|>Hardware Limitations<|>SYSTEM_MODULE<|>This module describes the hardware limitations related to the ADC.)##                                                                          
("semantic"<|>Power Management<|>SYSTEM_MODULE<|>This module provides information related to power management for the ADC.)##                                                                       
("semantic"<|>IRAM Safe Functions<|>SYSTEM_MODULE<|>This module covers the functions that are safe to use in IRAM.)##                                                                               
("semantic"<|>Thread Safety<|>SYSTEM_MODULE<|>This module lists which APIs are guaranteed to be thread-safe by the driver.)##"""

    from langchain_community.callbacks import get_openai_callback

    with get_openai_callback() as cb:
        result = agent.invoke({"document": text, "entity_set": entity_set})
        # print(result)
        # get all attributes of the cb object except unserializable ones
        cb_dict = {k: v for k, v in cb.__dict__.items() if not k.startswith("_")}
        print(json.dumps(cb_dict, indent=2))

"""
(Installing ADC Continuous Mode Driver<|>CONTAIN<|>Resource Allocation)##                                                                                                                                 
(Installing ADC Continuous Mode Driver<|>CONTAIN<|>ADC Configurations)##                                                                                                                                  
(Installing ADC Continuous Mode Driver<|>CONTAIN<|>ADC Control)##                                                                                                                                         
(Installing ADC Continuous Mode Driver<|>CONTAIN<|>Register Event Callbacks)##                                                                                                                            
(Reading ADC Conversion Results<|>CONTAIN<|>Getting ADC Conversion Result)##                                                                                                                              
(Installing ADC Continuous Mode Driver<|>CONTAIN<|>Hardware Limitations)##                                                                                                                                
(Installing ADC Continuous Mode Driver<|>CONTAIN<|>Power Management)##                                                                                                                                    
(Installing ADC Continuous Mode Driver<|>CONTAIN<|>IRAM Safe Functions)##                                                                                                                                 
(Installing ADC Continuous Mode Driver<|>CONTAIN<|>Thread Safety)##                                                                                                                                       
<|COMPLETE|>
"""
