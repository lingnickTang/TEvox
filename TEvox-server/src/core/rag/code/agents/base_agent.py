"""
基础 Agent 类，提供通用的工具调用功能
"""
import json
import re
import inspect
from typing import Dict, Any, Callable, Optional
from src.base import ToolCall
from src.utils.log import logger


class BaseAgent:
    """
    基础 Agent 类，提供工具注册、执行和解析的通用功能
    """
    
    def __init__(self):
        """初始化基础 Agent"""
        # 工具注册表: name -> function
        self.tools: Dict[str, Callable] = {}
    
    def register_tool(self, name: str, func: Callable):
        """
        注册工具函数
        
        Args:
            name: 工具名称
            func: 工具函数
        """
        self.tools[name] = func
        logger.info(f"Registered tool: {name}")
    
    def _execute_tool(self, tool_call: ToolCall) -> Any:
        """
        执行工具调用
        
        Args:
            tool_call: ToolCall 实例
            
        Returns:
            工具执行结果
            
        Raises:
            ValueError: 如果工具未找到或执行失败
        """
        if tool_call.tool_name not in self.tools:
            available_tools = list(self.tools.keys())
            raise ValueError(
                f"Tool '{tool_call.tool_name}' not found. Available tools: {available_tools}"
            )
        
        try:
            func = self.tools[tool_call.tool_name]
            result = func(**tool_call.tool_args)
            logger.info(f"Executed tool '{tool_call.tool_name}' with args {tool_call.tool_args}")
            return result
        except Exception as e:
            raise ValueError(f"Tool execution failed: {str(e)}")
    
    def _parse_tool_call(self, response: str, agent) -> Optional[ToolCall]:
        """
        从 LLM 响应中解析工具调用
        
        Args:
            response: LLM 响应字符串
            agent: Agent 实例，用于结构化输出
            
        Returns:
            ToolCall 实例（如果找到），否则为 None
        """      
        # 尝试使用结构化输出
        try:
            result = agent.invoke_with_structured_output(
                f"Extract tool call from this response. If no tool call, return tool_name='none':\n{response}",
                schema=ToolCall
            )
            if isinstance(result, dict) and result.get("tool_name") != "none":
                return ToolCall(**result)
        except Exception:
            pass
        
        return None
    
    def get_tools_description(self) -> str:
        """
        生成已注册工具的描述字符串
        
        Returns:
            工具描述字符串，包含每个工具的名称、描述和参数信息
        """
        if not self.tools:
            return "No tools available."
        
        descriptions = []
        for tool_name, tool_func in self.tools.items():
            # 获取函数文档字符串
            doc = inspect.getdoc(tool_func) or "No description available"

            # 构建工具描述
            tool_desc = f"""- {tool_name}:{doc}"""
            
            descriptions.append(tool_desc)
        
        return "\n\n".join(descriptions)

