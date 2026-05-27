from typing import List
from pydantic import BaseModel

from src.utils import get_llm, Agent
from src.core.agents.workspace.view.prompt import (
    open_files_prompt,
    prefix_prompt,
)
from src.core.tools import VSCodeClient
from src.utils.log import logger

base_url = "http://10.166.104.94:6789"


class ViewAction(BaseModel):
    files: List[str] = []
    directories: List[str] = []


class FileViewAction:

    def __init__(self, vscode_client: VSCodeClient):
        self.vscode_client = vscode_client

    def open_files(
        self, task: str, path: str, all_files=set(), all_dirs=set()
    ) -> tuple:
        try:
            opened_files = self.vscode_client.get_all_open_text_documents()
            files = self.vscode_client.get_directory_files(path)

            res = Agent(llm=get_llm()).invoke_with_structured_output(
                prefix_prompt.format(files=opened_files)
                + open_files_prompt.format(directory_path=path, files=files, task=task),
                schema=ViewAction,
            )

            for file in list(set(res.files)):
                if file not in all_files:
                    try:
                        self.vscode_client.open_file(file)
                        all_files.add(file)
                    except Exception as e:
                        logger.warning(f"Failed to open file `{file}`: {str(e)}")

            for directory in list(set(res.directories)):
                if directory not in all_dirs:
                    all_dirs.add(directory)
                    self.open_files(task, directory, all_files, all_dirs)

        except Exception as e:
            logger.warning(f"Failed to list files for path `{path}`: {str(e)}")

    def view_file(self, instruction: str):
        all_files = set()
        self.open_files(instruction, path="/", all_files=all_files)
        return f"The files have been opened in the VSCode editor: {list(all_files)}"


if __name__ == "__main__":
    print(
        FileViewAction(
            vscode_client=VSCodeClient(base_url="http://10.230.33.232:6789"),
        ).view_file(
            instruction="""编写一个hello world程序""",
        )
    )
