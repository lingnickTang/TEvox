import os
import re
import json
import uuid
import datetime
import pandas as pd

import torch
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.base import ToolCall, ToolSpec, ToolKit
from src.core.tools.vscode import VSCodeClient
from src.core.agents.workspace import FileEditAction
from src.core.tools.search import search_information
from src.utils import Agent, get_llm, logger
from openrlhf.custom.self_eval import pre_eval, post_eval
from openrlhf.custom.sampler import DatasetSampler, Trajectory
from openrlhf.custom.prompt import AGENT_USER_PROMPT, convert_to_langchain_messages


# vscode_client = VSCodeClient(base_url="http://10.166.104.94:6789")
vscode_client = VSCodeClient(base_url="http://10.166.41.116:6789")


def _search_information(query: str):
    pass


def _open_file(file_path: str):
    pass


def _delete_path(path: str):
    pass


def _get_directory_files(path: str):
    pass


def _write_file(file_path: str, task_desc: str):
    pass


def PioBuildDevice():
    pass


def PioUploadMonitorDevice():
    pass


def executeCommandInTerminal(command_line: str):
    pass


def _write_completion_report():
    pass


check_tools = ToolKit(
    [
        ToolSpec(
            tool_desc="Search information from the relevant documents and dependent libraries",
            tool_call=ToolCall(
                tool_name="search_information",
                tool_args={
                    "query": "The objective of the search information and which information is to be acquired",
                },
            ),
            tool_func=_search_information,
        ),
        ToolSpec(
            tool_desc="Open a file in the VSCode editor",
            tool_call=ToolCall(
                tool_name="open_file",
                tool_args={"file_path": "The path of the file to open"},
            ),
            tool_func=_open_file,
        ),
        ToolSpec(
            tool_desc="Deletes a file or directory in the VSCode editor",
            tool_call=ToolCall(
                tool_name="delete_path",
                tool_args={"path": "The path of the file or directory to be deleted"},
            ),
            tool_func=_delete_path,
        ),
        ToolSpec(
            tool_desc="Get the files and subdirectories of a directory",
            tool_call=ToolCall(
                tool_name="get_directory_files",
                tool_args={
                    "path": "The path of the directory to get the files and subdirectories"
                },
            ),
            tool_func=_get_directory_files,
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
            tool_func=_write_file,
        ),
        ToolSpec(
            tool_desc="Build device",
            tool_call=ToolCall(
                tool_name="PioBuildDevice",
                tool_args={},
            ),
            tool_func=PioBuildDevice,
        ),
        ToolSpec(
            tool_desc="Upload and monitor device",
            tool_call=ToolCall(
                tool_name="PioUploadMonitorDevice",
                tool_args={},
            ),
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
        ),
        ToolSpec(
            tool_desc="Write a task completion report when the task has been verified as completed.",
            tool_call=ToolCall(
                tool_name="write_completion_report",
                tool_args={},
            ),
            tool_func=_write_completion_report,
        ),
    ]
)


# tools = ToolKit(
#     [
#         ToolSpec(
#             tool_desc="Search information from the relevant documents and dependent libraries",
#             tool_call=ToolCall(
#                 tool_name="search_information",
#                 tool_args={
#                     "query": "The objective of the search information and which information is to be acquired",
#                 },
#             ),
#             tool_func=exec_search_information,
#         ),
#         ToolSpec(
#             tool_desc="Open a file in the VSCode editor",
#             tool_call=ToolCall(
#                 tool_name="open_file",
#                 tool_args={"file_path": "The path of the file to open"},
#             ),
#             tool_func=vscode_client.open_file,
#         ),
#         ToolSpec(
#             tool_desc="Deletes a file or directory in the VSCode editor",
#             tool_call=ToolCall(
#                 tool_name="delete_path",
#                 tool_args={"path": "The path of the file or directory to be deleted"},
#             ),
#             tool_func=vscode_client.delete_path,
#         ),
#         ToolSpec(
#             tool_desc="Get the files and subdirectories of a directory",
#             tool_call=ToolCall(
#                 tool_name="get_directory_files",
#                 tool_args={
#                     "path": "The path of the directory to get the files and subdirectories"
#                 },
#             ),
#             tool_func=vscode_client.get_directory_files,
#         ),
#         ToolSpec(
#             tool_desc="Write content to a new file or edit an existing file in the VSCode editor",
#             tool_call=ToolCall(
#                 tool_name="write_file",
#                 tool_args={
#                     "file_path": "The path of the file to be edited",
#                     "task_desc": "The simple and specific instruction for which content is to be written",
#                 },
#             ),
#             tool_func=FileEditAction(
#                 vscode_client=vscode_client, agent=Agent(llm=get_llm(), msgs=[])
#             ).edit_file,
#         ),
#         ToolSpec(
#             tool_desc="Build device",
#             tool_call=ToolCall(
#                 tool_name="PioBuildDevice",
#                 tool_args={},
#             ),
#             tool_func=vscode_client.PioBuildDevice,
#         ),
#         ToolSpec(
#             tool_desc="Upload and monitor device",
#             tool_call=ToolCall(
#                 tool_name="PioUploadMonitorDevice",
#                 tool_args={},
#             ),
#             tool_func=vscode_client.PioUploadMonitorDevice,
#         ),
#         ToolSpec(
#             tool_desc="Execute a shell command in the VSCode terminal",
#             tool_call=ToolCall(
#                 tool_name="executeCommandInTerminal",
#                 tool_args={
#                     "command_line": "Command line to execute, e.g. 'ls' to list files."
#                 },
#             ),
#             tool_func=vscode_client.executeCommandInTerminal,
#         ),
#         ToolSpec(
#             tool_desc="Write a task completion report when the task has been verified as completed.",
#             tool_call=ToolCall(
#                 tool_name="write_completion_report",
#                 tool_args={},
#             ),
#             tool_func=_write_completion_report,
#         ),
#     ]
# )


# for item in tools.execute_tool(
#     ToolCall(tool_name="search_information", tool_args={"query": "print log"})
# ):
#     print(item)
# print(tools.execute_tool(ToolCall(tool_name="open_file", tool_args={"file_path": "src/main.c"})))
# print(tools.execute_tool(ToolCall(tool_name="delete_path", tool_args={"path": "test_path"})))
# print(
#     tools.execute_tool(
#         ToolCall(tool_name="get_directory_files", tool_args={"path": "/"})
#     )
# )
# tools.execute_tool(ToolCall(tool_name="write_file", tool_args={"file_path": "src/main.c", "task_desc": "print hello world"}))
# tools.execute_tool(ToolCall(tool_name="PioBuildDevice", tool_args={}))
# tools.execute_tool(ToolCall(tool_name="PioUploadMonitorDevice", tool_args={}))
# print(
#     tools.execute_tool(
#         ToolCall(tool_name="executeCommandInTerminal", tool_args={"command_line": "ls"})
#     )
# )


def count_tags(text: str) -> float:
    count = 0.0
    if text.count("<think>") == 1:
        count += 0.25
    if text.count("</think>") == 1:
        count += 0.25
    if text.count("<action>") == 1:
        count += 0.25
    if text.count("</action>") == 1:
        count += 0.25
    return count


def parse_format(text: str):
    pattern = r"^<think>.*?</think>\s*<action>.*?</action>$"
    return re.match(pattern, text, re.DOTALL)


def parse_json(json_str: str):
    pattern = r"^```json(.*)```$"
    matches = re.findall(pattern, json_str, re.DOTALL)
    if not matches or len(matches) > 1:
        return None
    try:
        return json.loads(matches[-1])
    except Exception as e:
        return None


def extract_action(text: str) -> str | None:
    extracted_action = re.search(r"<action>(.*?)</action>", text, re.DOTALL)
    if not extracted_action:
        return None
    extracted_action = parse_json(extracted_action.group(1).strip())
    if not extracted_action:
        return None
    try:
        return ToolCall.model_validate(extracted_action)
    except Exception as e:
        return None


def reward_func(prompts, completions, labels, infos):
    rewards = []
    for prompt, completion, info in zip(prompts, completions, infos):
        completion = completion.rstrip("<|im_end|>")
        print("xxxprompt", prompt)
        print("xxxcompletion", completion)
        print("xxxinfo", info)

        reward = count_tags(completion)
        # reward = 0.0

        if not parse_format(completion):
            rewards.append(reward)
            continue
        else:
            reward += 1.0

        action = extract_action(completion)
        if not action:
            rewards.append(reward)
            continue

        try:
            check_tools.execute_tool(action)
            reward += 1.0
        except Exception as e:
            logger.error(f"Error in check_tools: {e}")
            rewards.append(reward)
            continue

        try:
            self_eval_reward = pre_eval(trajectory.prompt, completion).reward
            self_eval_reward = min(max(0.0, self_eval_reward), 1.0)
            reward += self_eval_reward
        except Exception as e:
            logger.error(f"Error in self_eval: {e}")
            rewards.append(reward)
            continue

        if self_eval_reward <= 0:
            rewards.append(reward)
            continue

        sampler = DatasetSampler()
        try:
            trajectory, task = sampler.get_trajectory_with_task(
                trajectory_id=info["id"]
            )
        except Exception as e:
            logger.error(f"Error in get_trajectory_with_task: {e}")
            rewards.append(reward)
            continue

        if action.tool_name == "write_completion_report":
            trajectory.prompt.extend(
                [
                    {"role": "assistant", "content": completion},
                ]
            )
            trajectory.status = False
            sampler.upsert_many_trajectories([trajectory])
            reward += 2.0
            continue

        if not trajectory.branch:
            # 1. 首先切换到任务分支
            vscode_client.executeCommandInPioTerminal(f"git checkout {task.branch}")

            # 2. 重置分支到最新状态
            vscode_client.executeCommandInPioTerminal("git reset --hard")

            # 3. 创建新分支并切换 (分支名格式: task_id + trajectory_id)
            new_branch_name = f"{task.id}_{trajectory.id}"
            vscode_client.executeCommandInPioTerminal(
                f"git checkout -b {new_branch_name}"
            )

            # 4. 更新轨迹的分支信息
            trajectory.branch = new_branch_name
            sampler.upsert_many_trajectories([trajectory])
        else:
            vscode_client.executeCommandInPioTerminal(
                f"git checkout {trajectory.branch}"
            )
            vscode_client.executeCommandInPioTerminal("git reset --hard")

        tools = ToolKit(
            [
                ToolSpec(
                    tool_desc="Search information from the relevant documents and dependent libraries",
                    tool_call=ToolCall(
                        tool_name="search_information",
                        tool_args={
                            "query": "The objective of the search information and which information is to be acquired",
                        },
                    ),
                    tool_func=search_information,
                ),
                ToolSpec(
                    tool_desc="Open a file in the VSCode editor",
                    tool_call=ToolCall(
                        tool_name="open_file",
                        tool_args={"file_path": "The path of the file to open"},
                    ),
                    tool_func=vscode_client.open_file,
                ),
                ToolSpec(
                    tool_desc="Deletes a file or directory in the VSCode editor",
                    tool_call=ToolCall(
                        tool_name="delete_path",
                        tool_args={
                            "path": "The path of the file or directory to be deleted"
                        },
                    ),
                    tool_func=vscode_client.delete_path,
                ),
                ToolSpec(
                    tool_desc="Get the files and subdirectories of a directory",
                    tool_call=ToolCall(
                        tool_name="get_directory_files",
                        tool_args={
                            "path": "The path of the directory to get the files and subdirectories"
                        },
                    ),
                    tool_func=vscode_client.get_directory_files,
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
                        vscode_client=vscode_client,
                        agent=Agent(
                            llm=get_llm(),
                            msgs=convert_to_langchain_messages(
                                trajectory.prompt
                                + [{"role": "assistant", "content": completion}]
                            ),
                        ),
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
                    tool_desc="Write a task completion report when the task has been verified as completed.",
                    tool_call=ToolCall(
                        tool_name="write_completion_report",
                        tool_args={},
                    ),
                    tool_func=_write_completion_report,
                ),
            ]
        )

        # action = ToolCall(tool_name="get_directory_files", tool_args={"path": "/"})

        try:
            tool_output = tools.execute_tool(action)
            reward += 1.0
        except Exception as e:
            rewards.append(reward)
            logger.error(f"Error in execute_tool: {e}")
            continue

        print("action", action)
        print("tool_output", tool_output)

        try:
            self_eval_reward = post_eval(
                trajectory.prompt, completion, feedback=tool_output
            ).reward
            self_eval_reward = min(max(0.0, self_eval_reward), 1.0)
            reward += self_eval_reward
        except Exception as e:
            logger.error(f"Error in self_eval: {e}")
            rewards.append(reward)
            continue

        rewards.append(reward)

        if self_eval_reward <= 0:
            continue

        # 1. 创建新分支并切换 (分支名格式: task_id + trajectory_id + "_new")
        new_branch_name = f"{task.id}_{trajectory.id}_new"
        vscode_client.executeCommandInPioTerminal(f"git checkout -b {new_branch_name}")

        # 2. 提交当前所有更改到新分支
        vscode_client.executeCommandInPioTerminal("git add .")
        vscode_client.executeCommandInPioTerminal(
            f'git commit -m "Checkout from {trajectory.branch}"'
        )

        tool_output_prompt = """The tool `{tool_name}` with args `{tool_args}` has been executed and its output is as follows: `{output}`\n\n"""
        trajectory.prompt.extend(
            [
                {"role": "assistant", "content": completion},
                {
                    "role": "user",
                    "content": tool_output_prompt.format(
                        tool_name=action.tool_name,
                        tool_args=action.tool_args,
                        output=tool_output,
                    )
                    + AGENT_USER_PROMPT,
                },
            ]
        )
        trajectory.id = str(uuid.uuid4())
        trajectory.branch = new_branch_name
        sampler.upsert_many_trajectories([trajectory])

    # 生成唯一的JSON文件名（使用时间戳和UUID）
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    # 设置文件保存路径为~/openrlhf/samples目录下
    json_filename = os.path.expanduser(
        f"~/openrlhf/samples/trajectory_data_{timestamp}_{unique_id}.json"
    )
    # 确保目标目录存在
    os.makedirs(os.path.dirname(json_filename), exist_ok=True)

    # 准备要保存的数据
    data_to_save = [
        {"prompt": p, "completion": c, "reward": r, "info": i}
        for p, c, r, i in zip(prompts, completions, rewards, infos)
    ]

    # 将数据保存到JSON文件
    try:
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        logger.info(f"成功保存数据到文件: {json_filename}")
    except Exception as e:
        logger.error(f"保存JSON文件失败: {e}")

    return torch.Tensor(rewards)
