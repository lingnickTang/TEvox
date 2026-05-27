"""
图构建 Agent

遍历文件列表，通过 open_file 获取文件内容，按 functionality_decompose 拆成子模块，
并用 Graph 的 add_node / add_edge 构建图；文件与模块之间为 contains 关系。
"""
import json
import os
import re
from collections import deque
from typing import List, Optional, Set, Tuple

from src.base import DefaultConfig
from src.utils import Agent, get_llm, get_dashscope_embedding
from src.utils.log import logger
from src.core.rag.code.agents.graph_prompt import GRAPH_PROMPTS
from src.core.rag.code.tools.graph import Graph
from src.core.rag.code.tools.vscode import VSCodeClient
from src.core.rag.code.tools.file_operation_tool import create_read_file_tool
from src.core.rag.code.context.fileanalyze import FileAnalyzer

try:
    from src.core.rag.code.query.evaluator.cpp_quality_analyzer_by_package import (
        CppCodeAnalyzerByPackage,
    )
except ImportError:
    CppCodeAnalyzerByPackage = None  # type: ignore[misc, assignment]

# ---------- 静态评估辅助（一期：耦合/内聚/可复用，不依赖 Halstead） ----------

_CPP_KEYWORDS = frozenset({
    "auto", "break", "case", "catch", "class", "const", "constexpr", "continue",
    "default", "delete", "do", "else", "enum", "explicit", "extern", "for",
    "friend", "goto", "if", "inline", "namespace", "new", "operator", "private",
    "protected", "public", "return", "struct", "switch", "template", "this",
    "throw", "try", "typedef", "typename", "union", "virtual", "void",
    "volatile", "while", "bool", "char", "double", "float", "int", "long",
    "short", "signed", "sizeof", "static", "unsigned", "true", "false", "nullptr",
})


def _static_declaration_count(body: str) -> int:
    """
    对 C++ 头文件/片段做静态声明计数（class/struct/enum + 函数声明），纯正则，不解析 AST。
    """
    if not body or not body.strip():
        return 0
    # 移除多行与单行注释，减少误匹配
    cleaned = re.sub(r"/\*[\s\S]*?\*/", " ", body)
    cleaned = re.sub(r"//[^\n]*", "\n", cleaned)
    n_type = len(re.findall(r"\b(class|struct|enum)\s+\w+", cleaned))
    # 函数声明：标识符 ( 参数 ) 后跟 const/override/noexcept 可选，再 ; 或 {
    n_func = len(re.findall(
        r"\b\w+\s+\w+\s*\([^)]*\)\s*(const|override|noexcept)*\s*;", cleaned
    ))
    return n_type + n_func


def _static_identifier_tokens(identifier: str) -> List[str]:
    """将标识符按 CamelCase / snake_case 拆成词元（小写），用于命名一致性。"""
    if not identifier or identifier in _CPP_KEYWORDS:
        return []
    # 先按下划线拆
    parts = re.split(r"_+", identifier)
    tokens: List[str] = []
    for p in parts:
        # CamelCase: 在大写前、或“大写+小写”前切分
        sub = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|[A-Z]+", p)
        tokens.extend(s.lower() for s in sub if s)
    return [t for t in tokens if t and t not in _CPP_KEYWORDS]


def _static_naming_consistency(body: str) -> float:
    """
    基于 body 中标识符的词元集合，计算平均两两 Jaccard 相似度，作为内聚性代理。
    无标识符或仅一个返回 1.0。
    """
    ids = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", body or "")
    ids = [x for x in ids if x not in _CPP_KEYWORDS and len(x) > 1]
    if not ids:
        return 1.0
    sets_list: List[Set[str]] = []
    for i in ids:
        s = set(_static_identifier_tokens(i))
        if s:
            sets_list.append(s)
    if len(sets_list) < 2:
        return 1.0
    total = 0.0
    count = 0
    for i in range(len(sets_list)):
        for j in range(i + 1, len(sets_list)):
            a, b = sets_list[i], sets_list[j]
            inter = len(a & b)
            union = len(a | b)
            total += (inter / union) if union else 1.0
            count += 1
    return total / count if count else 1.0


class Grapher:
    """
    图构建 Agent：遍历文件 -> open_file 取内容 -> functionality_decompose 拆模块 -> 写图。
    """

    def __init__(
        self,
        base_url: str = "http://localhost:6789",
        vscode_client: Optional[VSCodeClient] = None,
        graph: Optional[Graph] = None,
    ):
        self.vscode_client = vscode_client or VSCodeClient(base_url=base_url)
        self.graph = graph if graph is not None else Graph(directed=True)
        self.read_file = create_read_file_tool(self.vscode_client)
        self.agent = Agent(get_llm(model_name=DefaultConfig.agent_model))
        self.file_analyzer = FileAnalyzer(base_url=base_url)
        self.embedding_model = get_dashscope_embedding(model=DefaultConfig.embedding_model)

    def get_function_calls(
        self,
        file_name: str,
        function_symbol: str,
        analyze_files_dir: Optional[str] = None,
    ) -> List[str]:
        """
        根据文件名称和函数 symbol，返回该函数的调用函数 symbol 列表。

        文件名称用于在 evox-server/.rag/xiaozhi/grapher/analyze_files 下查找对应 JSON；
        函数 symbol 用于在 JSON 的 outgoing_calls 下查找被调用的函数列表。

        Args:
            file_name: 文件名称或路径，如 "adc_battery_monitor.h" 或 "main/boards/common/adc_battery_monitor.h"
            function_symbol: 函数 symbol，如 "AdcBatteryMonitor(adc_unit_t, adc_channel_t, float, float, gpio_num_t)"
            analyze_files_dir: 可选，analyze_files 目录路径，默认 evox-server/.rag/xiaozhi/grapher/analyze_files

        Returns:
            被调用函数的 symbol 列表。
        """
        if analyze_files_dir is None:
            analyze_files_dir = "evox-server/.rag/xiaozhi/grapher/analyze_files"
        base = os.path.normpath(analyze_files_dir)
        name = os.path.basename(file_name.replace("\\", "/"))
        if name.endswith(".cc"):
            name = name.replace(".cc", ".h")
        if not name.endswith(".json"):
            name = name + ".json"
        json_path = os.path.join(base, name)
        if not os.path.isfile(json_path):
            logger.warning("Analyze file not found: %s", json_path)
            return []
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s: %s", json_path, e)
            return []
        functions = data.get("functions") or []
        for function_full_label in functions:
            if function_symbol in function_full_label:
                function_symbol = function_full_label
                break
        outgoing = data.get("outgoing_calls") or {}
        calls = outgoing.get(function_symbol) or []
        return [item["name"] for item in calls if isinstance(item, dict) and "name" in item]

    def get_function_labels(
        self,
        file_name: str,
        analyze_files_dir: Optional[str] = None,
    ) -> List[str]:
        """
        根据文件名索引 analyze_files 下的 JSON，返回其中的 functions 列表（function labels）。

        Args:
            file_name: 文件名称或路径，如 "adc_battery_monitor.h" 或 "main/boards/common/adc_battery_monitor.h"
            analyze_files_dir: 可选，analyze_files 目录路径，默认 evox-server/.rag/xiaozhi/grapher/analyze_files

        Returns:
            该文件对应的 functions 列表；文件不存在或解析失败时返回 []。
        """
        if analyze_files_dir is None:
            analyze_files_dir = "evox-server/.rag/xiaozhi/grapher/analyze_files"
        base = os.path.normpath(analyze_files_dir)
        name = os.path.basename(file_name.replace("\\", "/"))

        if name.endswith(".cc"):
            name = name.replace(".cc", ".h")
        if not name.endswith(".json"):
            name = name + ".json"
        json_path = os.path.join(base, name)
        if not os.path.isfile(json_path):
            logger.warning("Analyze file not found: %s", json_path)
            return []
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s: %s", json_path, e)
            return []
        return data.get("functions") or []

    def _outgoing_callee_names(self, data: dict, caller_symbol: str) -> List[str]:
        """从已加载的 analyze JSON 中取 caller_symbol 对应的被调用函数 name 列表。"""
        functions = data.get("functions") or []
        full_key = caller_symbol
        for f in functions:
            if caller_symbol in f:
                full_key = f
                break
        outgoing = data.get("outgoing_calls") or {}
        calls = outgoing.get(full_key) or []
        return [item["name"] for item in calls if isinstance(item, dict) and "name" in item]

    def build_function_call_graph_from_analyze_files(
        self,
        analyze_files_dir: Optional[str] = None,
        output_path: str = "evox-server/.rag/xiaozhi/grapher/function_call_graph.json",
    ) -> Graph:
        """
        遍历 analyze_files 下 JSON：用 functions 建函数节点，用 outgoing_calls 建 depends_on 边
        （仅当被调用方在任意 analyze 文件的 functions 中才加边）。保存为 function_call_graph.json。
        """
        if analyze_files_dir is None:
            analyze_files_dir = "evox-server/.rag/xiaozhi/grapher/analyze_files"
        base = os.path.normpath(analyze_files_dir)
        graph = Graph(directed=True)
        all_symbols = set()
        symbol_to_node_ids = {}

        for name in os.listdir(base):
            if not name.endswith(".json"):
                continue
            file_key = name[:-5]
            json_path = os.path.join(base, name)
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load %s: %s", json_path, e)
                continue
            functions = data.get("functions") or []
            for symbol in functions:
                node_id = f"{file_key}:{symbol}"
                graph.add_node(node_id, type="function", label=symbol)
                all_symbols.add(symbol)
                symbol_to_node_ids.setdefault(symbol, []).append(node_id)

        for name in os.listdir(base):
            if not name.endswith(".json"):
                continue
            file_key = name[:-5]
            json_path = os.path.join(base, name)
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            functions = data.get("functions") or []
            for caller_symbol in functions:
                caller_id = f"{file_key}:{caller_symbol}"
                for callee_symbol in self._outgoing_callee_names(data, caller_symbol):
                    if callee_symbol not in all_symbols:
                        continue
                    for callee_id in symbol_to_node_ids.get(callee_symbol, []):
                        graph.add_edge(caller_id, callee_id, edge_type="depends_on")

        graph.to_json(output_path)
        return graph

    def build_merged_graph(
        self,
        file_decomposed_path: str = "evox-server/.rag/xiaozhi/grapher/file_decomposed_graph_with_dependencies.json",
        function_flow_path: str = "evox-server/.rag/xiaozhi/grapher/function_flow_graph_full.json",
        function_call_graph_path: str = "evox-server/.rag/xiaozhi/grapher/function_call_graph.json",
        output_path: Optional[str] = None,
    ) -> Graph:
        """
        合并 file_decomposed、function_flow、function_call 三图：
        - 以 function_call 为函数节点与 depends_on(function→function) 来源；
        - 从 file_decomposed 加 file/submodule 及 submodule→function 的 contains；
        - 从 function_flow 加 flow 节点，function→flow 为 contains，flow→function 为 depends_on；
        - function_flow 中函数 id 为 func:文件名:symbol，用 label 与 function_call 的节点按 symbol 合并。
        """
        g_call = Graph.from_json(function_call_graph_path)
        g_decomposed = Graph.from_json(file_decomposed_path)
        g_flow = Graph.from_json(function_flow_path)
        G = Graph(directed=True)

        symbol_to_node_ids = {}
        for nid in g_call.nodes():
            node = g_call.get_node(nid)
            symbol = (node or {}).get("label") or nid.split(":", 1)[-1]
            symbol_to_node_ids.setdefault(symbol, []).append(nid)
        for nid in g_call.nodes():
            node = g_call.get_node(nid)
            attrs = {k: v for k, v in (node or {}).items() if k not in ("id", "type")}
            G.add_node(nid, type="function", **attrs)
        for u, v in g_call.edges():
            G.add_edge(u, v, edge_type="depends_on")

        for nid in g_decomposed.nodes():
            node = g_decomposed.get_node(nid)
            attrs = {k: v for k, v in (node or {}).items() if k != "id"}
            G.add_node(nid, **attrs)
        for u, v in g_decomposed.edges():
            edge_data = g_decomposed.get_edge(u, v) or {}
            G.add_edge(u, v, **edge_data)
        for nid in g_decomposed.nodes():
            node = g_decomposed.get_node(nid)
            if node is None or node.get("type") != "submodule":
                continue
            for func_symbol in node.get("involved_functions") or []:
                for func_id in symbol_to_node_ids.get(func_symbol, []):
                    G.add_edge(nid, func_id, edge_type="contains")

        def flow_func_id_to_canonical(flow_id: str) -> Optional[str]:
            if not flow_id.startswith("func:"):
                return None
            parts = flow_id.split(":", 2)
            if len(parts) < 3:
                return None
            _, filename, symbol = parts
            base = os.path.splitext(filename)[0]
            for cand in symbol_to_node_ids.get(symbol, []):
                if cand.startswith(base + ".") or cand.startswith(base + ":"):
                    return cand
            return symbol_to_node_ids.get(symbol, [None])[0]

        flow_func_to_canonical = {}
        for nid in g_flow.nodes():
            node = g_flow.get_node(nid)
            if node is None:
                continue
            if node.get("label"):
                canonical = flow_func_id_to_canonical(nid)
                flow_func_to_canonical[nid] = canonical
                if canonical and not G.has_node(canonical):
                    G.add_node(canonical, type="function", label=node.get("label"))
                continue
            attrs = {k: v for k, v in (node or {}).items() if k not in ("id", "type")}
            G.add_node(nid, type="flow", **attrs)
        for u, v in g_flow.edges():
            canon_u = flow_func_to_canonical.get(u, u)
            if canon_u and G.has_node(canon_u):
                G.add_edge(canon_u, v, edge_type="contains")
        for nid in g_flow.nodes():
            node = g_flow.get_node(nid)
            if node is None or node.get("label"):
                continue
            for func_symbol in node.get("involved_functions") or []:
                for func_id in symbol_to_node_ids.get(func_symbol, []):
                    G.add_edge(nid, func_id, edge_type="depends_on")

        if output_path:
            G.to_json(output_path)
        return G

    def _make_json_serializable(self, obj):
        """Recursively convert dataclass/asdict output for JSON: Enum -> name, set -> list."""
        from enum import Enum

        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._make_json_serializable(x) for x in obj]
        if isinstance(obj, set):
            return [self._make_json_serializable(x) for x in obj]
        if isinstance(obj, Enum):
            return obj.name
        return obj

    def get_all_analyze_files(self, file_paths: List[str]):
        import os
        import json
        from dataclasses import asdict

        for fp in file_paths:
            fp = fp.replace('\\', '/')
            # if fp != "main/led/led.h":
            #     continue
            try:
                logger.info(f"Analyzing file {fp}")
                result = self.file_analyzer.analyze_file(fp)
                logger.info(f"Analyzed file {fp} result: {result}")
                if result:
                    file_name = os.path.basename(fp)
                    result_dict = asdict(result)
                    serializable = self._make_json_serializable(result_dict)
                    with open(f"evox-server/.rag/xiaozhi/grapher/analyze_files/{file_name}.json", "w", encoding="utf-8") as f:
                        json.dump(serializable, f, ensure_ascii=False, indent=4)
            except Exception as e:
                logger.error(f"Error analyzing file {fp}: {e}")
                continue

    def build_graph(
        self,
        file_paths: List[str],
        base_path: str = "",
    ) -> Graph:
        """
        遍历 file_paths，用 open_file 读内容，按 functionality_decompose 拆模块，
        调用 add_node / add_edge 构建图；文件 -> 模块 为 contains 边。

        Args:
            file_paths: 待处理文件路径列表。
            base_path: 文件路径前缀。

        Returns:
            构建后的 Graph 实例。
        """
        prompt_tpl = GRAPH_PROMPTS["functionality_decompose"]

        for fp in file_paths:
            # content = self.read_file(fp)
            # if not content:

            with open(base_path + fp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            labels = self.get_function_labels(  fp)
            functions_label_str = "\n".join("- " + (x or "") for x in labels) if labels else "(none)"
            prompt = prompt_tpl.format(
                file_content=content,
                functions_label=functions_label_str,
            )
            try:
                out = self.agent.invoke_with_structured_output(prompt)
            except Exception as e:
                logger.warning("Error invoking agent: %s", e)
                continue
            raw = out.get("nodes")
            nodes = raw if isinstance(raw, list) else []
            self.graph.add_node(fp, label=fp)

            for n in nodes:
                # id增加上文件名称的前缀
                nid = f"{fp}:{n.get("id")}"
                if not nid:
                    continue
                body = n.get("code") or ""
                involved_functions = n.get("involved_functions") or []
                self.graph.add_node(nid, body=body, involved_functions=involved_functions)
                self.graph.add_edge(fp, nid, edge_type="contains")

            logger.info("Processed %s: %d sub-modules", fp, len(nodes))

        return self.graph

    def compare_file_vs_submodules(
        self,
        file_content: str,
        submodules: List[dict],
        file_path: Optional[str] = None,
    ) -> dict:
        """
        比较「整文件」与「其对应 submodule」的静态代码指标（拆解前 vs 拆解后）。

        Args:
            file_content: 拆解前的整文件内容。
            submodules: 该文件拆解出的子模块列表，每项需含 "id" 及 "body" 或 "code"。
            file_path: 可选，文件路径或标识，传入后 Lizard 结果中显示该名而非 temp.cpp。

        Returns:
            dict: file_metrics（整文件指标）、submodule_metrics（各 submodule 指标）、
                  aggregate（各 submodule 指标的均值等聚合），用于说明高内聚。
        """
        if CppCodeAnalyzerByPackage is None:
            raise ImportError("需要安装 lizard 并确保 cpp_quality_analyzer_by_package 可导入")
        analyzer = CppCodeAnalyzerByPackage()

        def _metrics_to_dict(m) -> dict:
            return {
                "avg_cyclomatic_complexity": m.avg_cyclomatic_complexity,
                "halstead_volume": m.halstead_volume,
                "halstead_effort": m.halstead_effort,
                "halstead_difficulty": m.halstead_difficulty,
                "lines_of_code": m.lines_of_code,
                "function_count": m.function_count,
                "comment_density": m.comment_density,
                "avg_function_length": m.avg_function_length,
                "has_errors": m.has_errors,
            }

        file_metrics = analyzer.analyze_code_quality(
            file_content, source_name=file_path
        )
        submodule_metrics: List[dict] = []
        for i, sub in enumerate(submodules):
            body = sub.get("body") or sub.get("code") or ""
            sid = sub.get("id") or f"submodule_{i}"
            try:
                m = analyzer.analyze_code_quality(body, source_name=sid)
                submodule_metrics.append({"id": sid, "metrics": _metrics_to_dict(m)})
            except Exception as e:
                logger.warning("Submodule %s 分析失败: %s", sid, e)
                submodule_metrics.append(
                    {"id": sid, "metrics": None, "error": str(e)}
                )

        aggregate: dict = {}
        if submodule_metrics:
            valid = [x["metrics"] for x in submodule_metrics if x.get("metrics")]
            if valid:
                aggregate = {
                    "mean_avg_cyclomatic_complexity": sum(
                        v["avg_cyclomatic_complexity"] for v in valid
                    ) / len(valid),
                    "mean_function_count": sum(v["function_count"] for v in valid)
                    / len(valid),
                    "mean_lines_of_code": sum(v["lines_of_code"] for v in valid)
                    / len(valid),
                    "mean_halstead_difficulty": sum(v["halstead_difficulty"] for v in valid)
                    / len(valid),
                }

        return {
            "file_metrics": _metrics_to_dict(file_metrics),
            "submodule_metrics": submodule_metrics,
            "aggregate": aggregate,
        }

    def run_file_vs_submodules_comparison_for_merged_graph(
        self,
        merged_graph_path: str = "evox-server/.rag/xiaozhi/grapher/merged_graph_with_body.json",
        output_path: str = "evox-server/.rag/xiaozhi/grapher/file_vs_submodules_metrics.json",
    ) -> List[dict]:
        """
        遍历 merged_graph_with_body 中所有 type=file 的节点及其 submodule（contains 后继），
        对每个文件调用 compare_file_vs_submodules，将全部结果写入 output_path 的 JSON 文件。

        Args:
            merged_graph_path: merged_graph_with_body.json 路径。
            output_path: 结果 JSON 保存路径。

        Returns:
            所有文件的比较结果列表，每项为 {"file": file_id, "result": compare_result}。
        """
        graph = Graph.from_json(merged_graph_path)
        results: List[dict] = []
        for node_id in graph.nodes():
            node = graph.get_node(node_id)
            if node is None or node.get("type") != "file":
                continue
            file_content = node.get("body") or ""
            file_path = node.get("label") or node_id
            submodule_ids = [
                s
                for s in graph.successors(node_id)
                if (graph.get_node(s) or {}).get("type") == "submodule"
                and (graph.get_edge(node_id, s) or {}).get("edge_type") == "contains"
            ]
            submodules = [
                {"id": sid, "body": (graph.get_node(sid) or {}).get("body", "")}
                for sid in submodule_ids
            ]
            try:
                result = self.compare_file_vs_submodules(
                    file_content, submodules, file_path=file_path
                )
                results.append({"file": node_id, "result": result})
                logger.info("Compared file %s: %d submodules", node_id, len(submodules))
            except Exception as e:
                logger.warning("Compare failed for file %s: %s", node_id, e)
                results.append({"file": node_id, "error": str(e), "result": None})
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info("Saved %d file comparison results to %s", len(results), output_path)
        return results

    def compare_function_vs_flows(
        self,
        function_body: str,
        flows: List[dict],
        function_id: Optional[str] = None,
    ) -> dict:
        """
        比较「整函数」与「其拆解出的 flow」的 Halstead/圈复杂度等指标（拆解前 vs 拆解后）。
        function 有完整实现体，flow 为代码片段，适合用 Lizard 分析。

        Args:
            function_body: 拆解前的整函数体（C++ 代码）。
            flows: 该函数拆解出的 flow 列表，每项需含 "id" 及 "body" 或 "code"。
            function_id: 可选，函数节点 id 或 label，供 Lizard 结果标识。

        Returns:
            dict: function_metrics（整函数指标）、flow_metrics（各 flow 指标）、aggregate（均值等）。
        """
        if CppCodeAnalyzerByPackage is None:
            raise ImportError("需要安装 lizard 并确保 cpp_quality_analyzer_by_package 可导入")
        analyzer = CppCodeAnalyzerByPackage()

        def _metrics_to_dict(m) -> dict:
            return {
                "avg_cyclomatic_complexity": m.avg_cyclomatic_complexity,
                "halstead_volume": m.halstead_volume,
                "halstead_effort": m.halstead_effort,
                "halstead_difficulty": m.halstead_difficulty,
                "lines_of_code": m.lines_of_code,
                "function_count": m.function_count,
                "comment_density": m.comment_density,
                "avg_function_length": m.avg_function_length,
                "has_errors": m.has_errors,
            }

        function_metrics = analyzer.analyze_code_quality(
            function_body, source_name=function_id
        )
        flow_metrics: List[dict] = []
        for i, fl in enumerate(flows):
            body = fl.get("body") or fl.get("code") or ""
            fid = fl.get("id") or f"flow_{i}"
            try:
                m = analyzer.analyze_code_quality(body, source_name=fid)
                flow_metrics.append({"id": fid, "metrics": _metrics_to_dict(m)})
            except Exception as e:
                logger.warning("Flow %s 分析失败: %s", fid, e)
                flow_metrics.append({"id": fid, "metrics": None, "error": str(e)})

        aggregate: dict = {}
        if flow_metrics:
            valid = [x["metrics"] for x in flow_metrics if x.get("metrics")]
            if valid:
                aggregate = {
                    "mean_avg_cyclomatic_complexity": round(
                        sum(v["avg_cyclomatic_complexity"] for v in valid) / len(valid), 4
                    ),
                    "mean_function_count": round(
                        sum(v["function_count"] for v in valid) / len(valid), 2
                    ),
                    "mean_lines_of_code": round(
                        sum(v["lines_of_code"] for v in valid) / len(valid), 2
                    ),
                    "mean_halstead_volume": round(
                        sum(v["halstead_volume"] for v in valid) / len(valid), 2
                    ),
                    "mean_halstead_difficulty": round(
                        sum(v["halstead_difficulty"] for v in valid) / len(valid), 4
                    ),
                    "mean_halstead_effort": round(
                        sum(v["halstead_effort"] for v in valid) / len(valid), 2
                    ),
                }

        return {
            "function_metrics": _metrics_to_dict(function_metrics),
            "flow_metrics": flow_metrics,
            "aggregate": aggregate,
        }

    def run_function_vs_flows_comparison_for_merged_graph(
        self,
        merged_graph_path: str = "evox-server/.rag/xiaozhi/grapher/merged_graph_with_body.json",
        output_path: str = "evox-server/.rag/xiaozhi/grapher/function_vs_flows_metrics.json",
    ) -> List[dict]:
        """
        遍历 merged_graph_with_body 中所有 type=function 的节点及其 flow（contains 后继），
        对每个 function 调用 compare_function_vs_flows（Halstead 等），将全部结果写入 output_path 的 JSON。
        """
        graph = Graph.from_json(merged_graph_path)
        results: List[dict] = []
        for node_id in graph.nodes():
            node = graph.get_node(node_id)
            if node is None or node.get("type") != "function":
                continue
            function_body = node.get("body") or ""
            function_label = node.get("label") or node_id
            flow_ids = [
                s
                for s in graph.successors(node_id)
                if (graph.get_node(s) or {}).get("type") == "flow"
                and (graph.get_edge(node_id, s) or {}).get("edge_type") == "contains"
            ]
            flows = [
                {"id": fid, "body": (graph.get_node(fid) or {}).get("body", "")}
                for fid in flow_ids
            ]
            try:
                result = self.compare_function_vs_flows(
                    function_body, flows, function_id=node_id
                )
                results.append({"function": node_id, "result": result})
                logger.info(
                    "Compared function %s: %d flows",
                    node_id,
                    len(flows),
                )
            except Exception as e:
                logger.warning("Compare failed for function %s: %s", node_id, e)
                results.append({"function": node_id, "error": str(e), "result": None})
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(
            "Saved %d function-vs-flows comparison results to %s",
            len(results),
            output_path,
        )
        return results

    def compute_static_decomposition_metrics(
        self,
        graph: Graph,
        file_node_id: str,
    ) -> dict:
        """
        对单个 file 与其 submodules 做一期静态指标：耦合(Ca/Ce/Instability)、
        内聚(声明数/命名一致性)、可复用(粒度/Ce)，支持 file vs submodules 对比。
        完全基于图与 body 文本，不调用 Lizard/Halstead。
        """
        node = graph.get_node(file_node_id)
        if node is None or node.get("type") != "file":
            return {"file": file_node_id, "error": "not a file node", "before": None, "after_submodules": [], "after_aggregate": None}
        file_body = node.get("body") or ""
        submodule_ids = [
            s
            for s in graph.successors(file_node_id)
            if (graph.get_node(s) or {}).get("type") == "submodule"
            and (graph.get_edge(file_node_id, s) or {}).get("edge_type") == "contains"
        ]
        sub_set = set(submodule_ids)

        # ---------- before: 整文件视为一个模块 ----------
        before = {
            "declaration_count": _static_declaration_count(file_body),
            "naming_consistency": _static_naming_consistency(file_body),
            "module_count": 1,
            "api_count": _static_declaration_count(file_body),
        }

        # ---------- after: 每个 submodule 的耦合(Ca/Ce/Instability)、内聚、可复用 ----------
        after_submodules: List[dict] = []
        for sid in submodule_ids:
            sub_node = graph.get_node(sid) or {}
            body = sub_node.get("body") or ""
            involved = sub_node.get("involved_functions") or []
            # 仅统计本文件内 submodule 之间的 depends_on
            ca = sum(
                1
                for u in sub_set
                if u != sid and graph.has_edge(u, sid) and (graph.get_edge(u, sid) or {}).get("edge_type") == "depends_on"
            )
            ce = sum(
                1
                for v in sub_set
                if v != sid and graph.has_edge(sid, v) and (graph.get_edge(sid, v) or {}).get("edge_type") == "depends_on"
            )
            instability = ce / (ca + ce) if (ca + ce) > 0 else 0.0
            after_submodules.append({
                "submodule_id": sid,
                "Ca": ca,
                "Ce": ce,
                "Instability": round(instability, 4),
                "declaration_count": _static_declaration_count(body),
                "involved_functions_count": len(involved),
                "naming_consistency": round(_static_naming_consistency(body), 4),
            })

        # ---------- after 聚合（与 before 对比用） ----------
        if not after_submodules:
            after_aggregate = None
        else:
            n = len(after_submodules)
            after_aggregate = {
                "submodule_count": n,
                "mean_Ca": round(sum(x["Ca"] for x in after_submodules) / n, 4),
                "mean_Ce": round(sum(x["Ce"] for x in after_submodules) / n, 4),
                "mean_Instability": round(sum(x["Instability"] for x in after_submodules) / n, 4),
                "mean_declaration_count": round(sum(x["declaration_count"] for x in after_submodules) / n, 2),
                "mean_involved_functions_count": round(sum(x["involved_functions_count"] for x in after_submodules) / n, 2),
                "mean_naming_consistency": round(sum(x["naming_consistency"] for x in after_submodules) / n, 4),
            }

        return {
            "file": file_node_id,
            "before": before,
            "after_submodules": after_submodules,
            "after_aggregate": after_aggregate,
        }

    def run_static_decomposition_metrics_for_merged_graph(
        self,
        merged_graph_path: str = "evox-server/.rag/xiaozhi/grapher/merged_graph_with_body.json",
        output_path: str = "evox-server/.rag/xiaozhi/grapher/static_decomposition_metrics.json",
    ) -> List[dict]:
        """
        遍历 merged_graph_with_body 中所有 file 节点，对每个 file 计算一期静态指标
        （before: file 整体；after: 各 submodule + 聚合），并写入 JSON。
        """
        graph = Graph.from_json(merged_graph_path)
        results: List[dict] = []
        for node_id in graph.nodes():
            node = graph.get_node(node_id)
            if node is None or node.get("type") != "file":
                continue
            rec = self.compute_static_decomposition_metrics(graph, node_id)
            results.append(rec)
            logger.info(
                "Static metrics for %s: before decl=%s, after submodules=%d",
                node_id,
                rec.get("before", {}).get("declaration_count"),
                len(rec.get("after_submodules", [])),
            )
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info("Saved static decomposition metrics for %d files to %s", len(results), output_path)
        return results

    def build_function_flow_graph(
        self,
        jsonl_path: str = "evox-server/.rag/xiaozhi/grapher/functions_bodies.jsonl",
    ) -> Graph:
        """
        从 functions_bodies.jsonl 读取函数，用 function_flow_decompose 拆解为 flow，
        构建 function -> flow 的图；函数与 flow 为 contains 边。

        Args:
            jsonl_path: functions_bodies.jsonl 路径。

        Returns:
            构建后的 Graph 实例。
        """
        prompt_tpl = GRAPH_PROMPTS["function_flow_decompose"]
        path = os.path.normpath(jsonl_path)
        if not os.path.isfile(path):
            logger.warning("functions_bodies.jsonl not found: %s", path)
            return self.graph

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            i = 0
            for line in f:
                i += 1
                if i > 5:
                    exit(0)
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning("Skip invalid jsonl line: %s", e)
                    continue
                func_id = row.get("graph_node_id") or row.get("id")
                symbol = row.get("symbolName", "")
                body = row.get("functionBody", "")
                if not func_id:
                    continue
                outgoing_labels = self.get_function_calls(row.get("filepath"), symbol)
                prompt = prompt_tpl.format(function_name=symbol, function_body=body, outgoing_functions_label=outgoing_labels)
                try:
                    out = self.agent.invoke_with_structured_output(prompt)
                    raw = out.get("nodes")
                except Exception as e:
                    logger.warning("Error invoking agent: %s", e)
                    continue
                nodes = raw if isinstance(raw, list) else []
                self.graph.add_node(func_id, label=symbol)
                for n in nodes:
                    nid = n.get("id")
                    if not nid:
                        continue
                    flow_id = f"{func_id}::{nid}"
                    code = n.get("code") or ""
                    involved_functions = n.get("involved_functions") or []
                    self.graph.add_node(flow_id, body=code, involved_functions=involved_functions)
                    self.graph.add_edge(func_id, flow_id, edge_type="contains")
                logger.info("Processed %s: %d flows", func_id, len(nodes))
        return self.graph

    # 对于functions中的每个function，查找submodules中involved_functions包含该function的submodule，返回所有这些submodule的列表
    def depend_submodule(self, functions: List[str], submodules: List)->List:
        relevant_submodules = []
        for function in functions:
            for submodule in submodules:
                involved_functions = submodule.get("involved_functions") or []
                if function in involved_functions and submodule not in relevant_submodules:
                    relevant_submodules.append(submodule)
        
        return relevant_submodules
        
    def flow_depend_on(self, function_flow_graph: Graph) -> None:
        # 遍历 function_flow_graph 的节点：有 label 的为 function，否则为 flow；nodes() 返回节点 ID
        for node_id in function_flow_graph.nodes():
            node = function_flow_graph.get_node(node_id)
            if node is None:
                continue
            if node.get("label"):
                function_flow_graph.add_node(node_id, type="function")
            else:
                function_flow_graph.add_node(node_id, type="flow")

    def combine_graph(self, file_decomposed_graph: Graph, function_flow_graph: Graph) -> Graph:
        """
        合并文件分解图和函数流图
        """
        # 遍历file_decomposed_graph的节点，若包含label表明为文件，增加属性为file,否则为submodule    
        pass


    def module_depend_on(self, file_decomposed_graph: Graph) -> Graph:
        """
        合并文件分解图和函数流图
        """
        # 遍历 file_decomposed_graph 的节点：有 label 的为文件，否则为 submodule；将 submodule 加入列表
        # nodes() 返回节点 ID（str），需用 get_node(node_id) 获取节点属性
        submodules = []
        for node_id in file_decomposed_graph.nodes():
            node = file_decomposed_graph.get_node(node_id)
            if node is None:
                continue
            if node.get("label"):
                file_decomposed_graph.add_node(node_id, type="file")
            else:
                file_decomposed_graph.add_node(node_id, type="submodule")
                submodules.append({**node, "id": node_id})
        
        # 构建 module 间依赖：对每个文件节点，取其后继 submodule，根据 involved_functions 的调用关系加边
        # successors() 返回后继节点 ID 列表（str），需用 get_node 取属性
        for node_id in file_decomposed_graph.nodes():
            node = file_decomposed_graph.get_node(node_id)
            if node is None or node.get("type") != "file":
                continue
            submodule_ids = file_decomposed_graph.successors(node_id)
            for submodule_id in submodule_ids:
                submodule_data = file_decomposed_graph.get_node(submodule_id)
                if submodule_data is None:
                    continue
                involved_functions = submodule_data.get("involved_functions") or []
                for func in involved_functions:
                    outgoing_functions = self.get_function_calls(node_id, func)
                    relevant_submodules = self.depend_submodule(outgoing_functions, submodules)
                    for relevant_submodule in relevant_submodules:
                        if submodule_id != relevant_submodule.get("id"):
                            file_decomposed_graph.add_edge(submodule_id, relevant_submodule.get("id"), edge_type="depends_on")
        
        return file_decomposed_graph

    # 从file_decomposed_graph_with_dependencies中，选择两个文件，将这两个文件的子模块间的depends_on关系进行列出；
    def get_depends_on_relationships(self, file_decomposed_graph: Graph, file1_id: str, file2_id: str) -> List[str]:
        """
        从file_decomposed_graph_with_dependencies中，选择两个文件，将这两个文件的子模块间的depends_on关系进行列出；
        """
        # 遍历file_decomposed_graph的节点，若包含label表明为文件，增加属性为file,否则为submodule
        file1_node = None
        file2_node = None
        for node_id in file_decomposed_graph.nodes():
            node = file_decomposed_graph.get_node(node_id)
            label = node.get("label")
            if node is None:
                continue
            if label == file1_id:
                file1_node = node
            elif label == file2_id:
                file2_node = node
        if file1_node is None or file2_node is None:
            return []
        depends_on_relationships = []
        # 对任意的两个不同submodule，如果有一个depends_on的边，那么增加对应的关系
        submodule1_ids = file_decomposed_graph.successors(file1_node.get("label"))
        submodule2_ids = file_decomposed_graph.successors(file2_node.get("label"))
        outgoing_edge = False
        incoming_edge = False
        for submodule1_id in submodule1_ids:
            for submodule2_id in submodule2_ids:
                if submodule1_id == submodule2_id:
                    continue
                if file_decomposed_graph.has_edge(submodule1_id, submodule2_id):
                    depends_on_relationships.append(f"{submodule1_id} -> {submodule2_id}")
                    outgoing_edge = True
                if file_decomposed_graph.has_edge(submodule2_id, submodule1_id):
                    depends_on_relationships.append(f"{submodule2_id} -> {submodule1_id}")
                    incoming_edge = True


        return depends_on_relationships
    def add_knowledge_body(self, merged_graph: Graph, base_path: str = "") -> Graph:
        """
        将 merged_graph 中的 body 属性添加到 knowledge_graph 中
        """
        # 读取evox-server\.rag\xiaozhi\grapher\functions_bodies.jsonl作为备用
        function_body_dict = {}
        with open("evox-server/.rag/xiaozhi/grapher/functions_bodies.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                function_body = data.get("functionBody")
                function_symbol = data.get("symbolName")
                function_body_dict[function_symbol] = function_body
        # 遍历 merged_graph中的节点
        # 对于其中type为file的节点，读取 base_path+label 下的文件作为该节点的body
        # 对于type为function的节点，遍历func根据其label找到具有相同symbolName的function_body
        for node_id in merged_graph.nodes():
            node = merged_graph.get_node(node_id)
            if node is None:
                continue
            updated_node = {**node}
            if node.get("type") == "file":
                with open(base_path + node.get("label"), "r", encoding="utf-8") as f:
                    body = f.read()
                    updated_node["body"] = body
            elif node.get("type") == "function":
                function_symbol = node.get("label")
                function_body = function_body_dict.get(function_symbol)
                updated_node["body"] = function_body
            merged_graph.add_node(node_id, **updated_node)
        return merged_graph
    
    def get_embedding(self, body: str) -> list:
        """
        根据body获取embedding list
        """
        embedding = self.embedding_model.embed_query(body)
        return embedding

    def construct_embedding_knowledge_graph(self, merged_graph_with_body: Graph, output_path: str = "evox-server/.rag/xiaozhi/grapher/graph_embedding.json") -> dict:
        # 遍历merged_graph_with_body中的节点，获取其中的节点的body
        # 根据body获取embedding，存储在graph_embedding.json中
        graph_embedding = {}
        for node_id in merged_graph_with_body.nodes():
            node = merged_graph_with_body.get_node(node_id)
            if node is None:
                continue
            body = node.get("body")
            if body is None:
                continue
            embedding = self.get_embedding(body)
            graph_embedding[node_id] = embedding

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(graph_embedding, f, ensure_ascii=False, indent=4)
        return graph_embedding

def show_part_graph(
    merged_graph_path: str = "evox-server/.rag/xiaozhi/grapher/merged_graph.json",
    seed_node: Optional[str] = None,
    file_id: Optional[str] = None,
    depth: int = 4,
    max_nodes: int = 120,
    target_files: int = 2,
    target_submodules: int = 3,
    target_functions: int = 5,
    target_flows: int = 9,
) -> None:
    """
    从 merged_graph.json 加载图，用文本绘图方式打印节点与边。
    若指定 file_id：仅包含该文件、其 submodule、submodule 对应的 function、function 对应的 flow 及它们之间的边。
    否则按 seed 与深度 BFS，并按类型目标数量补足节点，分组打印 contains、depends_on 等关系。

    Args:
        merged_graph_path: merged_graph.json 路径。
        seed_node: 子图起点（file_id 为 None 时有效）；为 None 时取第一个根节点或第一个节点。
        file_id: 指定一个文件节点 id；非 None 时仅展示该文件及其 submodule -> function -> flow 链。
        depth: BFS 最大深度（file_id 为 None 时有效）。
        max_nodes: 子图最大节点数（file_id 为 None 时有效）。
        target_files: 至少包含的 file 节点数（file_id 为 None 时有效）。
        target_submodules: 至少包含的 submodule 节点数。
        target_functions: 至少包含的 function 节点数。
        target_flows: 至少包含的 flow 节点数。
    """
    G = Graph.from_json(merged_graph_path)
    if G.node_count() == 0:
        print("图为空。")
        return

    def node_type(nid: str) -> str:
        return (G.get_node(nid) or {}).get("type", "?")

    def edge_type(u: str, v: str) -> str:
        return (G.get_edge(u, v) or {}).get("edge_type", "?")

    sub_nodes: Set[str] = set()

    if file_id is not None:
        if not G.has_node(file_id):
            print("文件节点不在图中: %s" % file_id)
            return
        if node_type(file_id) != "file":
            print("指定节点不是 file 类型: %s (type=%s)" % (file_id, node_type(file_id)))
            return
        sub_nodes.add(file_id)
        for s in G.successors(file_id):
            if edge_type(file_id, s) == "contains" and node_type(s) == "submodule":
                sub_nodes.add(s)
        submodules = [n for n in sub_nodes if node_type(n) == "submodule"]
        for sm in submodules:
            for s in G.successors(sm):
                if edge_type(sm, s) == "contains" and node_type(s) == "function":
                    sub_nodes.add(s)
        functions = [n for n in sub_nodes if node_type(n) == "function"]
        for fn in functions:
            for s in G.successors(fn):
                if edge_type(fn, s) == "contains" and node_type(s) == "flow":
                    sub_nodes.add(s)
        seed_node = file_id
    else:
        if seed_node is None:
            roots = G.roots()
            seed_node = roots[0] if roots else next(iter(G.nodes()))
        if not G.has_node(seed_node):
            print("种子节点不在图中: %s" % seed_node)
            return
        q: deque = deque([(seed_node, 0)])
        while q and len(sub_nodes) < max_nodes:
            n, d = q.popleft()
            if n in sub_nodes or d > depth:
                continue
            sub_nodes.add(n)
            for succ in G.successors(n):
                if len(sub_nodes) >= max_nodes:
                    break
                if succ not in sub_nodes:
                    q.append((succ, d + 1))
        by_type: dict = {"file": [], "submodule": [], "function": [], "flow": []}
        for nid in G.nodes():
            t = node_type(nid)
            if t in by_type and nid not in sub_nodes:
                by_type[t].append(nid)
        for t, ids in by_type.items():
            need = (
                target_files if t == "file" else
                target_submodules if t == "submodule" else
                target_functions if t == "function" else
                target_flows
            )
            current = sum(1 for n in sub_nodes if node_type(n) == t)
            for nid in ids:
                if current >= need:
                    break
                if nid not in sub_nodes:
                    sub_nodes.add(nid)
                    current += 1

    def short(s: str, w: int = 62) -> str:
        return (s[: w - 3] + "...") if len(s) > w else s

    n_file = sum(1 for n in sub_nodes if node_type(n) == "file")
    n_sub = sum(1 for n in sub_nodes if node_type(n) == "submodule")
    n_func = sum(1 for n in sub_nodes if node_type(n) == "function")
    n_flow = sum(1 for n in sub_nodes if node_type(n) == "flow")

    print("=" * 70)
    if file_id is not None:
        print("子图 [按文件]: %s" % file_id)
    print("子图: %d 个节点 (file=%d, submodule=%d, function=%d, flow=%d)" % (len(sub_nodes), n_file, n_sub, n_func, n_flow))
    print("=" * 70)
    print("\n--- 节点 (按类型) ---\n")
    for t in ("file", "submodule", "function", "flow"):
        ids = sorted(n for n in sub_nodes if node_type(n) == t)
        if not ids:
            continue
        print("  [%s] (%d 个)" % (t, len(ids)))
        for nid in ids:
            node = G.get_node(nid)
            label = (node or {}).get("label", "")
            body = (node or {}).get("body", "")
            if label:
                desc = short(str(label), 58)
            else:
                desc = short(str(body), 58) if body else "(无 label/body)"
            print("    [%s]  %s" % (short(nid, 55), desc))
        print()
    print("--- 边 (全部) ---\n")
    edge_list = [(u, v, (G.get_edge(u, v) or {}).get("edge_type", "?")) for u, v in G.edges() if u in sub_nodes and v in sub_nodes]
    for u, v, et in edge_list:
        print("  %s  -->  %s  [%s]" % (short(u, 45), short(v, 45), et))
    print("\n(共 %d 条边)\n" % len(edge_list))
    print("--- 边按关系类型 (contains / depends_on 等) ---\n")
    by_edge_type: dict = {}
    for u, v in G.edges():
        if u not in sub_nodes or v not in sub_nodes:
            continue
        et = (G.get_edge(u, v) or {}).get("edge_type", "?")
        by_edge_type.setdefault(et, []).append((u, v))
    for et in sorted(by_edge_type.keys()):
        pairs = by_edge_type[et]
        print("  [%s] (%d 条)" % (et, len(pairs)))
        for u, v in pairs:
            print("    %s  -->  %s" % (short(u, 48), short(v, 48)))
        print()
    print("--- 从种子出发的树状视图 (depth=%d) ---\n" % depth)
    visited: Set[str] = set()

    def tree_lines(nid: str, indent: int, d: int) -> None:
        if d > depth or nid in visited:
            return
        visited.add(nid)
        node = G.get_node(nid)
        t = (node or {}).get("type", "?")
        prefix = "  " * indent
        print("%s%s  [%s]" % (prefix, short(nid, 60), t))
        for s in G.successors(nid):
            if s not in visited and s in sub_nodes:
                edge = G.get_edge(nid, s) or {}
                et = edge.get("edge_type", "?")
                print("%s  -> %s  [%s]" % (prefix + "  ", short(s, 52), et))
                tree_lines(s, indent + 1, d + 1)

    tree_lines(seed_node, 0, 0)
    print("\n" + "=" * 70)

def header_file_list():
    """
    读取 header_files_list.txt，返回其中的文件路径列表
    """
    header_file_paths = []
    with open("evox-server/src/core/rag/code/header_files_list.txt", "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            file_path = stripped.split(":", 1)[0]
            if file_path and file_path not in header_file_paths:
                header_file_paths.append(file_path)
    return header_file_paths

def source_file_list():
    """
    读取 source_files_list.txt，返回其中的文件路径列表
    """
    source_file_paths = []
    with open("evox-server/src/core/rag/code/source_files_list.txt", "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            file_path = stripped.split(":", 1)[0]
            if file_path and file_path not in source_file_paths:
                source_file_paths.append(file_path)
    return source_file_paths


def extract_file_function_kg(
    merged_graph_path: str,
    output_path: Optional[str] = None,
) -> Graph:
    """
    从 merged_graph_with_body.json 中提取 file 与 function 的关联，构建一张基础的 KG 知识图谱。

    - 节点仅保留 file、function 两类；file -> function 的 contains 由原图 file->submodule->function 推断。
    - function 之间的关联由原图上的 function -> depends_on 构成。
    - 节点属性保留 type、label、body。

    Args:
        merged_graph_path: merged_graph_with_body.json 的路径。
        output_path: 可选，KG 导出 JSON 的路径；若指定则保存时输出节点数与边数。

    Returns:
        构建好的 Graph 实例（有向图）。
    """
    from pathlib import Path

    G = Graph.from_json(merged_graph_path)
    kg = Graph(directed=True)

    def node_type(nid: str) -> str:
        return (G.get_node(nid) or {}).get("type", "?")

    # 只保留 file、function 节点，属性含 type、label、body
    for nid in G.nodes():
        t = node_type(nid)
        if t not in ("file", "function"):
            continue
        attrs = G.get_node(nid) or {}
        keep = {k: v for k, v in attrs.items() if k in ("type", "label", "body")}
        kg.add_node(nid, **keep)

    # 由原图 file->submodule->function 推断 file->function（contains）
    submodule_to_file: dict = {}
    for u, v in G.edges():
        edge_attrs = G.get_edge(u, v) or {}
        if edge_attrs.get("edge_type") != "contains":
            continue
        tu, tv = node_type(u), node_type(v)
        if tu == "file" and tv == "submodule":
            submodule_to_file[v] = u
    for u, v in G.edges():
        edge_attrs = G.get_edge(u, v) or {}
        if edge_attrs.get("edge_type") != "contains":
            continue
        tu, tv = node_type(u), node_type(v)
        if tu == "submodule" and tv == "function" and kg.has_node(v):
            file_id = submodule_to_file.get(u)
            if file_id is not None and kg.has_node(file_id):
                kg.add_edge(file_id, v, edge_type="contains")

    # function -> function（depends_on）
    for u, v in G.edges():
        if not kg.has_node(u) or not kg.has_node(v):
            continue
        edge_attrs = G.get_edge(u, v) or {}
        if edge_attrs.get("edge_type") == "depends_on":
            if node_type(u) == "function" and node_type(v) == "function":
                kg.add_edge(u, v, edge_type="depends_on")

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        kg.to_json(output_path)
        n_nodes = kg.node_count()
        n_edges = kg.edge_count()
        logger.info(
            "File-function KG exported to %s: nodes=%d, edges=%d",
            output_path,
            n_nodes,
            n_edges,
        )
        print("File-function KG: nodes=%d, edges=%d -> %s" % (n_nodes, n_edges, output_path))
    return kg


def build_file_decomposed_graph(grapher: Grapher, base_path: str = ""):
    """
    构建文件分解图
    """
    header_file_paths = header_file_list()
    graph = grapher.build_graph(header_file_paths, base_path=base_path)
    graph.to_json("evox-server/.rag/xiaozhi/grapher/file_decomposed_graph.json")

def build_function_flow_graph(grapher: Grapher, base_path: str = ""):
    """
    构建函数流图
    """
    function_flow_graph = grapher.build_function_flow_graph("evox-server/.rag/xiaozhi/grapher/functions_bodies.jsonl")
    function_flow_graph.to_json("evox-server/.rag/xiaozhi/grapher/function_flow_graph_test.json")

if __name__ == "__main__":
    # grapher = Grapher()
    # merged_path = "evox-server/.rag/xiaozhi/grapher/merged_graph_with_body.json"
    # # 1) 一期静态评估：file vs submodules（耦合/内聚/可复用）
    # static_results = grapher.run_static_decomposition_metrics_for_merged_graph(
    #     merged_graph_path=merged_path,
    #     output_path="evox-server/.rag/xiaozhi/grapher/static_decomposition_metrics.json",
    # )
    # print("Static decomposition metrics for %d files -> static_decomposition_metrics.json" % len(static_results))
    # # 2) function vs flows：Halstead/圈复杂度等（需 lizard）
    # func_flow_results = grapher.run_function_vs_flows_comparison_for_merged_graph(
    #     merged_graph_path=merged_path,
    #     output_path="evox-server/.rag/xiaozhi/grapher/function_vs_flows_metrics.json",
    # )
    # print("Function vs flows (Halstead) for %d functions -> function_vs_flows_metrics.json" % len(func_flow_results))
    # kg = extract_file_function_kg(
    #     merged_graph_path="evox-server/.rag/xiaozhi/grapher/merged_graph_with_body.json",
    #     output_path="evox-server/.rag/xiaozhi/grapher/file_function_kg.json",
    # )
    grapher = Grapher()
    grapher.construct_embedding_knowledge_graph(
        merged_graph_with_body=Graph.from_json("evox-server/.rag/xiaozhi/grapher/KG.json"),
        output_path="evox-server/.rag/xiaozhi/grapher/KG_embedding.json",
    )
