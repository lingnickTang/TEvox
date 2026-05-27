"""
知识提取 Agent

用于提取并保存代码知识，包括：
- Module Interface 知识提取
- System Design 知识提取
- Implementation Flow 实现流程分析
"""
import json
import os
import inspect
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import yaml

from src.utils import get_llm, Agent
from src.utils.log import logger
from src.core.rag.code.agents.base_agent import BaseAgent
from src.core.rag.code.tools.vscode import VSCodeClient
from src.core.rag.code.tools.file_operation_tool import (
    create_search_files_tool,
    create_read_file_tool,
    create_get_directory_files_tool,
    create_find_in_files_tool,
)
from src.core.rag.code.tools.knowledge_tool import (
    create_get_system_design_tool,
    create_get_module_interface_tool,
    create_knowledge_graph_tool,
)
from src.core.rag.code.agents.knowledge_extractor_prompt import KNOWLEDGE_EXTRACTOR_PROMPTS
from src.base import ToolCall


class SystemModule(BaseModel):
    """系统模块信息"""
    name: str
    file_paths: List[str]


class SystemDesign(BaseModel):
    """系统设计信息"""
    modules: List[SystemModule]


class KnowledgeExtractor(BaseAgent):
    """
    知识提取 Agent，负责提取并保存代码知识，包括：
    - Module Interface 模块接口知识提取
    - System Design 系统设计知识提取
    - Implementation Flow 实现流程知识提取
    """
    
    def __init__(
        self, 
        agent: Optional[Agent] = None, 
        base_url: str = "http://localhost:6789", 
        vscode_client: Optional[VSCodeClient] = None,
        model_name: str = "qwen3-coder-30b-a3b-instruct",
        module_interface_path: str = "evox-server/.rag/knowledge/module_interface.yaml"
    ):
        """
        初始化知识提取 Agent
        
        Args:
            agent: 可选的 Agent 实例，如果为 None 则创建新实例
            base_url: VSCode API 服务器地址
            vscode_client: 可选的 VSCodeClient 实例，如果为 None 则创建新实例
            model_name: 模型名称
            module_interface_path: 模块接口 YAML 文件路径
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
        self.search_files_tool = create_search_files_tool()
        
        # 注册文件操作工具
        self.register_tool("read_file", create_read_file_tool(self.vscode_client))
        self.register_tool("get_directory_files", create_get_directory_files_tool(self.vscode_client))
        self.register_tool("find_in_files", create_find_in_files_tool(self.vscode_client))
        # self.register_tool("query_knowledge_graph", create_knowledge_graph_tool())
        
        # # 注册知识检索工具
        # self.register_tool("get_module_interface", create_get_module_interface_tool(module_interface_path))
        
        # 保存路径供后续使用
        self.module_interface_path = module_interface_path
    
    def extract_module_interface(
        self, 
        module_interface_path: str = "evox-server/.rag/knowledge/module_interface.yaml",
        system_design_path: str = "evox-server/.rag/knowledge/system_design.md",
        repository_path: str = "F:/github/xiaozhi-esp32",
        hardware_type: str = "atk-dnesp32s3"
    ) -> Dict[str, Any]:
        """
        提取模块接口知识
        
        Args:
            module_interface_path: 输出的 module_interface.yaml 路径
            system_design_path: system_design.md 路径
            repository_path: 代码仓库根路径
            
        Returns:
            提取结果统计字典
        """
        # 1. 检查 module_interface.yaml 是否存在
        if os.path.exists(module_interface_path):
            logger.info(f"Module interface already exists at {module_interface_path}, skipping extraction")
            return {
                "status": "skipped",
                "reason": "already_exists",
                "path": module_interface_path
            }
        
        # 3. 确保 system_design.md 存在，如果不存在则调用 extract_system_design
        if not os.path.exists(system_design_path):
            self.extract_system_design()
        with open(system_design_path, "r", encoding="utf-8") as f:
            system_design_data = f.read()

        # 用python 获取仓库下main函数的头文件
        main_dir = os.path.join(repository_path, "main")
        header_files = []
        for root, dirs, files in os.walk(main_dir):
            for file in files:
                if file.endswith(".h"):
                    abs_path = os.path.join(root, file)
                    header_files.append(abs_path)
        logger.info(f"Found {len(header_files)} .h files under {main_dir}")

        # 用system_design_file_filter筛选一遍header_files
        prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["system_design_file_filter"].format(
            hardware_type=hardware_type,
            file_list=header_files
        )
        filtered_header_files = self.agent.invoke_with_structured_output(prompt)
        # 4. 遍历每个头文件，打开对应文件提取接口描述
        module_interfaces = {}
        for header_file in filtered_header_files:
            with open(header_file, "r", encoding="utf-8") as f:
                content = f.read()
            prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["module_interface_extraction"].format(
                headers=content
            )
            module_interface = self.agent.invoke(prompt)
            logger.info(f"Extracted module interface for header file: {header_file}")
            module_interfaces[os.path.basename(header_file)] = module_interface
        
        # 5. 保存结果
        os.makedirs(os.path.dirname(module_interface_path), exist_ok=True)
        with open(module_interface_path, 'w', encoding='utf-8') as f:
            yaml.dump(module_interfaces, f, indent=4)
        
        return {
            "status": "success",
            "header_files_count": len(header_files),
            "path": module_interface_path
        }
    
    def extract_system_design(
        self,
        system_design_path: str = "evox-server/.rag/knowledge/system_design.md",
        repository_path: str = "F:/github/xiaozhi-esp32",
        hardware_type: str = "atk-dnesp32s3"
    ) -> Dict[str, Any]:
        """
        提取系统设计知识（新版本 - 使用 VSCode 工具）
        
        Args:
            system_design_path: 输出的系统设计文档路径（Markdown 格式）
            repository_path: 代码仓库根路径
            hardware_type: 硬件类型，默认为 "atk-dnesp32s3"
            
        Returns:
            提取结果统计字典
        """
        # 1. 检查是否已存在
        if os.path.exists(system_design_path):
            logger.info(f"System design already exists at {system_design_path}")
            return {
                "status": "skipped",
                "reason": "already_exists",
                "path": system_design_path
            }
        
        # 2. 使用 Python 遍历 main 目录下所有文件并筛选出 .h 结尾的文件
        main_dir = os.path.join(repository_path, "main")
        logger.info(f"Scanning directory recursively for .h files: {main_dir}")

        header_files = []
        try:
            for root, dirs, files in os.walk(main_dir):
                for file in files:
                    if file.endswith(".h"):
                        abs_path = os.path.join(root, file)
                        header_files.append(abs_path)
            logger.info(f"Found {len(header_files)} .h files under {main_dir}")
        except Exception as e:
            logger.error(f"Failed to walk directory for .h files: {e}")
            return {
                "status": "error",
                "reason": "failed_to_scan_header_files",
                "message": str(e)
            }
        
        # 3. 使用 agent 筛选与当前硬件平台相关的头文件列表
        # 构建文件列表字符串
        file_list_str = "\n".join(header_files)
        
        # 使用 prompt 筛选文件
        filter_prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["system_design_file_filter"].format(
            hardware_type=hardware_type,
            file_list=file_list_str
        )
        
        try:
            # 使用 structured output 获取筛选后的文件列表
            header_files = self.agent.invoke_with_structured_output(
                filter_prompt
            )
            logger.info(f"Filtered {len(header_files)} header files related to {hardware_type}")
        except Exception as e:
            logger.error(f"Failed to filter files: {e}")
            return {
                "status": "error",
                "reason": "failed_to_filter_files",
                "message": str(e)
            }
        
        if not header_files:
            logger.warning("No header files found after filtering")
            return {
                "status": "error",
                "reason": "no_files_found",
                "message": "No header files found after filtering"
            }
        # 5. 使用 read_file 依次读取关键文件列表中的内容
        file_contents = []
        for header_file in header_files:
            try:
                # 确保文件路径是绝对路径
                if not os.path.isabs(header_file):
                    header_file = os.path.join(repository_path, "main", header_file)
                
                # 检查文件是否存在
                if not os.path.exists(header_file):
                    logger.warning(f"File does not exist: {header_file}")
                    continue
                
                logger.info(f"Reading file: {header_file}")
                # 直接使用 open() 读取文件内容
                with open(header_file, "r", encoding="utf-8") as f:
                    content = f.read()
                file_contents.append({
                    "file_path": header_file,
                    "content": content
                })
            except Exception as e:
                logger.warning(f"Failed to read file {header_file}: {e}")
                continue
        
        if not file_contents:
            logger.error("No files were successfully read")
            return {
                "status": "error",
                "reason": "no_files_read",
                "message": "No files were successfully read"
            }
        
        # 6. 构建文件内容字符串用于 prompt
        file_contents_str = "\n\n".join([
            f"## File: {fc['file_path']}\n```cpp\n{fc['content']}\n```"
            for fc in file_contents
        ])
        
        # 7. 使用 prompt 生成系统设计文档
        design_prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["system_design_generation"].format(
            hardware_type=hardware_type,
            file_contents=file_contents_str
        )
        try:
            system_design_markdown = self.agent.invoke(design_prompt)
            logger.info("Generated system design document")
        except Exception as e:
            logger.error(f"Failed to generate system design: {e}")
            return {
                "status": "error",
                "reason": "failed_to_generate_design",
                "message": str(e)
            }

        # 8. 保存系统设计文档
        os.makedirs(os.path.dirname(system_design_path), exist_ok=True)
        with open(system_design_path, 'w', encoding='utf-8') as f:
            f.write(system_design_markdown)
        
        return {
            "status": "success",
            "header_files_count": len(header_files),
            "read_files_count": len(file_contents),
            "path": system_design_path
        }
    
    def _find_header_file(self, input_path: str, base_path: str) -> Optional[str]:
        """
        查找同名的 .h 头文件
        
        Args:
            input_path: 输入文件路径（例如 source.cc）
            base_path: 基础路径，用于递归搜索
            
        Returns:
            头文件路径，如果未找到则返回 None
        """
        header_path = os.path.splitext(input_path)[0] + '.h'
        if os.path.exists(header_path):
            return header_path
        
        module_name = os.path.splitext(os.path.basename(input_path))[0]
        header_filename = module_name + '.h'
        
        if os.path.exists(base_path):
            for root, dirs, files in os.walk(base_path):
                if header_filename in files:
                    return os.path.join(root, header_filename)
        
        return None
    
    def extract_implementation_flow(
        self,
        requirement: str,
        implementation_flow_path: str,
        repository_path: str
    ) -> str:
        """
        提取实现流程分析
        
        Args:
            requirement: 代码实现的需求描述
            implementation_flow_path: implementation_flow.json 文件路径
            repository_path: 代码仓库根路径，用于搜索头文件
        Returns:
            实现流程分析结果字符串
        """
        
        # 尝试从缓存读取
        try:
            if os.path.exists(implementation_flow_path):
                with open(implementation_flow_path, "r", encoding="utf-8") as f:
                    cached_data = json.loads(f.read())
                if requirement in cached_data:
                    logger.info(f"Found cached implementation flow for requirement: {requirement[:50]}...")
                    return cached_data[requirement]
        except Exception as e:
            logger.warning(f"Failed to read cached implementation flow: {str(e)}")
        

        # 使用 agent 提取关键词
        prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["header_keyword_extraction"].format(
            requirement=requirement
        )
        header_keywords = self.agent.invoke(prompt).split(",")
        header_paths = []
        for keyword in header_keywords:
            # 使用 search_files_tool 搜索头文件
            header_paths.extend(self.search_files_tool(keyword=keyword, file_extensions=[".h"], search_path=repository_path, max_results=10))

        # 读取所有头文件内容
        headers_summary = []
        for header_path in header_paths:
            try:
                with open(header_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                headers_summary.append(f"## File: {header_path}\n```cpp\n{content}\n```\n")
            except Exception as e:
                logger.warning(f"Failed to read header file {header_path}: {e}")
                continue
        
        if not headers_summary:
            return "No valid header files found or readable."
        
        # 使用LLM分析实现流程
        prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["implementation_flow_analysis"].format(
            requirement=requirement,
            header_files="\n\n".join(headers_summary)
        )
        
        result = self.agent.invoke(prompt)
        logger.info(f"Extracted implementation flow for requirement: {requirement[:50]}...")
        
        # 保存到缓存
        try:
            cached_data = {}
            if os.path.exists(implementation_flow_path):
                with open(implementation_flow_path, "r", encoding="utf-8") as f:
                    cached_data = json.loads(f.read())
            cached_data[requirement] = result
            os.makedirs(os.path.dirname(implementation_flow_path), exist_ok=True)
            with open(implementation_flow_path, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save implementation flow: {str(e)}")
        
        return result
    
    def get_file_content(self, file_path: str) -> str:
        """
        获取文件内容
        """
        tool_call = ToolCall(
            tool_name="read_file",
            tool_args={"file_path": file_path}
        )
        result = self._execute_tool(tool_call)
        return result

    def generate_implementation_flow(
        self,
        filename: str,
        requirement: str,
        description: str,
        repository_path: str = "F:/github/xiaozhi-esp32",
        max_iterations: int = 5
    ) -> str:
        """
        生成实现流程分析
        
        通过迭代调用工具，收集相关信息，包括系统设计和模块接口知识，
        最终生成实现流程分析。
        
        Args:
            filename: 目标文件路径
            requirement: 需求描述
            repository_path: 代码仓库根路径
            max_iterations: 最大迭代次数，默认5次
            
        Returns:
            实现流程分析结果字符串
        """
        logger.info(f"Generating implementation flow for file: {filename}, requirement: {requirement[:50]}...")
        
        # 获取工具描述（使用 base_agent 的方法）
        tools_description = self.get_tools_description()
        # 初始化上下文
        context = {
            "target_file": filename,
            "requirement": requirement,
            "description": description,
        }
        
        # # 首先读取目标文件，了解上下文
        # try:
        #     target_content = self._execute_tool(ToolCall(
        #         tool_name="read_file",
        #         tool_args={"file_path": filename}
        #     ))
        #     context["target_file_content"] = target_content
        #     logger.info(f"Read target file: {filename}")
        # except Exception as e:
        #     logger.warning(f"Failed to read target file: {e}")
        #     target_content = f"Error reading file: {str(e)}"
        #     context["target_file_content"] = target_content
        
        # 将 system_design 知识常备到 context 中
        try:
            self.extract_system_design()
            context["system_design"] = open("evox-server/.rag/knowledge/system_design.md", "r", encoding="utf-8").read()
            logger.info("Loaded system design knowledge into context")
        except Exception as e:
            logger.warning(f"Failed to extract system design: {e}")
            context["system_design"] = f"Error extracting system design: {str(e)}"
        
        # # 将 module_interface 拥有的modules的keywords常备到 context 中
        # self.extract_module_interface()
        # with open("evox-server/.rag/knowledge/module_interface.yaml", "r", encoding="utf-8") as f:
        #     module_interface = yaml.load(f, Loader=yaml.FullLoader)
        #     context["module_interface_keywords"] = module_interface.keys()

        logger.info("Loaded module interface knowledge into context")
        # 迭代调用工具
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Implementation flow generation iteration {iteration}/{max_iterations}")
            
            # 让 LLM 根据 context 和 tools_description 决定下一步操作
            planning_prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["knowledge_collection_tool_planning"].format(
                context=context,
                tools_description=tools_description
            )
            
            try:
                planning_result = self.agent.invoke_with_structured_output(planning_prompt)
                
                if not planning_result.get("continue", False):
                    logger.info("LLM decided to stop tool calling, ready to extract knowledge")
                    break
                
                next_tool_call = planning_result.get("next_tool_call", {})
                tool_name = next_tool_call.get("tool_name")
                tool_args = next_tool_call.get("tool_args", {})
                
                if not tool_name or tool_name == "none":
                    logger.info("No tool call requested, ready to extract knowledge")
                    break
                
                # 执行工具调用
                logger.info(f"Calling tool: {tool_name} with args: {tool_args}")
                
                try:
                    tool_call = ToolCall(tool_name=tool_name, tool_args=tool_args)
                    result = self._execute_tool(tool_call)
                    
                    context[tool_name] = result
                
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    context["error"] = f"Tool {tool_name} failed: {str(e)}"
            
            except Exception as e:
                logger.error(f"Planning failed: {e}")
                # 如果规划失败，尝试直接提取知识
                break
        
        # 使用 LLM 提取实现流程知识
        extraction_prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["similar_implementation_extraction"].format(
            context=context
        )
        
        try:
            implementation_flow = self.agent.invoke(extraction_prompt)
            logger.info(f"Successfully generated implementation flow")
            return implementation_flow
        except Exception as e:
            logger.error(f"Failed to generate implementation flow: {e}")
            return f"Error generating implementation flow: {str(e)}"
    
    def generate_implementation_flow_with_tool_calls(
        self,
        filename: str,
        requirement: str,
        description: str,
        repository_path: str = "F:/github/xiaozhi-esp32",
        max_iterations: int = 5
    ) -> str:
        """
        生成实现流程分析（纯粹工具调用版本）
        
        通过迭代调用工具，收集相关信息，最终生成实现流程分析。
        仅提供 read_file 和 find_in_files 两种工具。
        
        Args:
            filename: 目标文件路径
            requirement: 需求描述
            repository_path: 代码仓库根路径
            max_iterations: 最大迭代次数，默认5次
            
        Returns:
            实现流程分析结果字符串
        """
        logger.info(f"Generating implementation flow for file: {filename}, requirement: {requirement[:50]}...")
        
        # 只提供 read_file 和 find_in_files 两种工具的描述
        available_tools = {
            "read_file": self.tools.get("read_file"),
            "find_in_files": self.tools.get("find_in_files")
        }
        
        # 构建工具描述字符串（只包含这两个工具）
        tools_description = []
        for tool_name, tool_func in available_tools.items():
            if tool_func is None:
                continue
            doc = inspect.getdoc(tool_func) or "No description available"
            tools_description.append(f"- {tool_name}: {doc}")
        
        tools_description_str = "\n\n".join(tools_description)
        
        # 初始化上下文
        context = {
            "target_file": filename,
            "requirement": requirement,
            "description": description,
            "file_content": self.get_file_content(filename),
        }
        
        # 迭代调用工具
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Implementation flow generation iteration {iteration}/{max_iterations}")
            
            # 让 LLM 根据 context 和 tools_description 决定下一步操作
            planning_prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["knowledge_collection_tool_planning"].format(
                context=context,
                tools_description=tools_description_str
            )
            
            try:
                planning_result = self.agent.invoke_with_structured_output(planning_prompt)
                
                if not planning_result.get("continue", False):
                    logger.info("LLM decided to stop tool calling, ready to extract knowledge")
                    break
                
                next_tool_call = planning_result.get("next_tool_call", {})
                tool_name = next_tool_call.get("tool_name")
                tool_args = next_tool_call.get("tool_args", {})
                
                if not tool_name or tool_name == "none":
                    logger.info("No tool call requested, ready to extract knowledge")
                    break
                
                # 只允许 read_file 和 find_in_files
                if tool_name not in ["read_file", "find_in_files"]:
                    logger.warning(f"Tool {tool_name} is not allowed, only read_file and find_in_files are available")
                    context[f"error_{iteration}"] = f"Tool {tool_name} is not allowed. Only read_file and find_in_files are available."
                    continue
                
                # 执行工具调用
                logger.info(f"Calling tool: {tool_name} with args: {tool_args}")
                
                try:
                    tool_call = ToolCall(tool_name=tool_name, tool_args=tool_args)
                    result = self._execute_tool(tool_call)
                    
                    # 简化处理：直接将 tool_name 和 result 作为 context
                    # 使用 tool_name 作为 key，如果多次调用同一工具，则追加序号
                    tool_key = tool_name
                    if tool_key in context:
                        # 如果已存在，转换为列表或追加序号
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
            
            except Exception as e:
                logger.error(f"Planning failed: {e}")
                # 如果规划失败，尝试直接提取知识
                break
        return context #直接反馈
        # 使用 LLM 提取实现流程知识
        # extraction_prompt = KNOWLEDGE_EXTRACTOR_PROMPTS["similar_implementation_extraction"].format(
        #     context=context
        # )
        
        # try:
        #     implementation_flow = self.agent.invoke(extraction_prompt)
        #     logger.info(f"Successfully generated implementation flow")
        #     return implementation_flow
        # except Exception as e:
        #     logger.error(f"Failed to generate implementation flow: {e}")
        #     return f"Error generating implementation flow: {str(e)}"

if __name__ == "__main__":
    # requirement = "Implement the InitializeKey0Button function, which initializes the key0 button of the IO expander XL9555 (not a GPIO) on the atk_dnesp32s3 board and uses it to create a counter. Each press of the button should notify the count on the screen."
    knowledge_extractor = KnowledgeExtractor()
    knowledge_extractor.generate_implementation_flow_with_tool_calls(
        filename="main/boards/atk-dnesp32s3/atk_dnesp32s3.cc",
        requirement="complete the function InitializeKey0Button()()",
        description="Implement the InitializeKey0Button function, which initializes the key0 button of the IO expander XL9555 (not a GPIO) on the atk_dnesp32s3 board and uses it to create a counter. Each press of the button should notify the count on the screen.",
        repository_path="F:/github/xiaozhi-esp32",
        max_iterations=5
    )
    # knowledge_extractor.extract_system_design()

