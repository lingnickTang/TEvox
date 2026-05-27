"""
代码补全 Agent

用于智能代码生成和补全，支持：
- 基于需求生成完整代码
- 补全不完整的代码片段
- Reflection 机制：检查生成代码的隐式关联问题
"""
import re
import inspect
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.utils import get_llm, Agent, extract_code_block
from src.base import DefaultConfig, ToolCall
from src.utils.log import logger
from src.core.rag.code.tools.knowledge_tool import (
    create_get_module_interface_tool,
    create_get_system_design_tool,
    create_knowledge_graph_tool,
)
from src.core.rag.code.tools.file_operation_tool import (
    create_read_file_tool,
    create_write_file_tool,
    create_find_in_files_tool,
    create_find_references_tool,
    create_get_directory_files_tool,
)
from src.core.rag.code.tools.vscode import VSCodeClient
from src.core.rag.code.agents.base_agent import BaseAgent
from src.core.rag.code.agents.code_completer_prompt import CODE_COMPLETER_PROMPTS


class CodeCompleter(BaseAgent):
    """
    代码补全 Agent，用于智能代码生成和补全
    """
    
    def __init__(self, agent: Optional[Agent] = None, base_url: str = "http://localhost:6789", system_design_path: str = "evox-server/.rag/knowledge/system_design.json", model_name: str = "qwen3-coder-30b-a3b-instruct", module_interface_path: str = "evox-server/.rag/knowledge/module_interface.json", vscode_client: Optional[VSCodeClient] = None):
        """
        初始化代码补全 Agent
        
        Args:
            agent: 可选的 Agent 实例，如果为 None 则创建新实例
            base_url: VSCode API 服务器地址
            system_design_path: 系统设计 JSON 文件路径
            model_name: 模型名称
            module_interface_path: 模块接口 JSON 文件路径
            vscode_client: 可选的 VSCodeClient 实例，如果为 None 则创建新实例
        """
        super().__init__()
        
        if agent is None:
            llm = get_llm(model_name=model_name)
            self.agent = Agent(llm)
        else:
            self.agent = agent
        
        # 初始化 VSCode 客户端
        if vscode_client is None:
            self.vscode_client = VSCodeClient(base_url=base_url)
        else:
            self.vscode_client = vscode_client
        
        # 注册工具
        self.register_tool("get_module_interface", create_get_module_interface_tool(module_interface_path))
        self.register_tool("get_system_design", create_get_system_design_tool(system_design_path))
        self.register_tool("read_file", create_read_file_tool(self.vscode_client))
        self.register_tool("write_file", create_write_file_tool(self.vscode_client))
        # Reflection 工具
        self.register_tool("find_references", create_find_references_tool(self.vscode_client))
        self.register_tool("find_in_files", create_find_in_files_tool(self.vscode_client))
        self.register_tool("get_directory_files", create_get_directory_files_tool(self.vscode_client))
        self.register_tool("query_knowledge_graph", create_knowledge_graph_tool())
    
    def _build_knowledge_context(
        self,
        requirement: str,
        file_path: str
    ) -> str:
        """
        构建知识上下文，整合模块接口信息
        
        Args:
            requirement: 需求描述
            
        Returns:
            知识上下文字符串
        """
        
        # 获取模块接口信息
        try:
            # system_design = self._execute_tool(ToolCall(
            #     tool_name="get_system_design",
            # ))
            file_content = self._execute_tool(ToolCall(
                tool_name="read_file",
                tool_args={"file_path": file_path}
            ))

            # 根据 requirement+system_design+file_content 来判断需要哪些模块接口信息
            # prompt = CODE_COMPLETER_PROMPTS["filter_module_interface"].format(
            #     system_design=system_design,
            #     requirement=requirement,
            #     file_content=file_content
            # )
            # module_names = self.agent.invoke(prompt).split(",")
            # module_info = self._execute_tool(ToolCall(
            #     tool_name="get_module_interface",
            #     tool_args={"module_names": module_names}
            # ))
            #return "module_info: "+module_info+"\nfile_content: "+file_content
            return "file_content: "+file_content
        except Exception as e:
            logger.warning(f"Failed to get module interface or system design: {str(e)}")

    def reflect_on_code(
        self,
        generated_code: str,
        requirement: str,
        file_path: str,
        max_iterations: int = 2
    ) -> Dict[str, Any]:
        """
        对生成的代码进行反思，检查隐式关联问题
        
        Args:
            generated_code: 生成的代码
            requirement: 原始需求
            file_path: 目标文件路径
            max_iterations: 最大迭代次数
        
        Returns:
            {
                "information_collected": str,  # 收集的信息
                "refined_code": str,          # 改进后的代码（如果有问题）
            }
        """
        logger.info(f"Starting information collection for {file_path}")
        
        # 初始化上下文
        file_content = self._execute_tool(ToolCall(
            tool_name="read_file",
            tool_args={"file_path": file_path}
        ))

        context = {
            "requirement": requirement,
            "generated_code": generated_code,
            "file_content": file_content,
        }
        
        # 获取可用的 Reflection 工具描述
        reflection_tools = {
            "find_references": self.tools.get("find_references"),
            "find_in_files": self.tools.get("find_in_files"),
            "get_directory_files": self.tools.get("get_directory_files"),
        }
        
        tools_description = []
        for tool_name, tool_func in reflection_tools.items():
            if tool_func is None:
                continue
            doc = inspect.getdoc(tool_func) or "No description available"
            tools_description.append(f"- {tool_name}: {doc}")
        
        tools_description_str = "\n\n".join(tools_description)
        
        # 迭代调用工具收集信息
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Reflection iteration {iteration}/{max_iterations}")
            
            # 让 LLM 决定下一步操作
            planning_prompt = CODE_COMPLETER_PROMPTS["reflection_tool_planning"].format(
                context=context,
                tools_description=tools_description_str
            )
            
            try:
                planning_result = self.agent.invoke_with_structured_output(planning_prompt)
                
                if not planning_result.get("continue", False):
                    logger.info("LLM decided to stop tool calling")
                    break
                
                next_tool_call = planning_result.get("next_tool_call", {})
                tool_name = next_tool_call.get("tool_name")
                tool_args = next_tool_call.get("tool_args", {})
                
                if not tool_name or tool_name == "none":
                    logger.info("No tool call requested")
                    break
                
                # 执行工具调用
                logger.info(f"Calling reflection tool: {tool_name} with args: {tool_args}")
                
                try:
                    tool_call = ToolCall(tool_name=tool_name, tool_args=tool_args)
                    result = self._execute_tool(tool_call)
                    
                    # 存储工具结果（处理多次调用同一工具的情况）
                    tool_key = tool_name
                    if tool_key in context:
                        counter = 1
                        while f"{tool_name}_{counter}" in context:
                            counter += 1
                        tool_key = f"{tool_name}_{counter}"
                    
                    context[tool_key] = "tool_args: "+str(tool_args)+"\nresult: "+result
                    logger.info(f"Stored tool result in context with key: {tool_key}")
                
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    error_key = f"error_{tool_name}_{iteration}"
                    context[error_key] = f"tool_args: {str(tool_args)}\nerror: {str(e)}"

                # 生成更新后的代码
                refine_prompt = CODE_COMPLETER_PROMPTS["refine_code_from_reflection"].format(
                    context=context,
                    requirement=requirement
                )

                response = self.agent.invoke(refine_prompt)
                refined_code = extract_code_block(response, keyword="cpp")
                if not refined_code:
                    refined_code = generated_code  # 如果提取失败，使用原代码
                context["generated_code"] = refined_code

            except Exception as e:
                logger.error(f"Planning failed: {e}")
                break

        return context

    def generate_code(
        self,
        requirement: str,
        file_path: str,
        knowledge_context: str,
        test_type: str
    ) -> str:
        """
        基于需求生成代码（可选启用 Reflection）
        
        Args:
            requirement: 代码需求描述
            file_path: 目标文件路径
            knowledge_context: 上下文信息
            test_type: 测试类型，用于决定是否启用 Reflection 机制
            
        Returns:
            生成的代码字符串（如果启用 Reflection，返回改进后的代码）
        """
        prompt = CODE_COMPLETER_PROMPTS["generate_function_code"].format(
            requirement=requirement,
            context=knowledge_context
        )
        
        response = self.agent.invoke(prompt)
        code = extract_code_block(response, keyword="cpp")
        
        logger.info(f"Generated code for requirement: {requirement[:50]}...")
        
        # result = self.complete_function(file_path=file_path, code=code, edit_type="replace")

        # 如果启用 Reflection，进行反思和改进
        if test_type.endswith("rf"):
            logger.info("Starting reflection on generated code...")
            reflection_result = self.reflect_on_code(
                generated_code=code,
                requirement=requirement,
                file_path=file_path
            )
            code = reflection_result["generated_code"]

            #result = self.complete_function(file_path=file_path, code=code, edit_type="replace")
        
        return code
    
    def complete_function(self, file_path: str, code: str, edit_type: str) -> str:
        """
        将生成的代码写入文件
        
        Args:
            file_path: 目标文件路径
            code: 要写入的代码内容
            edit_type: 要补全的代码的编辑类型
        Returns:
            写入的代码内容
        """
        file_content = self._execute_tool(ToolCall(
            tool_name="read_file",
            tool_args={"file_path": file_path}
        ))
        prompt = CODE_COMPLETER_PROMPTS["complete_function"].format(
            file_path=file_path,
            file_content=file_content,
            code=code,
        )
        response = self.agent.invoke_with_structured_output(prompt)
        tool_call = ToolCall(
            tool_name="write_file",
            tool_args={"start_line": response['start_line'], "end_line": response['end_line'], "edit_type": edit_type, "file_path":file_path, "content": code}
        )
        result = self._execute_tool(tool_call)
        return result

if __name__ == "__main__":
    code = """
    void Es8388AudioCodec::EnableInput(bool enable) {
    std::lock_guard<std::mutex> lock(data_if_mutex_);
    if (enable == input_enabled_) {
        return;
    }
    if (enable) {
        esp_codec_dev_sample_info_t fs = {
            .bits_per_sample = 16,
            .channel = (uint8_t) input_channels_,
            .channel_mask = ESP_CODEC_DEV_MAKE_CHANNEL_MASK(0),
            .sample_rate = (uint32_t)input_sample_rate_,
            .mclk_multiple = 0,
        };
        if (input_reference_) {
            fs.channel_mask |= ESP_CODEC_DEV_MAKE_CHANNEL_MASK(1);
        }
        ESP_ERROR_CHECK(esp_codec_dev_open(input_dev_, &fs));
        if (input_reference_) {
            uint8_t gain = (11 << 4) + 0;
            ctrl_if_->write_reg(ctrl_if_, 0x09, 1, &gain, 1);
        }else{
            ESP_ERROR_CHECK(esp_codec_dev_set_in_gain(input_dev_, input_gain_));
        }
    } else {
        ESP_ERROR_CHECK(esp_codec_dev_close(input_dev_));
    }
    AudioCodec::EnableInput(enable);
}
    """
    code_completer = CodeCompleter()
    #测试find_references和get_symbol_definition工具的调用
    # result = code_completer._execute_tool(ToolCall(
    #     tool_name="find_references",
    #     tool_args={"file_path": "main/audio/codecs/es8388_audio_codec.cc", "line_number": 142, "selected_symbol": "EnableInput"}
    # ))
    # print(result)
    result = code_completer.generate_code(requirement="Enable the input of the audio codec", file_path="main/audio/codecs/es8388_audio_codec.cc", knowledge_context="", test_type="rf")
    print(result)