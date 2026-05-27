import yaml
import json
import random
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.core.rag.code.agents.knowledge_extractor import KnowledgeExtractor
from src.core.rag.code.agents.code_completer import CodeCompleter
from src.core.rag.code.agents.debugger import DebuggerAgent
from src.core.rag.code.agents.evaluator import EvaluatorAgent
from src.core.rag.code.tools.vscode import VSCodeClient
from src.core.rag.code.tools.knowledge_tool import reset_graph_cache
from src.utils.log import logger
from src.core.rag.code.agents.base_agent import BaseAgent
from src.core.rag.code.agents.graph_extractor import GraphExtractor

def get_benchmark_yaml_filename(file_path: str) -> str:
    """
    根据 file_path 获取对应的 benchmark yaml 文件名
    
    Args:
        file_path: 文件路径，如 "main/boards/common/i2c_device.cc"
        
    Returns:
        yaml 文件名，如 "i2c_device.yaml"
    """
    # 从文件路径提取文件名（不含扩展名）
    # 例如: main/boards/common/i2c_device.cc -> i2c_device
    path_obj = Path(file_path)
    filename_without_ext = path_obj.stem
    return f"{filename_without_ext}.yaml"


def clear_function_body(
    vscode_client: VSCodeClient,
    file_path: str,
    start_line: int,
    end_line: int
) -> str:
    """
    清空函数体：将 start_line+1 到 end_line-1 的内容替换为空白
    
    Args:
        vscode_client: VSCode 客户端实例
        file_path: 文件路径
        start_line: 起始行号
        end_line: 结束行号
        
    Returns:
        操作结果
    """
    logger.info(f"Clearing function body in {file_path} from line {start_line+1} to {end_line-1}")
    
    # 计算要替换的行范围
    actual_start = start_line + 1
    actual_end = end_line - 1
    
    # 如果 start_line+1 > end_line-1，则不需要清空
    if actual_start > actual_end:
        logger.warning(f"Invalid range: start_line+1 ({actual_start}) > end_line-1 ({actual_end})")
        return "No content to clear"
    
    # 使用空字符串替换指定范围的内容
    return vscode_client.write_file(
        file_path=file_path,
        content="",
        start_line=actual_start,
        end_line=actual_end,
        edit_type="replace"
    )

def restore_workspace(vscode_client: VSCodeClient):
    """
    使用 git stash 恢复工作区
    使用 vscode_client.close_all_open_text_documents() 关闭所有打开的文件
    
    Args:
        vscode_client: VSCode 客户端实例
        
    """
    logger.info("Restoring workspace with git stash")
    
    # 执行 git stash 来恢复现场
    # 注意：这里使用 executeCommandInTerminal，你可能需要根据实际情况选择
    # executeCommandInEspIdfTerminal 或 executeCommandInPioTerminal
    result = vscode_client.executeCommandInTerminal("git stash")
    logger.info(f"Git stash result: {result}")
    reset_graph_cache()
    # 关闭所有文件
    result = vscode_client.close_all_open_text_documents()
    logger.info(f"Close all open text documents result: {result}")

def run_agents_for_query(
    query_item: Dict[str, Any],
    knowledge_extractor: KnowledgeExtractor,
    code_completer: CodeCompleter,
    evaluator: EvaluatorAgent,
    vscode_client: VSCodeClient,
    graph_extractor: GraphExtractor,
    benchmark_dir: str = "evox-server/.rag/benchmark/functions_all",
    test_type: str = "workflow",
    enable_debugger: bool = True,
) -> Dict[str, Any]:
    """
    为单个 query 运行所有 agents
    
    Args:
        query_item: 包含 query, file_path, start_line, end_line 的字典
        knowledge_extractor: 知识提取器实例
        code_completer: 代码补全器实例
        evaluator: 评估器实例
        vscode_client: VSCode 客户端实例
        benchmark_dir: benchmark 文件目录
        test_type: 测试类型
    Returns:
        运行结果字典
    """
    query = query_item.get("query", "")
    description = query_item.get("description", "")
    file_path = query_item.get("file_path", "")
    start_line = query_item.get("start_line")
    end_line = query_item.get("end_line")
    
    logger.info(f"Processing query: {query}")
    logger.info(f"File path: {file_path}, Lines: {start_line}-{end_line}")
    
    results = {
        "query": query,
        "description": description,
        "file_path": file_path,
        "knowledge_extraction": None,
        "code_generation": None,
        "debugging": None,
        "evaluation": None,
        "timing": {},
    }
    
    try:
        # 1. 恢复工作区
        restore_workspace(vscode_client)
        
        # 2. 清空函数体
        clear_function_body(vscode_client, file_path, start_line, end_line)
        
        # 3. 加载对应的 benchmark yaml 文件
        benchmark_filename = get_benchmark_yaml_filename(file_path)
        benchmark_file_path = Path(benchmark_dir) / benchmark_filename
        
        if not benchmark_file_path.exists():
            logger.warning(f"Benchmark file not found: {benchmark_file_path}")
            results["error"] = f"Benchmark file not found: {benchmark_filename}"
            return results
        
        # 加载 benchmark yaml 文件（新格式：字典格式，包含顶层的 file_path 和 benchmark 列表）
        with open(benchmark_file_path, 'r', encoding='utf-8') as f:
            benchmark_data = yaml.safe_load(f)
        
        # 4. 运行 Knowledge Extractor
        knowledge_context = ""
        start_time = time.time()
        if test_type.startswith("workflow"):
            logger.info("Running Knowledge Extractor...")
            knowledge_context = knowledge_extractor.generate_implementation_flow(
                filename=file_path,
                requirement=query,
                description=description,
                repository_path="F:/github/xiaozhi-esp32",
                max_iterations=5
            )
        elif test_type.startswith("tools"):
            knowledge_context = knowledge_extractor.generate_implementation_flow_with_tool_calls(
                filename=file_path,
                requirement=query,
                description=description,
                repository_path="F:/github/xiaozhi-esp32",
                max_iterations=5
            )
        elif test_type.startswith("local"): #进获取文件内容
            knowledge_context = knowledge_extractor.get_file_content(file_path) + "\n" + description
        elif test_type.startswith("SRP"):
            knowledge_context = graph_extractor.decompose_and_collect_graph_iterative(
                filename=file_path,
                requirement=query,
                description=description,
                repository_path="F:/github/xiaozhi-esp32/",
                max_iterations=5
            )
        elif test_type.startswith("without"):
            knowledge_context = description
        elif test_type.startswith("a3"):
            knowledge_context = graph_extractor.collect_a3(
                filename=file_path,
                requirement=query,
                description=description,
                repository_path="F:/github/xiaozhi-esp32/",
            )
        elif test_type.startswith("eg"):
            knowledge_context = graph_extractor.collect_embedgenius(
                filename=file_path,
                requirement=query,
                description=description,
                repository_path="F:/github/xiaozhi-esp32/",
            )
        results["knowledge_extraction"] = knowledge_context
        results["timing"]["knowledge_extraction"] = time.time() - start_time
    

        # 5. 运行 Code Completer
        logger.info("Running Code Completer...")
        start_time = time.time()
        generated_code = code_completer.generate_code(
            requirement=query,
            file_path=file_path,
            knowledge_context=knowledge_context,
            test_type=test_type
        )
        results["code_generation"] = generated_code
        results["timing"]["code_generation"] = time.time() - start_time
        
        # 6. 运行 Debugger（可选）
        final_code = generated_code
        if "workflow" in test_type and enable_debugger:
            logger.info("Running Debugger...")
            start_time = time.time()
            debug_result = debugger.iterative_build_and_fix(
                file_to_fix=file_path,
                task_description=query,
            )
            results["debugging"] = debug_result
            results["timing"]["debugging"] = time.time() - start_time

            # 获取 debugger 返回的最终代码（函数体）
            final_code = debug_result.get("final_code", generated_code)
        else:
            results["timing"]["debugging"] = 0.0
        
        # 7. 将 final_code 保存到 yaml 文件中
        if final_code:
            logger.info(f"Saving final_code to {benchmark_filename}")
            try:
                # 从顶层获取 benchmark 列表
                benchmark_list = benchmark_data.get("benchmark", [])
                
                # 找到匹配的 item 并更新 workflow 字段（只通过 query 匹配）
                found = False
                for item in benchmark_list:
                    if item.get("query") == query:
                        item[test_type] = final_code
                        logger.info(f"Updated {test_type} field for query: {query}")
                        found = True
                        break
                
                if not found:
                    logger.warning(f"No matching item found for query: {query}")
                
                # 保存回 YAML 文件（保持字典结构）
                benchmark_data["benchmark"] = benchmark_list
                with open(benchmark_file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(benchmark_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                logger.info(f"Successfully saved {test_type} to {benchmark_filename}")
            except Exception as e:
                logger.error(f"Failed to save {test_type} to yaml file: {e}")
        else:
            logger.warning(f"No final_code to save for query: {query}")
        
        # 8. 运行 Evaluator
        logger.info("Running Evaluator...")
        start_time = time.time()
        # 评估器从 yaml 文件中读取 test_type 字段进行评估
        evaluation_result = evaluator.evaluate_single_query(
            query=query,
            benchmark_filename=benchmark_filename,
            test_type=test_type
        )
        results["evaluation"] = evaluation_result
        results["timing"]["evaluation"] = time.time() - start_time

        # 恢复工作区
        restore_workspace(vscode_client)
        
    except Exception as e:
        logger.error(f"Error processing query {query}: {e}")
        results["error"] = str(e)
    
    return results

def get_token_stats(agents: List[BaseAgent]) -> Dict[str, Any]:
    stats = {}
    for agent in agents:
        if hasattr(agent, 'agent') and hasattr(agent.agent, 'get_token_stats'):
            stats[agent.__class__.__name__] = agent.agent.get_token_stats()
    return stats

def main(test_type):
    """主函数：遍历 function_complement.yaml 中的所有 query"""
    big_model_name = "qwen3-coder-480b-a35b-instruct"
    small_model_name = "qwen3-coder-30b-a3b-instruct"
    if "small" in test_type:
        model_name = small_model_name
    else:
        model_name = big_model_name
    # 配置路径
    YAML_BENCHMARK_PATH = "evox-server/.rag/benchmark/function_complement.yaml"
    BENCHMARK_DIR = "evox-server/.rag/benchmark/functions_all"
    TEST_TYPE = test_type
    ENABLE_DEBUGGER = False
    ignore_list = [
        "main/application.cc",
        "main/mcp_server.cc",
        "main/audio/audio_service.cc",
        "main/boards/common/esp32_camera.cc",
        "main/boards/echoear/EchoEar.cc",
        "main/boards/m5stack-tab5/m5stack_tab5.cc",
        "main/boards/otto-robot/otto_controller.cc",
        "main/boards/otto-robot/otto_movements.cc",
        "main/boards/sensecap-watcher/sensecap_watcher.cc",
        "main/boards/sensecap-watcher/sscma_camera.cc",
        "main/boards/taiji-pi-s3/taiji_pi_s3.cc",
        "main/display/emote_display.cc",
        "main/display/lcd_display.cc"
    ]

    # 初始化 VSCode 客户端
    vscode_client = VSCodeClient(base_url="http://localhost:6789")
    
    # 实例化 agents（传入共享的 vscode_client）
    logger.info("Initializing agents...")
    knowledge_extractor = KnowledgeExtractor(vscode_client=vscode_client, model_name=model_name)
    code_completer = CodeCompleter(vscode_client=vscode_client, model_name=model_name)
    debugger = DebuggerAgent(vscode_client=vscode_client)
    if TEST_TYPE.startswith("SRP"): # KG
        graph_extractor = GraphExtractor(kg_type="SRP_KG", model_name=model_name)
    else:
        graph_extractor = GraphExtractor(kg_type="KG", model_name=model_name)
    evaluator = EvaluatorAgent(benchmark_dir=BENCHMARK_DIR)
    
    # 读取 benchmark 文件
    logger.info(f"Loading benchmark file: {YAML_BENCHMARK_PATH}")
    with open(YAML_BENCHMARK_PATH, 'r', encoding='utf-8') as f:
        benchmark = yaml.safe_load(f)
    
    test_cases = benchmark.get("benchmark", [])
    logger.info(f"Found {len(test_cases)} test cases")
    
    # 遍历每个 query
    all_results = []
    final_test_cases = []
    final_test_cases_example = []
    final_test_cases_96 = []
    final_test_cases_10 = []
    final_test_cases_168 = []
    # 筛选对应的 cases
    for idx, test_case in enumerate(test_cases):
        if test_case['query'] == "complete the function Assets()()":
            final_test_cases_example.append(test_case)

        # ground truth 需要超过20行
        start_line = test_case.get("start_line", 0)
        end_line = test_case.get("end_line", 0)
        if end_line - start_line >= 20:
            final_test_cases_96.append(test_case)

        # 去除ignore list中的部分
        if test_case['file_path'] not in ignore_list:
            final_test_cases_168.append(test_case)
            
    random.seed(42)  # 设置随机种子保证每次随机结果一致
    final_test_cases_10 = random.sample(final_test_cases_96, 10)

    if "96" in TEST_TYPE:
        final_test_cases = final_test_cases_96
    elif "168" in TEST_TYPE:
        final_test_cases = final_test_cases_168
    elif "10" in TEST_TYPE:
        final_test_cases = final_test_cases_10
    else:
        final_test_cases = final_test_cases_example

    logger.info(f"Found {len(final_test_cases)} test cases")

        # 保存所有结果，包括统计信息
    import datetime
    date = datetime.datetime.now().strftime("%m_%d_%H_%M")
    output_file = Path(f"evox-server/.rag/benchmark/{TEST_TYPE}_results_{date}.json")

    for idx, test_case in enumerate(final_test_cases):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing test case {idx + 1}/{len(final_test_cases)}")
        logger.info(f"{'='*60}")
        
        result = run_agents_for_query(
            query_item=test_case,
            knowledge_extractor=knowledge_extractor,
            code_completer=code_completer,
            evaluator=evaluator,
            vscode_client=vscode_client,
            graph_extractor=graph_extractor,
            benchmark_dir=BENCHMARK_DIR,
            test_type=TEST_TYPE,
            enable_debugger=ENABLE_DEBUGGER,
        )
        
        all_results.append(result)
        
        # 输出当前测试用例的时间统计
        timing = result.get("timing", {})
        if timing:
            logger.info(f"Timing for test case {idx + 1}:")
            for module, duration in timing.items():
                logger.info(f"  {module}: {duration:.2f} seconds")
        
        logger.info(f"Completed test case {idx + 1}")
    
    # 汇总时间统计
    # 把使用的模型名称也统计进去
    total_timing = {
        "knowledge_extraction": 0.0,
        "code_generation": 0.0,
        "debugging": 0.0,
        "evaluation": 0.0
    }
    
    for result in all_results:
        timing = result.get("timing", {})
        for module in total_timing.keys():
            total_timing[module] += timing.get(module, 0.0)
    
    # 计算平均时间统计
    average_timing = {}
    for module, total_time in total_timing.items():
        average_timing[module] = total_time / len(all_results) if all_results else 0.0
    
    logger.info(f"\n{'='*60}")
    logger.info("Total Timing Statistics:")
    logger.info(f"{'='*60}")
    for module, total_time in total_timing.items():
        avg_time = average_timing[module]
        logger.info(f"{module}:")
        logger.info(f"  Total: {total_time:.2f} seconds")
        logger.info(f"  Average: {avg_time:.2f} seconds")
    logger.info(f"{'='*60}")
    
    token_stats = get_token_stats([knowledge_extractor, code_completer, debugger, evaluator, graph_extractor])
    logger.info(f"Total token stats: {token_stats}")
    
    # 构建包含统计信息的输出数据
    output_data = {
        "metadata": {
            "test_type": TEST_TYPE,
            "date": date,
            "model_name": model_name
        },
        "statistics": {
            "timing": {
                "total": total_timing,
                "average": average_timing
            },
            "tokens": token_stats,
            "total_test_cases": len(all_results)
        },
        "results": all_results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\nAll results saved to: {output_file}")
    logger.info(f"Total test cases processed: {len(all_results)}")

    from winotify import Notification

    toast = Notification(
        app_id="evox-server",
        title="workflow.py",
        msg="运行已完成",
        duration="long"
    )
    toast.show()

if __name__ == "__main__":
    last_run_test_type = None
    test_file = Path("evox-server/src/core/rag/code/workflow_tests.txt")

    while True:
        
        if not test_file.exists():
            time.sleep(10)
            logger.warning(f"Test file not found: {test_file}")
            continue

        with open(test_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        # 从后往前遍历lines
        idx = -1
        for i, line in enumerate(lines):
            if last_run_test_type == line:
                idx = i
                break
        # 根据last_run_test_type匹配
        if idx+1 == len(lines):
            time.sleep(10)
            continue
        next_line = lines[idx+1]
        if next_line[-1] != ";":
            time.sleep(10)
            logger.warning(f"Line {next_line} does not end with ;")
            continue
        else:
            if next_line == "exit;":
                break
            logger.info(f"Running test_type: {next_line}")
            last_run_test_type = next_line
            try:
                main(next_line)
            except Exception as e:
                logger.error(f"Error running test_type {next_line}: {e}")
                time.sleep(10)
                continue
            

    # output_file = Path(f"evox-server/.rag/benchmark/functions_all/main.yaml")
    # with open(output_file, 'r', encoding='utf-8') as f:
    #     data = yaml.safe_load(f)
    # print("data:", data["benchmark"][0]["workflow"])
    # data["benchmark"][0]["workflow"] = "hello world"
    # with open(output_file, 'w', encoding='utf-8') as f:
    #     yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

