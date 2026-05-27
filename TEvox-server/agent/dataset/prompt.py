from langchain_core.prompts import PromptTemplate
from src.base import ToolCall, ToolSpec, ToolKit

DEFAULT_SYSTEM_PROMPT = "A conversation between User and Assistant. The user asks a question, and the Assistant solves it. The assistant first thinks about the reasoning process in the mind and then provides the user with the answer. The reasoning process and answer are enclosed within <think> </think> and <answer> </answer> tags, respectively, i.e., <think> reasoning process here </think> <answer> answer here </answer>."

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


def search_information(query: str):
    pass


def view_workspace(instruction: str):
    pass


def write_file(file_path: str, task_desc: str):
    pass


def PioBuildDevice():
    pass


def PioUploadMonitorDevice():
    pass


def executeCommandInTerminal(command_line: str):
    pass


tools = ToolKit(
    [
        ToolSpec(
            tool_desc="Search information from the relevant documents and dependent libraries",
            tool_call=ToolCall(
                tool_name="semantic_search",
                tool_args={
                    "query": "The objective of the search information and which information is to be acquired",
                },
            ),
            tool_func=search_information,
            # default_args={
            #     "context": context,
            # },
        ),
        ToolSpec(
            tool_desc="Viewing directory structure and opening relevant files in the workspace",
            tool_call=ToolCall(
                tool_name="view_workspace",
                tool_args={
                    "instruction": "The objective of the workspace view and which content is to be viewed",
                },
            ),
            tool_func=view_workspace,
            # tool_func=FileViewAction(vscode_client=vscode_client).view_file,
            # tool_func=lambda x: x,
        ),
        ToolSpec(
            tool_desc="Write content to a new file or edit an existing file in the VSCode editor",
            tool_call=ToolCall(
                tool_name="write_file",
                tool_args={
                    "file_path": "The path of the file to be edited",
                    "task_desc": "The simple and specific instruction for which content is to be written",
                },
            ),
            tool_func=write_file,
            # tool_func=FileEditAction(
            #     vscode_client=vscode_client, agent=agent
            # ).edit_file,
            # tool_func=lambda x: x,
        ),
        ToolSpec(
            tool_desc="Build device",
            tool_call=ToolCall(
                tool_name="PioBuildDevice",
                tool_args={},
            ),
            # tool_func=vscode_client.PioBuildDevice,
            tool_func=PioBuildDevice,
        ),
        ToolSpec(
            tool_desc="Upload and monitor device",
            tool_call=ToolCall(
                tool_name="PioUploadMonitorDevice",
                tool_args={},
            ),
            # tool_func=vscode_client.PioUploadMonitorDevice,
            tool_func=PioUploadMonitorDevice,
        ),
        ToolSpec(
            tool_desc="Execute a shell command in the VSCode terminal",
            tool_call=ToolCall(
                tool_name="executeCommandInTerminal",
                tool_args={
                    "command_line": "Command line to execute, e.g. 'ls' to list files."
                },
            ),
            tool_func=executeCommandInTerminal,
            # tool_func=vscode_client.executeCommandInTerminal,
        ),
    ]
)


# print(
#     AGENT_SYSTEM_PROMPT.format(
#         task="The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements. The deliverables include comprehensive documentation (design documents, API references) and code (implementation code, test code).",
#         tools=tools,
#     )
# )

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
