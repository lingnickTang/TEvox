import os

from src.core.agents.planner.agent import Planner
from src.base import (
    Task,
    TaskStatus,
    TaskStack,
    ToolSpec,
    ToolCall,
    ToolKit,
    ContinueOrTerminate,
    ContinueOrBacktrack,
    BreakdownOrExecution,
    Context,
    ContextManager,
    MetaData,
    Evaluation,
    Action,
    ActionRecord,
    Tracer,
    TASK_TYPE,
    TOOL_TYPE,
    FEEDBACK_TYPE,
    DefaultConfig,
    TaskNode,
    TaskTree,
)
from src.core.tools import (
    VSCodeClient,
    ask_help,
    search_information,
    get_feedback,
    ExperienceCollector,
    run_web_search,
)
from src.core.agents.planner.prompt import (
    system_prompt,
    continue_or_terminate_prompt,
    continue_or_backtrack_prompt,
    breakdown_or_execution_prompt,
    breakdown_prompt,
    execution_prompt,
    tool_output_prompt,
    context_summary_prompt,
    task_progress_prompt,
    solve_feedback_prompt,
    eval_prompt,
    remove_context_prompt,
    DEFAULT_EXPERIENCE,
)
from src.utils import logger, get_llm, Agent
from src.core.agents.workspace import FileEditAction


class AgentServe(Planner):

    def __init__(self, task_id, task_spec: str = None):
        self.task_stack_path = f"{task_id}_task_stack.json"
        self.context_path = f"{task_id}_context.json"

        if not os.path.exists(self.task_stack_path):
            task = Task(
                name="user requirement",
                spec=task_spec,
            )
            self.task_stack = TaskStack()
            self.task_stack.push_task(TaskNode.from_task(task))
        else:
            self.task_stack = TaskStack.load_from_file(self.task_stack_path)

        if not os.path.exists(self.context_path):
            self.context = ContextManager()
        else:
            self.context = ContextManager.load(self.context_path)

        vscode_client = VSCodeClient(base_url=DefaultConfig.vscode_api_base)
        agent = Agent(
            llm=get_llm(
                base_url=DefaultConfig.agent_api_base,
                api_key=DefaultConfig.agent_api_key,
                model_name=DefaultConfig.agent_model,
            ),
            msgs=[],
        )
        tools = ToolKit(
            [
                ToolSpec(
                    tool_desc="Search information from the internal knowledge base first if it is necessary to acquire additional information",
                    tool_call=ToolCall(
                        tool_name="search_information_from_knowledge_base",
                        tool_args={
                            "query": "The objective of the search information and which information is to be acquired.",
                        },
                    ),
                    tool_func=search_information,
                ),
                # ToolSpec(
                #     tool_desc="Search information from the external web internet again if the information is not found in the internal knowledge base",
                #     tool_call=ToolCall(
                #         tool_name="search_information_from_web_internet",
                #         tool_args={
                #             "task": "The objective of the search information and which information is to be acquired.",
                #         },
                #     ),
                #     tool_func=run_web_search,
                # ),
                ToolSpec(
                    tool_desc="View directory structure in the workspace",
                    tool_call=ToolCall(
                        tool_name="view_directory",
                        tool_args={
                            "path": "The path of the directory to view the structure, e.g., ./ represents the root directory of the workspace."
                        },
                    ),
                    tool_func=vscode_client.get_directory_files,
                ),
                ToolSpec(
                    tool_desc="View file content in the workspace",
                    tool_call=ToolCall(
                        tool_name="view_file",
                        tool_args={
                            "file_path": "The path of the file to view the content"
                        },
                    ),
                    tool_func=vscode_client.open_file,
                ),
                ToolSpec(
                    tool_desc="Close a file that is no longer needed for viewing",
                    tool_call=ToolCall(
                        tool_name="close_file",
                        tool_args={"file_path": "The path of the file to close"},
                    ),
                    tool_func=vscode_client.close_file,
                ),
                ToolSpec(
                    tool_desc="Rename a file or directory in the workspace",
                    tool_call=ToolCall(
                        tool_name="rename_path",
                        tool_args={
                            "old_path": "The current path of the file or directory",
                            "new_path": "The new target path for the file or directory",
                        },
                    ),
                    tool_func=vscode_client.rename_path,
                ),
                ToolSpec(
                    tool_desc="Delete a file or directory in the workspace",
                    tool_call=ToolCall(
                        tool_name="delete_path",
                        tool_args={
                            "path": "The path of the file or directory to be deleted"
                        },
                    ),
                    tool_func=vscode_client.delete_path,
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
                    tool_func=FileEditAction(
                        vscode_client=vscode_client, agent=agent
                    ).edit_file,
                ),
                ToolSpec(
                    tool_desc="Build, Upload and Monitor device with qemu if no connected device",
                    tool_call=ToolCall(
                        tool_name="BuildUploadMonitorDevice",
                        tool_args={},
                    ),
                    default_args={
                        "command_line": "idf.py qemu monitor",
                    },
                    tool_func=vscode_client.executeCommandInEspIdfTerminal,
                ),
                # ToolSpec(
                #     tool_desc="Build device using esp-idf vscode extention",
                #     tool_call=ToolCall(
                #         tool_name="EspIdfBuildDevice",
                #         tool_args={},
                #     ),
                #     default_args={
                #         "command_line": "idf.py build",
                #     },
                #     tool_func=vscode_client.executeCommandInEspIdfTerminal,
                # ),
                # ToolSpec(
                #     tool_desc="Upload and monitor device using esp-idf vscode extention",
                #     tool_call=ToolCall(
                #         tool_name="EspIdfUploadMonitorDevice",
                #         tool_args={},
                #     ),
                #     default_args={
                #         "command_line": "idf.py flash monitor",
                #     },
                #     tool_func=vscode_client.executeCommandInEspIdfTerminal,
                # ),
                # ToolSpec(
                #     tool_desc="Build device",
                #     tool_call=ToolCall(
                #         tool_name="PioBuildDevice",
                #         tool_args={},
                #     ),
                #     tool_func=vscode_client.PioBuildDevice,
                # ),
                # ToolSpec(
                #     tool_desc="Upload and monitor device",
                #     tool_call=ToolCall(
                #         tool_name="PioUploadMonitorDevice",
                #         tool_args={},
                #     ),
                #     tool_func=vscode_client.PioUploadMonitorDevice,
                # ),
                # ToolSpec(
                #     tool_desc="Run test cases",
                #     tool_call=ToolCall(
                #         tool_name="PioRunTestCases",
                #         tool_args={
                #             "filter": "Optional filter parameter for the test cases, use empty string if not restricted, e.g. the relative path of the subdirectory relative to the test directory.",
                #             "ignore": "Optional ignore parameter for the test cases, use empty string if not restricted, e.g. the relative path of the subdirectory relative to the test directory.",
                #         },
                #     ),
                #     tool_func=vscode_client.PioRunTestCasesWithArgs,
                # ),
                # ToolSpec(
                #     tool_desc="Run test cases",
                #     tool_call=ToolCall(
                #         tool_name="PioRunTestCases",
                #         tool_args={},
                #     ),
                #     tool_func=vscode_client.PioRunTestCases,
                # ),
                ToolSpec(
                    tool_desc="Execute a shell command in the EspIdf terminal",
                    tool_call=ToolCall(
                        tool_name="executeCommandInTerminal",
                        tool_args={
                            "command_line": "Command line to execute, e.g. 'ls' to list files."
                        },
                    ),
                    tool_func=vscode_client.executeCommandInEspIdfTerminal,
                ),
                # ToolSpec(
                #     tool_desc="Execute a shell command in the VSCode terminal",
                #     tool_call=ToolCall(
                #         tool_name="executeCommandInTerminal",
                #         tool_args={
                #             "command_line": "Command line to execute, e.g. 'ls' to list files."
                #         },
                #     ),
                #     tool_func=vscode_client.executeCommandInPioTerminal,
                # ),
                ToolSpec(
                    tool_desc="Find code references for the selected code symbol of a file in the workspace",
                    tool_call=ToolCall(
                        tool_name="find_code_references",
                        tool_args={
                            "file_path": "The file path of the code to find references",
                            "line_number": "The line number of the code to find references",
                            "selected_symbol": "The code symbol to find references",
                        },
                    ),
                    tool_func=vscode_client.find_references,
                ),
                ToolSpec(
                    tool_desc="Search for content in the files of the workspace using a keyword or a regular expression",
                    tool_call=ToolCall(
                        tool_name="search_workspace_content",
                        tool_args={
                            "query": "The keyword or regex pattern to search for in the files of the workspace.",
                            "filesToInclude": "Glob pattern for files to include, e.g. '**/*.py'.",
                            "filesToExclude": "Glob pattern for files to exclude, e.g. 'node_modules/**'.",
                            "isRegex": "Set to True if the query should be interpreted as a regular expression.",
                            "isCaseSensitive": "Set to True to perform a case-sensitive search.",
                            "matchWholeWord": "Set to True to match whole words only.",
                        },
                    ),
                    tool_func=vscode_client.find_in_files,
                ),
                # ToolSpec(
                #     tool_desc="Ask human for help if needed",
                #     tool_call=ToolCall(
                #         tool_name="ask_human",
                #         tool_args={"help": "The specific help needed from the human."},
                #     ),
                #     tool_func=ask_help,
                # ),
            ]
        )

        super().__init__(
            agent=agent,
            tools=tools,
            task_stack=self.task_stack,
            context=self.context,
            tracer=Tracer(trj_path=f"{task_id}_trajectory.txt"),
            experience=ExperienceCollector(),
        )

    def serve(self, feedback=None, recent_actions_limit=10):
        res = """"""
        if feedback:
            self.solve_feedback(feedback)

        while not self.task_stack.is_empty():
            self.set_system_prompt(include_tools=True)
            self.agent.print_history()

            res = self.continue_or_not(feedback=feedback)

            if not res:
                if len(self.task_stack) == 1:
                    # self.evaluate()
                    res = f"""I think the task `{self.task_stack.get_final_task()}` has been completed."""
                    break
                self.backtrack()
                if (
                    len(self.task_stack.get_progress()) >= recent_actions_limit
                    and not feedback
                    # and len(self.task_stack) == 2
                ):
                    self.report()
                continue

            task = self.breakdown()
            if task:
                current_task = self.task_stack.get_current_task()
                res = f"""To complete the current task `{current_task.name}`, the following subtasks are still necessary to be completed:\n"""
                res += "\n\n".join(
                    f"""- {subtask}""" for subtask in current_task.get_subtasks()
                )
                res += (
                    f"""\n\nDo you want me continue the first subtask `{task.name}`?"""
                )
                self.task_stack.push_task(task)
                # trj = self.tracer.get_trjectory()[-1]
                # res = f"""{trj.action_name}: ({trj.action_desc["name"]}) {trj.action_desc["spec"]}"""
                break

            self.execution()
            res = self.tracer.get_trjectory()[-1].action_desc["tool_summary"]
            break

        self.task_stack.save_to_file(self.task_stack_path)
        self.context.save(self.context_path)
        return res


if __name__ == "__main__":
    import datetime

    task_id = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    # task_id = """2025-04-25-11-25-31"""
    # task_spec = """The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements. Note: The development environment has been set up successfully using PlatformIO, along with ESP-IDF framework."""
    task_spec = """The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements with ESP-IDF."""
    while True:
        input(f"Press Enter to continue...")
        agent = AgentServe(task_id=task_id, task_spec=task_spec)

        feedback = get_feedback()
        res = agent.serve(feedback)
        print(res)
