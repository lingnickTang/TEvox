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
from src.utils import logger, get_llm, Agent
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
from src.core.agents.workspace import FileEditAction
from src.core.agents.executor import Executor


class Planner:

    def __init__(
        self,
        agent: Agent,
        tools: ToolKit,
        task_stack: TaskStack,
        context: ContextManager,
        tracer: Tracer,
        experience: ExperienceCollector,
    ):
        self.agent = agent
        self.tools = tools
        self.context = context
        self.task_stack = task_stack
        self.tracer = tracer
        self.experience = experience
        self._experience = []

    def set_system_prompt(
        self,
        view_dirs=True,
        view_files=True,
        include_tools=False,
        update_experience=False,
        verbose=False,
    ):
        context = str(self.context)

        if view_dirs:
            context += (
                """\n\nThe workspace contains the following files and directories:\n"""
                + VSCodeClient(
                    base_url=DefaultConfig.vscode_api_base
                ).get_directory_files("./", recursive="true")
            )

        if view_files:
            context += (
                """\n\nThe workspace contains the following open files:\n"""
                + VSCodeClient(
                    base_url=DefaultConfig.vscode_api_base
                ).get_all_open_text_documents()
            )

        if update_experience:
            self._experience = DEFAULT_EXPERIENCE + self.experience.search_experience(
                str(self.task_stack.get_current_task())
            )
        else:
            self._experience = DEFAULT_EXPERIENCE

        prompt = system_prompt.format(
            experience=self._experience,
            # task_tree=self.task_stack.tree(),
            task_stack=str(self.task_stack),
            tasks=self.task_stack.get_all_tasks(),
            tools=str(self.tools) if include_tools else None,
            progress=self.task_stack.get_progress(),
            context=context,
        )
        self.agent.set_system_prompt(prompt, verbose=verbose)

    def continue_or_terminate(self):
        current_task = self.task_stack.get_current_task()
        logger.info(f"Determine continue or terminate for `{current_task.name}`...\n")

        res = self.agent.invoke_with_structured_output(
            continue_or_terminate_prompt.format(task=current_task),
            schema=ContinueOrTerminate,
        )
        self.agent.remove_last_k_messages(2)

        return res.value()

    def continue_or_backtrack(self):
        current_task = self.task_stack.get_current_task()
        logger.info(f"Determine continue or backtrack for `{current_task.name}`...\n")

        res = self.agent.invoke_with_structured_output(
            continue_or_backtrack_prompt.format(task=current_task),
            schema=ContinueOrBacktrack,
        )
        self.agent.remove_last_k_messages(2)

        return res.value()

    def continue_or_not(self, feedback=None):
        current_task = self.task_stack.get_current_task()
        logger.info(f"Determine continue or not for `{current_task.name}`...\n")

        if current_task.get_status() == TaskStatus.NOT_STARTED:
            current_task.set_status(TaskStatus.STARTED)
            if not feedback:
                return True

        # if len(current_task.get_subtasks()) > 0:
        #     return True

        if len(self.task_stack) == 1:
            return self.continue_or_terminate()
        else:
            return self.continue_or_backtrack()

    def judge_complexity(self, current_task):
        logger.info(f"Judge complexity for `{current_task.name}`...\n")

        res = self.agent.invoke_with_structured_output(
            breakdown_or_execution_prompt.format(task=current_task),
            schema=BreakdownOrExecution,
        )
        self.agent.remove_last_k_messages(2)

        return res.value()

    def solve_complexity(self, current_task, schema=""):
        logger.info(f"Solve complexity for `{current_task.name}`...\n")

        res = self.agent.invoke_with_structured_output(
            breakdown_prompt.format(task=current_task, schema=schema),
            schema=Task,
        )
        self.agent.remove_last_k_messages(2)

        return [TaskNode.from_task(task) for task in res]

    def breakdown(self):
        current_task = self.task_stack.get_current_task()

        # if len(self.task_stack) >= 4:
        #     current_task.set_status(TaskStatus.EXECUTION)
        #     return None

        # if current_task.type == "search_info":
        #     current_task.set_status(TaskStatus.EXECUTION)
        #     return None

        # schema = ", i.e. search_info, design_code, develop_code, test_code, debug_code, others, etc."
        # schema = ", i.e. search_info, develop_code, test_code, debug_code, others, etc. Note: You should follow the incremental development methodology, which involves developing, testing, and debugging each function one by one. Only after one function has been developed, tested, and debugged should you start developing the next function. For example, develop function A, test function A, debug function A, after that, develop function B, test function B, debug function B. For the task of search_info, it only needs to be broken down into sub-tasks of search_info."

        # if (
        #     current_task.get_status() == TaskStatus.BREAKDOWN
        #     and len(current_task.get_subtasks()) > 0
        #     or len(self.task_stack) == 1
        # ):
        #     pass
        if len(self.task_stack) == 1:
            pass
        else:
            res = self.judge_complexity(current_task)
            if not res:
                current_task.set_status(TaskStatus.EXECUTION)
                return None

        current_task.set_status(TaskStatus.BREAKDOWN)
        # current_task.set_subtasks(self.solve_complexity(current_task, schema=schema))
        current_task.set_subtasks(self.solve_complexity(current_task))
        return self.schedule()

    def schedule(self):
        current_task = self.task_stack.get_current_task()

        if len(current_task.get_subtasks()) == 0:
            return None
        task = current_task.get_subtasks()[0]

        if current_task.name == task.name:
            logger.warning("The subtask name is identical to the parent task name.")
            return None

        self.tracer.add_trjectory(
            ActionRecord(
                action_type=TASK_TYPE,
                action_name=f"Schedule a subtask for the current task `{current_task}`",
                action_desc=Task(
                    # type=task.type,
                    name=task.name,
                    spec=task.spec,
                ).model_dump(),
            )
        )

        logger.info(f"Schedule a subtask `{task.name}` for `{current_task.name}`...\n")

        return task

    def execution(self):
        current_task = self.task_stack.get_current_task()
        logger.info(f"Executing task `{current_task.name}`...\n")

        tool_call, tool_output = Executor(agent=self.agent, tools=self.tools).execute(
            execution_prompt.format(task=current_task)
        )
        self.agent.remove_last_k_messages(2)

        tool_summary = self.agent.invoke(
            tool_output_prompt.format(
                task=current_task,
                tool_name=tool_call.tool_name,
                tool_args=tool_call.tool_args,
                output=tool_output,
            )
            + context_summary_prompt,
        )
        self.agent.remove_last_k_messages(2)

        tool_summary = tool_output_prompt.format(
            task=current_task,
            tool_name=tool_call.tool_name,
            tool_args=tool_call.tool_args,
            output=tool_summary,
        )
        action = Action(
            tool_call=tool_call,
            tool_output=tool_output,
            tool_summary=tool_summary,
        )

        # current_task.add_progress(action)
        self.task_stack.add_actions(action)
        self.task_stack.add_progress(tool_summary)

        if tool_call.tool_name != "write_file":
            action.tool_output = None
        self.tracer.add_trjectory(
            ActionRecord(
                action_type=TOOL_TYPE,
                action_name=f"Execute a tool for the current task `{current_task}`",
                action_desc=action.model_dump(),
            )
        )

        return tool_call

    def backtrack(self):
        child_task = self.task_stack.get_current_task()
        self.task_stack.pop_task()
        parent_task = self.task_stack.get_current_task()

        # if len(parent_task.get_subtasks()) > 1:
        #     parent_task.set_subtasks(parent_task.get_subtasks()[1:])
        #     # task = self.schedule()
        #     # if task:
        #     #     task.set_status(TaskStatus.STARTED)
        #     #     self.task_stack.push_task(task)
        # else:
        #     parent_task.set_subtasks([])
        # parent_task.add_progress(child_task)

        logger.info(
            f"Backtracking from task `{child_task.name}` to `{parent_task.name}`...\n"
        )

    def solve_feedback(self, feedback):
        # res = self.agent.invoke(solve_feedback_prompt.format(feedback=feedback))

        # self.experience.append(res)
        # self.task_stack.add_progress(
        #     f"The feedback from the user: `{feedback}` and the learned lessons: `{res}`."
        # )
        # current_task = self.task_stack.get_current_task()
        # self.task_stack.add_progress(
        #     f"The feedback from the user for the current task `{current_task.name}`: `{feedback}`."
        # )
        # current_task = self.task_stack.get_current_task()
        self.task_stack.add_progress(f"The feedback from the user : `{feedback}`.")

        self.tracer.add_trjectory(
            ActionRecord(
                action_type=FEEDBACK_TYPE,
                action_name=f"Feedback from the user",
                action_desc={
                    "feedback": feedback,
                    # "experience": res,
                },
            )
        )

    # def evaluate(self):
    #     agent = Agent(llm=get_llm(), msgs=[])

    #     res = agent.invoke_with_structured_output(
    #         eval_prompt.format(
    #             task=self.init_prompt,
    #             context=self.tracer.get_trjectory(),
    #         ),
    #         load_json=False,
    #     )

    #     self.tracer.add_experience(res)
    #     self.experience.add_experience(res)

    def report(self):
        task = self.task_stack.get_final_task()
        logger.info(f"Reporting task `{task.name}`...\n")

        res = self.agent.invoke(task_progress_prompt.format(task=task))

        for progress in self.task_stack.get_progress():
            self.context.append_context(
                Context(
                    metadata=MetaData(source="tool_execution_summary"),
                    content=progress,
                )
            )

        self.task_stack.clear_progress()
        self.task_stack.add_progress(res)

        res = self.agent.invoke_with_structured_output(
            remove_context_prompt.format(task=task)
        )
        self.agent.remove_last_k_messages(4)
        self.context.remove_context(res)

    def solve(self, debug=False, recent_actions_limit=10):
        feedback = None

        while not self.task_stack.is_empty():
            self.set_system_prompt(include_tools=True)
            self.agent.print_history()

            # import time

            # time.sleep(3)

            res = self.continue_or_not(feedback=feedback)

            if debug:
                input(f"Press Enter to continue...")
            feedback = get_feedback()
            if feedback:
                self.solve_feedback(feedback)
                continue

            if not res:
                if len(self.task_stack) == 1:
                    # self.evaluate()
                    return
                self.backtrack()
                if (
                    len(self.task_stack.get_progress())
                    >= recent_actions_limit
                    # and len(self.task_stack) == 2
                ):
                    self.report()
                continue

            task = self.breakdown()

            if debug:
                input(f"Press Enter to breakdown...")
            feedback = get_feedback()
            if feedback:
                self.solve_feedback(feedback)
                continue

            if task:
                self.task_stack.push_task(task)
                continue

            self.set_system_prompt(include_tools=True)
            self.agent.print_history()

            self.execution()

            if debug:
                input(f"Press Enter to execution...")
            feedback = get_feedback()
            if feedback:
                self.solve_feedback(feedback)
                continue

    # def react(self):
    #     while not self.task_stack.is_empty():
    #         self.set_system_prompt()
    #         self.agent.print_history()
    #         tool_call = self.execution()
    #         if tool_call.tool_name == "write_completion_report":
    #             break


if __name__ == "__main__":
    while True:
        # llm = get_llm()
        llm = get_llm(
            base_url=DefaultConfig.agent_api_base,
            api_key=DefaultConfig.agent_api_key,
            model_name=DefaultConfig.agent_model,
        )
        agent = Agent(llm=llm, msgs=[])
        context = ContextManager()
        # context.append_context(
        #     Context(
        #         metadata=MetaData(source="Given Information"),
        #         content="""The development environment has been set up successfully using PlatformIO (with unity test framework), along with ESP-IDF v5.4 framework.
        #     # ESP32S3 and INMP441 Microphone and MAX98357A Digital Amplifier Connections
        #     - **ESP32S3 GPIO4 (I2S0 Master)** → **INMP441 WS**
        #     - **ESP32S3 GPIO5 (I2S0 Master)** → **INMP441 SCK**
        #     - **ESP32S3 GPIO6 (I2S0 Master)** → **INMP441 SD**
        #     - **ESP32S3 GPIO7 (I2S1 Master)** → **MAX98357A DIN**
        #     - **ESP32S3 GPIO15 (I2S1 Master)** → **MAX98357A BCLK**
        #     - **ESP32S3 GPIO16 (I2S1 Master)** → **MAX98357A LRC**
        #     """,
        #     )
        # )
        # context.append_context(
        #     Context(
        #         metadata=MetaData(source="Given Information"),
        #         content="""The development environment has been set up successfully using PlatformIO, along with esp32-camera and opencv library (lib/esp32-camera and lib/opencv library are ready).
        #                 # Hardware Schematic (ESP32 & 0v2640 camera)
        # | 字段名            | 描述                         | ESP32对应引脚       |
        # |-------------------|------------------------------|----------------|
        # | `pin_pwdn`        | 摄像头电源控制引脚             | GPIO32        |
        # | `pin_reset`       | 摄像头复位引脚                 | NC          |
        # | `pin_xclk`        | 摄像头 XCLK 引脚               |GPIO0 |
        # | `pin_sccb_sda`    | 摄像头 SDA 数据线(I2C)       | 对应 TWI_SDA(GPIO26) |
        # | `pin_sccb_scl`    | 摄像头 SCL 时钟线(I2C)       | 对应 TWI_SCK(GPIO27) |
        # | `pin_d7`          | 摄像头数据线 D7               | 对应 CSI_D7(GPIO35) |
        # | `pin_d6`          | 摄像头数据线 D6               | 对应 CSI_D6(GPIO34) |
        # | `pin_d5`          | 摄像头数据线 D5               | 对应 CSI_D5(GPIO39) |
        # | `pin_d4`          | 摄像头数据线 D4               | 对应 CSI_D4(GPIO36) |
        # | `pin_d3`          | 摄像头数据线 D3               | 对应 CSI_D3(GPIO21) |
        # | `pin_d2`          | 摄像头数据线 D2               | 对应 CSI_D2(GPIO19) |
        # | `pin_d1`          | 摄像头数据线 D1               | 对应 CSI_D1(GPIO18) |
        # | `pin_d0`          | 摄像头数据线 D0               | 对应 CSI_D0(GPIO5) |
        # | `pin_vsync`       | 摄像头 VSYNC 垂直同步信号线    | 对应 CSI_VSYNC(GPIO25) |
        # | `pin_href`        | 摄像头 HREF 水平参考信号线     | 对应 CSI_HSYNC(GPIO23) |
        # | `pin_pclk`        | 摄像头 PCLK 像素时钟线        | 对应 CSI_PCLK(GPIO22) |""",
        #     )
        # )

        vscode_client = VSCodeClient(base_url=DefaultConfig.vscode_api_base)
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
                ToolSpec(
                    tool_desc="Search information from the external web internet again if the information is not found in the internal knowledge base",
                    tool_call=ToolCall(
                        tool_name="search_information_from_web_internet",
                        tool_args={
                            "task": "The objective of the search information and which information is to be acquired.",
                        },
                    ),
                    tool_func=run_web_search,
                ),
                ToolSpec(
                    tool_desc="View directory structure in the workspace",
                    tool_call=ToolCall(
                        tool_name="view_directory",
                        tool_args={
                            "path": "The path of the directory to view the structure, e.g., / represents the root directory of the workspace."
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
                    tool_desc="Build device",
                    tool_call=ToolCall(
                        tool_name="PioBuildDevice",
                        tool_args={},
                    ),
                    tool_func=vscode_client.PioBuildDevice,
                ),
                ToolSpec(
                    tool_desc="Upload and monitor device",
                    tool_call=ToolCall(
                        tool_name="PioUploadMonitorDevice",
                        tool_args={},
                    ),
                    tool_func=vscode_client.PioUploadMonitorDevice,
                ),
                ToolSpec(
                    tool_desc="Run test cases",
                    tool_call=ToolCall(
                        tool_name="PioRunTestCases",
                        tool_args={},
                    ),
                    tool_func=vscode_client.PioRunTestCases,
                ),
                ToolSpec(
                    tool_desc="Execute a shell command in the VSCode terminal",
                    tool_call=ToolCall(
                        tool_name="executeCommandInTerminal",
                        tool_args={
                            "command_line": "Command line to execute, e.g. 'ls' to list files."
                        },
                    ),
                    tool_func=vscode_client.executeCommandInPioTerminal,
                ),
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
                #     tool_desc="Write a task completion report when the task has been verified as completed.",
                #     tool_call=ToolCall(
                #         tool_name="write_completion_report",
                #         tool_args={},
                #     ),
                #     tool_func=lambda x: x,
                # ),
                ToolSpec(
                    tool_desc="Ask human for help if needed",
                    tool_call=ToolCall(
                        tool_name="ask_human",
                        tool_args={"help": "The specific help needed from the human."},
                    ),
                    tool_func=ask_help,
                ),
            ]
        )

        task = Task(
            # name="design, develop, and test firmware",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to implement an echo function using i2s, ring buffer, freertos, which means capturing audio through a microphone and playing it back through a speaker. The deliverables include comprehensive documentation (design documents, API references) and code (implementation code, test code). 首先,编写详细的设计文档, 包括子模块的开发spec和测试spec""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-CAM (ESP32-WROVER-E). The requirement is to implement an infinite loop that (starting from capturing 128x128 grayscale image), every 250ms, checks the time interval since the last high-resolution image capture. If the interval is greater than or equal to 5 seconds, switch the resolution to 640x480, capture a 640x480 JPEG image (jpeg_quality 12). If the interval is less than 5 seconds, switch the resolution to 128x128 (without reinitialization), capture a 128x128 grayscale image. Note: A detailed requirement document has been written in docs/requirement.md. The development environment has been successfully set up using PlatformIO, along with ESP-IDF v5.4 (bluetooth), esp32-camera (image capture), and OpenCV (calcOpticalFlowPyrLK) library (lib/esp32-camera and lib/opencv libraries are ready). The implementation should be as simple as possible and placed in separate files so that each file is as simple as possible. The initial code has been developed and needs to be tested.""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-CAM (ESP32-WROVER-E). The requirement is to implement an infinite loop that (starting from capturing 128x128 grayscale image), every 250ms, checks the time interval since the last high-resolution image capture. If the interval is greater than or equal to 5 seconds, switch the resolution to 640x480, capture a 640x480 JPEG image (jpeg_quality 12). If the interval is less than 5 seconds, switch the resolution to 128x128 (without reinitialization), capture a 128x128 grayscale image. After capturing the grayscale image, if there is a previous grayscale image, calculate the optical flow between the current and the previous grayscale images using calcOpticalFlowPyrLK with 256 flow points, evenly sampled at 16x16. Note: A detailed requirement document has been written in docs/requirement.md. The development environment has been successfully set up using PlatformIO, along with ESP-IDF v5.4 (bluetooth), esp32-camera (image capture), and OpenCV (calcOpticalFlowPyrLK) library (lib/esp32-camera and lib/opencv libraries are ready). The implementation should be as simple as possible and placed in separate files so that each file is as simple as possible. The initial code has been developed and needs to be tested.""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-CAM (ESP32-WROVER-E). The requirement is to implement an infinite loop that (starting from capturing 128x128 grayscale image), every 250ms, checks the time interval since the last high-resolution image capture. If the interval is greater than or equal to 5 seconds, switch the resolution to 640x480, capture a 640x480 JPEG image (jpeg_quality 12). If the interval is less than 5 seconds, switch the resolution to 128x128 (without reinitialization), capture a 128x128 grayscale image. After capturing the grayscale image, if there is a previous grayscale image, calculate the optical flow between the current and the previous grayscale images using calcOpticalFlowPyrLK with 256 flow points, evenly sampled at 16x16. Note: A detailed requirement document has been written in docs/requirement.md. The development environment has been successfully set up using PlatformIO, along with ESP-IDF v5.4 (bluetooth), esp32-camera (image capture), and OpenCV (calcOpticalFlowPyrLK) library (lib/esp32-camera and lib/opencv libraries are ready). The implementation should be as simple as possible and placed in separate files so that each file is as simple as possible.""",
            # description="""The task is to write a c program to print hello world in the computer, just write a c program and use gcc to compile and get an executable program. do not care things about esp or platformio etc.""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-WROVER-E. The requirement is to implement a timed photo capture function, where a photo is taken every 5 seconds.""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to implement an echo function using i2s, ring buffer, freertos, which means capturing audio through a microphone and playing it back through a speaker. The deliverables include comprehensive documentation (design documents, API references) and code (implementation code, test code).""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements. Note: The development environment has been set up successfully using PlatformIO, along with ESP-IDF framework.""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to implement an echo function without buffer, which means capturing audio through a microphone and playing it back through a speaker.""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to implement playing random audio through a speaker every 1 second in while loop without using buffer.""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to implement an echo function without buffer, which means capturing audio through a microphone and playing it back through a speaker. 任务：编写详细的设计文档, 包括子模块的开发spec和测试spec""",
            # description="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to implement an echo function without buffer, which means capturing audio through a microphone and playing it back through a speaker. 任务: 细化I2S Configuration Module的设计, 包括它的子模块的开发spec和测试spec""",
            # description="""为了完成需求，根据测试驱动开发的方法, 先编写测试markdown文档, 测试文档包括当前需求的测试场景、预期结果、验证方式""",
            # description="""为了达到测试场景的预期结果, 接着编写设计的markdown文档, 设计文档包括满足当前需求的子模块, 每个模块的输入输出, 以及模块间的依赖关系""",
            # description="""为了达到测试场景的预期结果, 接着编写I2S Configuration Module的测试markdown文档, 测试文档包括当前需求的测试场景、预期结果、验证方式""",
            # description="""为了达到I2S Configuration Module测试场景的预期结果, 接着编写I2S Configuration Module的设计markdown文档, 设计文档包括满足当前需求的子模块, 每个模块的输入输出, 以及模块间的依赖关系""",
            # description="""为了达到I2S Configuration Module测试场景的预期结果, 接着编写I2S0 (Microphone Submodule)的测试markdown文档, 测试文档包括当前需求的测试场景、预期结果、验证方式""",
            # description="""为了达到I2S0 (Microphone Submodule)测试场景的预期结果, 接着编写实现I2S0 (Microphone Submodule)的代码, 包括详细的注释, 验证正确性的日志""",
            # description="""为了达到I2S0 (Microphone Submodule)测试场景的预期结果, 接着编写测试I2S0 (Microphone Submodule)的代码, 并完成测试和验证""",
            # description="""任务: 为了验证I2S Configuration Module的正确性, 需要添加相应的测试用例, 并运行测试""",
            # type="user_requirement",
            name="user requirement",
            # spec="""The requirement is to implement an echo function using esp-idf ring buffer, which means capturing audio through a microphone and playing it back through a speaker.""",
            spec="""The task is to design, develop, and test basic firmware based on the ESP32-S3. The requirement is to print 'Hello World' on the serial monitor using log statements. Note: The development environment has been set up successfully using PlatformIO, along with ESP-IDF framework.""",
        )
        task_stack = TaskStack()
        task_stack.push_task(TaskNode.from_task(task))

        # vscode_client.close_all_open_text_documents()
        # vscode_client.executeCommandInTerminal(f"git checkout init_start")
        # vscode_client.executeCommandInTerminal(f"git checkout camera")
        # vscode_client.executeCommandInTerminal("git reset --hard")
        # vscode_client.executeCommandInTerminal("git clean -fd")

        import datetime

        new_branch_name = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        # vscode_client.executeCommandInTerminal(f"git checkout -b {new_branch_name}")

        path = f"./trajectory_{new_branch_name}.txt"
        exp_path = f"./experiences.txt"

        agent = Planner(
            agent=agent,
            tools=tools,
            task_stack=task_stack,
            context=context,
            tracer=Tracer(trj_path=path, exp_path=exp_path),
            experience=ExperienceCollector(),
        )
        agent.solve(debug=True)

        # vscode_client.executeCommandInTerminal("git add .")
        # vscode_client.executeCommandInTerminal(f'git commit -m "{new_branch_name}"')

        # input("Press Enter")
        break
