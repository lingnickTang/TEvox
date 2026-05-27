from src.utils import logger, Agent
from src.base import ToolCall, ToolKit


class Executor:

    def __init__(
        self,
        agent: Agent,
        tools: ToolKit,
        debug=True,
    ):
        self.agent = agent
        self.tools = tools

    def execute(self, prompt: str, retry: int = 3):
        idx = len(self.agent.get_history()) + 1
        prefix = ""

        for i in range(retry):
            tool_call = self.agent.invoke_with_structured_output(
                input=prefix + prompt,
                schema=ToolCall,
            )

            # input(
            #     f"Press Enter to execute tool {tool_call.tool_name} with args: {tool_call.tool_args}"
            # )

            try:
                tool_output = self.tools.execute_tool(tool_call)
                break
            except Exception as e:
                prefix = f"Executing the tool `{tool_call.tool_name}` with args `{tool_call.tool_args}` failed: {str(e)}. "
                logger.warning(f"Failed to execute the tool: {str(e)}")
                if i == retry - 1:
                    raise e

        self.agent.insert_message(idx, self.agent.get_history()[-1])
        self.agent.retain_first_k_messages(idx + 1)

        logger.info(
            f"Executing tool {tool_call.tool_name} with args: {tool_call.tool_args}, output: {tool_output}"
        )

        return tool_call, tool_output
