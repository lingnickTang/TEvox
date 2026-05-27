from typing import List, Dict, Any, Callable
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool_name: str = Field(description="The name of the tool to be executed")
    tool_args: Dict[str, Any] = Field(
        default_factory=dict, description="The required arguments for the tool"
    )


class ToolSpec(BaseModel):
    tool_desc: str = Field(description="The functional description of the tool")
    tool_call: ToolCall = Field(description="The name and arguments of the tool")
    tool_func: Callable = Field(description="The function to be executed by the tool")
    default_args: Dict[str, Any] = Field(
        default_factory=dict, description="The default arguments for the tool"
    )

    def __str__(self) -> str:
        return f"### {self.tool_desc}\n```json\n{self.tool_call.model_dump_json(indent=4)}\n```"


class ToolKit:

    def __init__(self, tools: List[ToolSpec]):
        self._tools = {tool.tool_call.tool_name: tool for tool in tools}

    def execute_tool(self, tool_call: ToolCall):
        if tool_call.tool_name not in self._tools:
            raise ValueError(
                f"The tool_name {tool_call.tool_name} is unavailable. The available tools are: {list(self._tools.keys())}"
            )
        try:
            return self._tools[tool_call.tool_name].tool_func(
                **{
                    **self._tools[tool_call.tool_name].default_args,
                    **tool_call.tool_args,
                }
            )
        except Exception as e:
            raise ValueError(
                f"Executing the tool `{tool_call.tool_name}` with args `{tool_call.tool_args}` failed: {str(e)}"
            )

    def __str__(self) -> str:
        return "\n\n".join([str(tool) for tool in self._tools.values()])


if __name__ == "__main__":
    tools = [
        ToolSpec(
            tool_desc="xxx",
            tool_call=ToolCall(tool_name="xxx", tool_args={"x": 1}),
            tool_func=lambda x: x,
        ),
        ToolSpec(
            tool_desc="yyy",
            tool_call=ToolCall(tool_name="yyy", tool_args={"y": 2}),
            tool_func=lambda y: y,
        ),
    ]
    tool_kit = ToolKit(tools)
    print(tool_kit)
