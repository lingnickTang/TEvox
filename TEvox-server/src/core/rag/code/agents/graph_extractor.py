"""
图知识提取 Agent

基于 SRP 的 Query 拆解 + 多路径检索：decompose（流程步骤 + 依赖模块）-> 固定多路径检索（flow/submodule 语义 + 1-hop dataflow）-> 可选 LLM 规划补充。
检索结果以节点 dict 返回，按 id 合并去重后放入 knowledge_nodes 返回给 workflow。
"""
import os
from typing import Dict, Any, Optional, List

from src.utils import get_llm, Agent
from src.base import DefaultConfig, ToolCall
from src.utils.log import logger
from src.core.rag.code.agents.base_agent import BaseAgent
from src.core.rag.code.tools.knowledge_tool import create_knowledge_graph_tool
from src.core.rag.code.agents.graph_extractor_prompt import GRAPH_EXTRACTOR_PROMPTS
from src.core.rag.code.tools.vscode import VSCodeClient


def _current_node_id(file_path: str, requirement: str) -> Optional[str]:
    """从 file_path 和 requirement 解析当前要补全的函数对应节点 id（与 knowledge_tool 内 to_ignore 解析一致）。"""
    try:
        first = os.path.basename(file_path).replace(".cc", ".h")
        last = requirement.split(" ")[-1][:-2]
        return first + ":" + last
    except Exception:
        return None


def _merge_result_nodes(context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """将各次 query_knowledge_graph 返回的 nodes 按 id 合并为单一 dict（自动去重）。"""
    merged: Dict[str, Dict[str, Any]] = {}
    for key in sorted(context.keys()):
        if not key.startswith("query_knowledge_graph_result_") or not key[len("query_knowledge_graph_result_"):].isdigit():
            continue
        val = context.get(key)
        if not isinstance(val, dict) or "nodes" not in val:
            continue
        for n in val["nodes"]:
            nid = n.get("id")
            if nid:
                merged[nid] = n
    return merged


def _reference_api_from_submodules(merged: Dict[str, Dict[str, Any]]) -> List[str]:
    """从所有 submodule 节点收集 involved_functions 作为参考 API 列表（去重保序）。"""
    api_list: List[str] = []
    seen = set()
    for n in merged.values():
        if n.get("type") != "submodule":
            continue
        for fn in n.get("involved_functions") or []:
            if fn and fn not in seen:
                seen.add(fn)
                api_list.append(fn)
    return api_list


def _format_context_summary_for_planning(context: Dict[str, Any], system_design_max_chars: int = 3000) -> str:
    """将 context 格式化为供迭代规划 prompt 使用的摘要，避免传入过长的节点 body。"""
    lines = []
    for key in ("target_file", "requirement", "description", "target_file_content", "hypothetical_code"):
        if key in context and context[key]:
            lines.append(f"{key}: {context[key]}")
    system_design = context.get("system_design") or ""
    if system_design:
        sd = system_design if len(system_design) <= system_design_max_chars else system_design[:system_design_max_chars] + "\n...(truncated)"
        lines.append(f"system_design:\n{sd}")
    current_node_id = context.get("current_node_id")
    if current_node_id:
        lines.append(f"current_node_id in the Knowledge Graph: {current_node_id}")
    for key in sorted(context.keys()):
        if not key.startswith("query_knowledge_graph_result_") or not key[len("query_knowledge_graph_result_"):].isdigit():
            continue
        val = context[key]
        if isinstance(val, dict) and "nodes" in val:
            nodes = val["nodes"]
            parts = [f"{n.get('id', '')} ({n.get('type', '')})" for n in nodes[:20]]
            if len(nodes) > 20:
                parts.append(f"... and {len(nodes) - 20} more")
            lines.append(f"{key}: {len(nodes)} nodes: " + ", ".join(parts))
        else:
            s = str(val)[:500] + ("..." if len(str(val)) > 500 else "")
            lines.append(f"{key}: (text) {s}")
    return "\n\n".join(lines) if lines else "(empty context)"


def _format_issued_queries_for_planning(context: Dict[str, Any]) -> str:
    """列出已执行的 query_knowledge_graph 参数，供 agent 判断还需检索什么。"""
    lines = []
    for key in sorted(context.keys()):
        if not key.startswith("query_knowledge_graph_params_") or not key[len("query_knowledge_graph_params_"):].isdigit():
            continue
        params = context[key]
        if not isinstance(params, dict):
            continue
        parts = [f"{k}={repr(v)}" for k, v in sorted(params.items())]
        lines.append(f"  [{key.split('_')[-1]}] " + ", ".join(parts))
    return "\n".join(lines) if lines else "  (none)"


class GraphExtractor(BaseAgent):
    """
    图知识提取 Agent：仅使用 knowledge graph 工具，在 system_design 与目标文件内容
    基础上迭代调用 query_knowledge_graph，并生成图知识摘要。
    """

    def __init__(
        self,
        agent: Optional[Agent] = None,
        kg_type: str = "SRP_KG",
        base_url: str = "http://localhost:6789",
        max_results: int = 5,
        model_name: str = "qwen3-coder-30b-a3b-instruct",
    ):
        super().__init__()
        if agent is None:
            llm = get_llm(model_name=model_name)
            self.agent = Agent(llm)
        else:
            self.agent = agent
        self.vscode_client = VSCodeClient(base_url=base_url)
        # 注册知识检索工具
        self.kg_type = kg_type
        self.register_tool("query_knowledge_graph", create_knowledge_graph_tool(kg_type=self.kg_type, max_results=max_results))
        #self.register_tool("read_file", create_read_file_tool(self.vscode_client))

        # 注册文件操作工具
        # self.register_tool("read_file", create_read_file_tool(self.vscode_client))
        # self.register_tool("get_directory_files", create_get_directory_files_tool(self.vscode_client))
        # self.register_tool("find_in_files", create_find_in_files_tool(self.vscode_client))
        
    # 使用 embedgenius 进行代码知识提取
    def collect_embedgenius(
        self,
        filename: str,
        requirement: str,
        description: str,
        system_design_path: str = "evox-server/.rag/knowledge/system_design.md",
        max_iterations: int = 5,
        repository_path: str = "F:/github/xiaozhi-esp32/",
    ) -> str:
        """
        在获取 system_design 与目标文件内容后，类比 collect_embedgenius
        进行迭代工具调用（仅 query_knowledge_graph），最后生成实现流程分析。

        Args:
            filename: 目标文件路径
            requirement: 需求描述
            system_design_path: 系统设计文档路径
            max_iterations: 最大迭代次数

        Returns:
            实现流程分析字符串
        """
        logger.info(f"Generating implementation flow for file: {filename}, requirement: {requirement[:50]}...")

        try:
            with open(repository_path+filename, "r", encoding="utf-8") as f:
                target_content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read target file: {e}")
            target_content = f"Error reading file: {str(e)}"

        system_design = ""
        try:
            if os.path.isfile(system_design_path):
                with open(system_design_path, "r", encoding="utf-8") as f:
                    system_design = f.read()
                logger.info("Loaded system design for decompose")
            else:
                logger.warning(f"System design file not found: {system_design_path}")
        except Exception as e:
            logger.warning(f"Failed to load system design: {e}")

        context: Dict[str, Any] = {
            "target_file": filename,
            "requirement": requirement,
            "description": description,
            "target_file_content": target_content,
            
        }

        # 1) Decompose：流程步骤 + 依赖模块（含 system_design 辅助）
        decompose_prompt = GRAPH_EXTRACTOR_PROMPTS["decompose"].format(
            target_file=filename,
            requirement=requirement,
            description=description,            
            # target_file_content=context["target_file_content"],
            system_design=system_design,
        )
        try:
            out = self.agent.invoke_with_structured_output(decompose_prompt)
            context["decompose"] = out
        except Exception as e:
            logger.warning(f"Decompose failed: {e}")
            context["decompose"] = {"process_steps": [], "dependency_modules": []}

        process_steps: List[Dict[str, str]] = context["decompose"].get("process_steps") or []
        dependency_modules: List[str] = context["decompose"].get("dependency_modules") or []
        result_idx = 0

        def run_query(**kwargs) -> None:
            nonlocal result_idx
            tool_args = {"file_path": filename, "requirement": requirement, **kwargs}
            try:
                result = self._execute_tool(ToolCall(tool_name="query_knowledge_graph", tool_args=tool_args))
                context[f"query_knowledge_graph_result_{result_idx}"] = result
                result_idx += 1
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                context[f"error_query_{result_idx}"] = str(e)
                result_idx += 1

        # 2) 固定多路径检索
        for i, item in enumerate(process_steps):
            retrieval = (item if isinstance(item, dict) else {}).get("retrieval") or str(item)
            if not retrieval.strip():
                continue
            logger.info(f"Fixed path flow query {i}: {retrieval[:50]}...")
            run_query(query=retrieval, node_type="flow", use_semantic=True)
        for mod in dependency_modules:
            if not (mod and str(mod).strip()):
                continue
            logger.info(f"Fixed path submodule query: {str(mod)[:50]}...")
            run_query(query=str(mod).strip(), node_type="submodule", use_semantic=True)
        current_nid = _current_node_id(filename, requirement)
        if current_nid:
            logger.info(f"Dataflow 1-hop (include_bodies): {current_nid}")
            run_query(node_id=current_nid, neighbors_only=True, include_bodies=True)

        # 3) 混合：LLM 规划补充
        tools_description = self.get_tools_description()
        remaining = max(0, max_iterations - result_idx)
        if remaining > 0:
            graph_collection_tool_planning_prompt = GRAPH_EXTRACTOR_PROMPTS["graph_collection_tool_planning"].format(
                context=context,
                tools_description=tools_description,
                tool_count=remaining,
            )
            try:
                plans = self.agent.invoke_with_structured_output(graph_collection_tool_planning_prompt).get("plans", [])
                for plan in plans:
                    if result_idx >= max_iterations:
                        break
                    tool_name = plan.get("tool_name")
                    tool_args = dict(plan.get("tool_args") or {})
                    if tool_name == "query_knowledge_graph":
                        tool_args["file_path"] = filename
                        tool_args["requirement"] = requirement
                    logger.info(f"Planning tool: {tool_name} with args: {tool_args}")
                    try:
                        result = self._execute_tool(ToolCall(tool_name=tool_name, tool_args=tool_args))
                        context[f"query_knowledge_graph_result_{result_idx}"] = result
                        result_idx += 1
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        context[f"error_{tool_name}_{result_idx}"] = str(e)
                        result_idx += 1
            except Exception as e:
                logger.warning(f"Planning failed: {e}")

        # 4) 合并节点；仅将 submodule 的 involved_functions 作为参考 API，submodule 节点本身从 knowledge_nodes 中去除
        merged = _merge_result_nodes(context)
        context["reference_api"] = _reference_api_from_submodules(merged)
        context["knowledge_nodes"] = {nid: n for nid, n in merged.items() if n.get("type") != "submodule"}
        return context

    def decompose_and_collect_graph_iterative(
        self,
        filename: str,
        requirement: str,
        description: str,
        system_design_path: str = "evox-server/.rag/knowledge/system_design.md",
        max_iterations: int = 5,
        repository_path: str = "F:/github/xiaozhi-esp32/",
    ) -> Dict[str, Any]:
        """
        基于 SRP_KG 的边检索边拆解：每轮根据当前 context 做流程/依赖分析，决定当下最需要的一次
        query_knowledge_graph 调用，执行后并入 context，直到达到次数或 LLM 停止。只返回 context。

        Args:
            filename: 目标文件路径
            requirement: 需求描述
            description: 功能描述
            system_design_path: 系统设计文档路径
            max_iterations: 最大迭代（检索）次数
            repository_path: 仓库路径（保留兼容，未使用）

        Returns:
            context: 含 knowledge_nodes, reference_api, 以及各轮 query 结果等
        """
        logger.info(f"Decompose-and-collect (iterative) for file: {filename}, requirement: {requirement[:50]}...")
        system_design = ""
        try:
            if os.path.isfile(system_design_path):
                with open(system_design_path, "r", encoding="utf-8") as f:
                    system_design = f.read()
                logger.info("Loaded system design for iterative planning")
            else:
                logger.warning(f"System design file not found: {system_design_path}")
        except Exception as e:
            logger.warning(f"Failed to load system design: {e}")

        try:
            with open(repository_path+filename, "r", encoding="utf-8") as f:
                target_content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read target file: {e}")
            target_content = f"Error reading file: {str(e)}"

        context: Dict[str, Any] = {
            "target_file": filename,
            #"target_file_content": target_content,
            "requirement": requirement,
            "description": description,
            "current_node_id": _current_node_id(filename, requirement),
            # "system_design": system_design,
        }

        # 根据当前上下文生成假设性代码
        hypothetical_prompt = GRAPH_EXTRACTOR_PROMPTS["a3_hypothetical_code"].format(
            requirement=requirement,
            description=description,
        )
        try:
            out = self.agent.invoke_with_structured_output(hypothetical_prompt)
            hypothetical_code = (out.get("code") or "").strip()
        except Exception as e:
            logger.warning(f"SRP_KG hypothetical code generation failed: {e}")
            hypothetical_code = ""

        # 线根据假设性代码进行embedding检索
        if hypothetical_code:
            try:
                result = self._execute_tool(
                    ToolCall(
                        tool_name="query_knowledge_graph",
                        tool_args={
                            "file_path": filename,
                            "requirement": requirement,
                            "query": hypothetical_code,
                            "use_semantic": True,
                            "node_type": "function",
                        },
                    )
                )
                context["hypothetical_code"] = result
            except Exception as e:
                logger.error(f"SRP_KG global query_knowledge_graph failed: {e}")
                context["error_hypothetical_code"] = str(e)
        result_idx = 0
        tools_description = self.get_tools_description()

        # 按照假设性代码进行拆解并检索

        while result_idx < max_iterations:
            remaining = max_iterations - result_idx
            context_summary = _format_context_summary_for_planning(context)
            issued_queries_summary = _format_issued_queries_for_planning(context)
            prompt = GRAPH_EXTRACTOR_PROMPTS["iterative_step_planning"].format(
                context_summary=context_summary,
                issued_queries_summary=issued_queries_summary,
                remaining_count=remaining,
                tools_description=tools_description,
            )
            try:
                plan = self.agent.invoke_with_structured_output(prompt)
            except Exception as e:
                logger.warning(f"Iterative planning failed: {e}")
                break
            if not plan.get("continue", False):
                logger.info("LLM decided to stop retrieval")
                break
            next_call = plan.get("next_tool_call") or {}
            if next_call.get("tool_name") != "query_knowledge_graph":
                logger.info("No query_knowledge_graph in plan, stopping")
                break
            tool_args = dict(next_call.get("tool_args") or {})
            tool_args["file_path"] = filename
            tool_args["requirement"] = requirement
            logger.info(f"Iterative query {result_idx}: {tool_args}")
            try:
                result = self._execute_tool(ToolCall(tool_name="query_knowledge_graph", tool_args=tool_args))
                context[f"query_knowledge_graph_result_{result_idx}"] = result
                context[f"query_knowledge_graph_params_{result_idx}"] = {
                    k: v for k, v in tool_args.items() if k not in ("file_path", "requirement")
                }
                result_idx += 1
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                context[f"error_query_{result_idx}"] = str(e)
                result_idx += 1
                break

        merged = _merge_result_nodes(context)
        context["reference_api"] = _reference_api_from_submodules(merged)
        context["knowledge_nodes"] = {nid: n for nid, n in merged.items() if n.get("type") != "submodule"}
        context["file_content"] = target_content
        return context

    def collect_a3(
        self,
        filename: str,
        requirement: str,
        description: str,
        system_design_path: str = "evox-server/.rag/knowledge/system_design.md",
        repository_path: str = "F:/github/xiaozhi-esp32/",
    ) -> Dict[str, Any]:
        """
        A3 代码知识提取：三步收集 local / global / library 内容。

        1. Local content: 用 open 直接读取目标文件（函数所在文件）。
        2. Global content: 对 query 生成假设性代码，用该代码做 embedding 检索相似代码。
        3. Library content: 读取 system_design.md。

        Returns:
            context: 含 local_content, knowledge_nodes, reference_api, library_content 等
        """
        logger.info(f"A3 collect for file: {filename}, requirement: {requirement[:50]}...")
        context: Dict[str, Any] = {
            "target_file": filename,
            "requirement": requirement,
            "description": description,
        }

        # 1) Local content: open 直接读取目标文件
        local_path = os.path.join(repository_path.rstrip(os.sep), filename.lstrip(os.sep))
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                local_content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read target file for A3 local: {e}")
            local_content = f"Error reading file: {str(e)}"
        context["local_content"] = local_content

        # 2) Global content: 生成假设性代码 -> embedding 检索
        hypothetical_prompt = GRAPH_EXTRACTOR_PROMPTS["a3_hypothetical_code"].format(
            requirement=requirement,
            description=description,
        )
        try:
            out = self.agent.invoke_with_structured_output(hypothetical_prompt)
            hypothetical_code = (out.get("code") or "").strip()
        except Exception as e:
            logger.warning(f"A3 hypothetical code generation failed: {e}")
            hypothetical_code = ""
        if hypothetical_code:
            try:
                result = self._execute_tool(
                    ToolCall(
                        tool_name="query_knowledge_graph",
                        tool_args={
                            "file_path": filename,
                            "requirement": requirement,
                            "query": hypothetical_code,
                            "use_semantic": True,
                        },
                    )
                )
                context["query_knowledge_graph_result_0"] = result
            except Exception as e:
                logger.error(f"A3 global query_knowledge_graph failed: {e}")
                context["error_query_0"] = str(e)
        # cmerged = _merge_result_nodes(context)
        # context["reference_api"] = _reference_api_from_submodules(merged)
        # context["knowledge_nodes"] = {nid: n for nid, n in merged.items() if n.get("type") != "submodule"}

        # 3) Library content: system_design.md
        library_content = ""
        try:
            if os.path.isfile(system_design_path):
                with open(system_design_path, "r", encoding="utf-8") as f:
                    library_content = f.read()
                logger.info("Loaded system_design for A3 library content")
            else:
                logger.warning(f"System design file not found: {system_design_path}")
        except Exception as e:
            logger.warning(f"Failed to load system design for A3: {e}")
        context["library_content"] = library_content

        return context

if __name__ == "__main__":
    # graph_extractor = GraphExtractor()
    # implementation_flow = graph_extractor.generate_implementation_flow(
    #     filename="main/main.cc",
    #     requirement="complete the function app_main(void)()",
    #     description="The `app_main` function serves as the entry point for the application, initializing the NVS flash storage for WiFi configuration and launching the main application instance. It handles potential NVS corruption by erasing and reinitializing the flash if necessary. Once initialized, it starts the application's main event loop, which manages core functionality such as audio processing, network communication, and device state management.",
    #     system_design_path="evox-server/.rag/knowledge/system_design.md",
    # )
    # print(implementation_flow)

    extractor = GraphExtractor(kg_type="SRP_KG", model_name="qwen3-coder-480b-a35b-instruct")
    context = extractor.decompose_and_collect_graph_iterative(
        filename="main/assets.cc",
        requirement="complete the function InitializePartition()()",
        description="The function initializes and validates an assets partition in flash memory, ensuring it exists, has sufficient space, and passes checksum verification.It maps the partition into memory and builds an index of assets with their sizesand offsets for efficient access. Returns true if the partition is successfully initialized and validated, false otherwise.",
        system_design_path="evox-server/.rag/knowledge/system_design.md",
    )
    print(context)
# 使用 context["knowledge_nodes"], context["reference_api"] 等