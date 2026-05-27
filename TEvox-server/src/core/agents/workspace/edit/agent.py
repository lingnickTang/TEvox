from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from src.utils.agent import Agent
from src.core.agents.workspace.edit.prompt import (
    continue_or_terminate_prompt,
    edit_file_prompt,
    get_edit_type_prompt,
    insert_prompt,
    replace_prompt,
    merge_file_prompt,
)
from src.core.tools import VSCodeClient
from src.base.action import Evaluation
from src.base import DefaultConfig
from src.utils import get_llm


class EditType(BaseModel):
    model_config = ConfigDict(extra="ignore")
    edit_type: Literal["insert", "replace"]
    start_line: int = Field(description="The start line of the edit range.")
    end_line: int = Field(description="The end line of the edit range.")


class FileEditAction:

    def __init__(self, vscode_client: VSCodeClient, agent: Agent):
        self.vscode_client = vscode_client
        self.agent = agent

    def get_range(self, file_path: str, task_desc: str) -> tuple:
        diff = self.vscode_client.write_file(
            file_path=file_path,
            content="",
            start_line=1,
            end_line=-1,
            edit_type="insert",
        )
        file_path = diff.get("filePath")
        old_text = diff.get("oldText")

        res = self.agent.invoke_with_structured_output(
            edit_file_prompt.format(file_path=file_path, file_content=old_text)
            + get_edit_type_prompt.format(task=task_desc),
            schema=EditType,
        )
        self.agent.remove_last_k_messages(2)

        return (
            file_path,
            old_text,
            res.edit_type,
            res.start_line,
            res.end_line,
        )

    def write_file(
        self,
        file_path: str,
        task_desc: str,
        old_text: str,
        edit_type: str,
        start_line: int,
        end_line: int,
    ):
        prompt = edit_file_prompt.format(file_path=file_path, file_content=old_text)

        if edit_type == "insert":
            prompt += insert_prompt.format(task=task_desc, line=start_line)
        else:
            prompt += replace_prompt.format(
                task=task_desc, start_line=start_line, end_line=end_line
            )

        res = self.agent.invoke_with_structured_output(input=prompt, load_json=False)
        self.agent.remove_last_k_messages(2)

        return self.vscode_client.write_file(
            file_path, res, start_line, end_line, edit_type
        )

    def merge_file(
        self,
        file_path: str,
        task_desc: str,
        original_text: str,
        current_text: str,
    ):
        res = self.agent.invoke_with_structured_output(
            merge_file_prompt.format(
                task=task_desc,
                file_path=file_path,
                original_content=original_text,
                current_content=current_text,
            ),
            load_json=False,
        )
        self.agent.remove_last_k_messages(2)

        return self.vscode_client.write_file(
            file_path=file_path,
            content=res,
            start_line=1,
            end_line=-1,
            edit_type="replace",
        )

    def continue_or_terminate(
        self, file_path: str, task_desc: str, old_text: str, new_text: str
    ):
        res = self.agent.invoke_with_structured_output(
            continue_or_terminate_prompt.format(
                file_path=file_path,
                original_content=old_text,
                current_content=new_text,
                task=task_desc,
            ),
            schema=Evaluation,
        )
        self.agent.remove_last_k_messages(2)

        return res.value()

    def edit_file(self, file_path: str, task_desc: str):
        _llm = self.agent._llm
        llm = get_llm(
            base_url=DefaultConfig.code_api_base,
            api_key=DefaultConfig.code_api_key,
            model_name=DefaultConfig.code_model,
        )
        self.agent.set_llm(llm)
        idx = 1
        original_text = ""

        while True:
            file_path, old_text, edit_type, start_line, end_line = self.get_range(
                file_path=file_path,
                task_desc=task_desc,
            )

            if idx == 1:
                original_text = old_text

            res = self.write_file(
                file_path, task_desc, old_text, edit_type, start_line, end_line
            )

            newText = self.merge_file(
                file_path,
                task_desc,
                original_text,
                res.get("newText"),
            ).get("newText")

            # self.agent.remove_last_k_messages(idx * 2)
            # self.agent.set_llm(_llm)
            # return (
            #     f"""File written successfully at path {file_path}. Original file content: {original_text}. Current file content: {newText}""",
            # )

            if not self.continue_or_terminate(
                file_path, task_desc, original_text, newText
            ):
                # self.agent.remove_last_k_messages(idx * 2)
                self.agent.set_llm(_llm)
                return (
                    f"""File written successfully at path {file_path}. Original file content: {original_text}. Current file content: {newText}""",
                )

            # idx += 1


if __name__ == "__main__":
    from src.utils import get_llm, Agent

    agent = Agent(llm=get_llm())
    print(
        FileEditAction(
            agent=agent,
            vscode_client=VSCodeClient(),
        ).edit_file(
            file_path="src/main.c",
            task_desc="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to implement an echo function using i2s, ring buffer, freertos, which means capturing audio through a microphone and playing it back through a speaker. The deliverables include comprehensive documentation (design documents, API references) and code (implementation code, test code).""",
        )
    )
