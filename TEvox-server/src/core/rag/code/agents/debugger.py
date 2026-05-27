"""
调试器 Agent

用于代码调试的智能代理，支持：
- 编译代码（使用 idf.py build）
- 打开和修改文件
- 分析编译错误
- 修复代码问题
"""
from typing import Dict, Any, Optional, List
from src.utils import get_llm, Agent
from src.base import DefaultConfig, ToolCall
from src.utils.log import logger
from src.core.rag.code.tools.vscode import VSCodeClient
from src.core.rag.code.tools.file_operation_tool import (
    create_read_file_tool,
    create_write_file_tool,
)
from src.core.rag.code.tools.terminal_tool import create_esp_idf_build_tool
from src.core.rag.code.agents.base_agent import BaseAgent
from src.core.rag.code.agents.debugger_prompt import DEBUGGER_PROMPTS


class DebuggerAgent(BaseAgent):
    """
    调试器 Agent，用于自动化代码调试和修复
    """
    
    def __init__(self, agent: Optional[Agent] = None, base_url: str = "http://localhost:6789", vscode_client: Optional[VSCodeClient] = None):
        """
        初始化调试器 Agent
        
        Args:
            agent: 可选的 Agent 实例，如果为 None 则创建新实例
            base_url: VSCode API 服务器地址
            vscode_client: 可选的 VSCodeClient 实例，如果为 None 则创建新实例
        """
        super().__init__()
        
        if agent is None:
            llm = get_llm(model_name=DefaultConfig.agent_model)
            self.agent = Agent(llm)
        else:
            self.agent = agent
        
        # 初始化 VSCode 客户端
        if vscode_client is None:
            self.vscode_client = VSCodeClient(base_url=base_url)
        else:
            self.vscode_client = vscode_client
        
        # 注册工具
        self._register_tools()
        
        # 执行历史
        self.history: List[Dict[str, Any]] = []
    
    def _register_tools(self):
        """注册所有可用的工具"""
        self.register_tool("build", create_esp_idf_build_tool(self.vscode_client))
        self.register_tool("read_file", create_read_file_tool(self.vscode_client))
        self.register_tool("write_file", create_write_file_tool(self.vscode_client))
        
        logger.info("Debugger tools registered: build, read_file, write_file")
    
    def iterative_build_and_fix(
        self, 
        file_to_fix: str, 
        task_description: str = "", 
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        """
        迭代编译和修复流程
        
        Args:
            file_to_fix: 需要修复的文件路径
            task_description: 任务描述，用于指导修复的函数体
            max_iterations: 最大迭代次数，默认5次
            
        Returns:
            包含最终结果的字典，包含 success, iterations, final_code 字段
        """
        logger.info(f"Starting iterative build and fix process for file: {file_to_fix} (task description: {task_description}, max {max_iterations} iterations)")
        
        iteration = 0        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Iteration {iteration}/{max_iterations}")
            
            # 1. 执行编译
            build_result = self._execute_tool(ToolCall(
                tool_name="build",
                tool_args={}
            ))
            
            # 2. 分析编译结果（YAML格式）
            analysis_prompt = DEBUGGER_PROMPTS["build_analysis"].format(
                build_result=build_result
            )
            analysis_text = self.agent.invoke_with_structured_output(analysis_prompt)
            
            if analysis_text['success']:
                # 编译成功，读取文件，并调用agent获取最终修复后的函数体代码
                try:
                    file_content = self._execute_tool(ToolCall(
                        tool_name="read_file",
                        tool_args={"file_path": file_to_fix}
                    ))
                    
                    extract_function_body_prompt = DEBUGGER_PROMPTS["extract_function_body"].format(
                        task_description=task_description,
                        file_content=file_content
                    )
                    final_code = self.agent.invoke_with_structured_output(extract_function_body_prompt)['function_code']

                    
                    logger.info(f"Build successful, final code read from {file_to_fix}")
                except Exception as e:
                    logger.warning(f"Failed to read final code: {e}")
                    final_code = None   
                return {
                    "success": True,
                    "iterations": iteration,
                    "final_code": final_code  # 返回最终编译通过的文件内容
                }
            else:
                fix_suggestions = analysis_text['fix_suggestions']
            
            # 3. 如果不成功，进行修复
            logger.info(f"Build failed, attempting to fix file: {file_to_fix}")
            
            # 3.1 读取需要修复的文件
            file_content = self._execute_tool(ToolCall(
                tool_name="read_file",
                tool_args={"file_path": file_to_fix}
            ))
            
            # 5.2 生成write_file工具调用
            code_fix_prompt = DEBUGGER_PROMPTS["code_fix"].format(
                fix_suggestions=fix_suggestions,
                code=file_content,
                task_description=task_description
            )
            
            code_fix_response = self.agent.invoke_with_structured_output(code_fix_prompt)

            # 5.4 执行write_file工具
            tool_call = ToolCall(
                tool_name="write_file",
                tool_args={
                    "file_path": file_to_fix,
                    "content": code_fix_response['content'],
                    "start_line": code_fix_response['start_line'],
                    "end_line": code_fix_response['end_line'],
                    "edit_type": "replace"
                }
            )

            try:
                write_result = self._execute_tool(tool_call)
                logger.info(f"Fixed code written to {file_to_fix}: {write_result}")
            except Exception as e:
                logger.error(f"Failed to write fixed code: {e}")
                break
        
        # 达到最大迭代次数仍未成功，尝试extract_function_body获取最后一次的函数体代码
        try:
            file_content = self._execute_tool(ToolCall(
                tool_name="read_file",
                tool_args={"file_path": file_to_fix}
            ))
            extract_function_body_prompt = DEBUGGER_PROMPTS["extract_function_body"].format(
                task_description=task_description,
                file_content=file_content
            )
            final_code = self.agent.invoke_with_structured_output(extract_function_body_prompt)['function_code']
            return {
                "success": False,
                "iterations": iteration,
                "final_code": final_code  # 返回最后一次尝试的函数体代码
            }
        except Exception as e:
            logger.warning(f"Failed to extract final code: {e}")
            return None   

if __name__ == "__main__":
    debugger_agent = DebuggerAgent()
    debugger_agent.iterative_build_and_fix(file_to_fix="main/audio/codecs/es8388_audio_codec.cc")