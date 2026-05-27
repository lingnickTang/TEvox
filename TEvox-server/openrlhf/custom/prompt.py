from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


prompt = """<ROLE>
You are an autonomous agent with available tools to complete the task. To complete the task, first thinks about the reasoning process in the mind and then takes the next action to invoke a tool. The reasoning process and next action are enclosed within <think> </think> and <action> </action> tags, respectively, i.e., <think> reasoning process here </think> <action> next action here </action>.
</ROLE>
{% if task %}
<TASK>
{{ task }}
</TASK>
{% endif -%}
{% if tools %}
<TOOLS>
{{ tools }}
</TOOLS>
{% endif -%}
{% if context %}
<CONTEXT>
{{ context }}
</CONTEXT>
{% endif -%}"""

AGENT_SYSTEM_PROMPT = PromptTemplate.from_template(
    template=prompt, template_format="jinja2"
)

AGENT_USER_PROMPT = """To efficiently complete the task, decide the highest-priority action could be taken next. Finally, output in the following format:
<think> reasoning process here </think>
<action>```json
{{
    "tool_name": The tool to be executed, chosen from the `<| TOOLS |>` list,
    "tool_args": The parameters required for the tool.
}}
```</action>"""

format_feedback = """The format of the output is incorrect. You should output in the following format:
<think> reasoning process here </think>
<action>```json
{
    "tool_name": "...",
    "tool_args": {...}
}```</action>"""


feedback_prompt = """Feedback: `{feedback}`. To efficiently complete the task, refine the reasoning process and the action taken based on the feedback. Finally, output in the following format:
<think> reasoning process here </think>
<action>```json
{{
    "tool_name": The tool to be executed, chosen from the `<| TOOLS |>` list,
    "tool_args": The parameters required for the tool.
}}
```</action>"""


def convert_to_langchain_messages(messages: list) -> list:
    langchain_messages = []
    for msg in messages:
        role = msg.get("role", "").lower()
        content = msg.get("content", "")

        if role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        else:
            raise ValueError(f"Unsupported message role: {role}")

    return langchain_messages

