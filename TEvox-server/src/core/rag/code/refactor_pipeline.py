# evox-server/src/core/rag/code/refactor_pipeline.py

import json
import os
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import yaml
from typing import Dict, Any, List, Optional, Tuple

from src.core.rag.code.index.designer import Designer
from src.core.rag.code.repair import Repairer
from src.core.rag.code.PATH import STATUS_JSON_PATH, DEPENDENCY_JSON_PATH, BASE_PATH, GRAPH_JSON_DIR

def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _strip_file_prefix(path: str) -> str:
    return path[5:] if path.startswith("file:") else path


def _derive_output_path(relative_path: str) -> Path:
    file_name = Path(relative_path).name
    return OUTPUT_DIR / f"{file_name}.json"


def _read_source_code(relative_path: str) -> Optional[str]:
    full_path = BASE_PATH / relative_path
    if not full_path.exists():
        print(f"✗ 未找到源文件: {full_path}")
        return None
    try:
        return full_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"✗ 读取源文件失败: {full_path}，原因: {exc}")
        return None


def _update_status_refactored(status_list: List[Dict[str, Any]], target_paths: List[str]) -> None:
    target_set = set(target_paths)
    for item in status_list:
        if item.get("path") in target_set:
            item["refactored"] = True


def _build_in_scope_list(status_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in status_list if item.get("in_refactor_scope")]


def _build_fanout(dependency_data: Dict[str, Any], in_scope_paths: set) -> Dict[str, List[str]]:
    edges = dependency_data.get("edges", {})
    fanout: Dict[str, List[str]] = defaultdict(list)
    for raw_source, raw_targets in edges.items():
        source = _strip_file_prefix(raw_source)
        if source not in in_scope_paths:
            continue
        for raw_target in raw_targets:
            target = _strip_file_prefix(raw_target)
            if target in in_scope_paths:
                fanout[source].append(target)
    return fanout

def get_reference_interfaces(relative_path: str) -> str:
    """
    根据 relative_path 从 file_dependencies.json 获取依赖节点列表，
    然后从对应的 graph JSON 文件中读取所有 type=header 的节点，
    并将它们返回。
    
    Args:
        relative_path: 相对路径，例如 "main/application.cc"
        
    Returns:
        格式字符串，包含所有依赖的 header 节点
    """    
    dependency_data = _load_json(DEPENDENCY_JSON_PATH)
    edges = dependency_data.get("edges", {})
    
    dependencies = edges.get(relative_path, [])
    if not dependencies or dependencies == []:
        return ""
    
    header_nodes = []
    for dep_path in dependencies:
        # 从依赖路径中提取 module_name（去掉扩展名）
        module_name = Path(dep_path).stem
        
        # 检查 GRAPH_JSON_DIR/module_name.json 是否存在
        graph_json_path = GRAPH_JSON_DIR / f"{module_name}.json"
        
        if not graph_json_path.exists():
            continue
            
        graph_data = _load_json(graph_json_path)
        nodes = graph_data.get("nodes", [])
        for node in nodes:
            if node.get("type") == "header":
                header_nodes.append(node)
    return header_nodes


def _designer_task(
    designer: Designer,
    relative_path: str,
) -> None:
    code = _read_source_code(relative_path)

    module_name = Path(relative_path).stem
    header_content = designer.find_header_file(str(BASE_PATH / relative_path), str(BASE_PATH))
    reference_interfaces = get_reference_interfaces(relative_path)
    graph_dict = designer.code_to_graph_simple(
        code=code,
        name=module_name,
        header=header_content,
        reference_interfaces=reference_interfaces
    )
    designer.graph_manager.update(GRAPH_JSON_DIR / f"{module_name}.json", graph_dict)

def _repair_task(
    repairer: Repairer,
    relative_path: str,
) -> None:
    code = _read_source_code(relative_path)
    module_name = Path(relative_path).stem
    repairer.simple_repair_flow(relative_path)

def _propagate_dependencies(
    designer: Designer,
    fanout: Dict[str, List[str]],
    queue: deque,
) -> Dict[str, Any]:
    propagation_stats = {
        "evaluated": 0,
        "refactored": 0,
        "errors": [],
    }

    while queue:
        cur = queue.popleft()
        cur_output = _derive_output_path(cur)
        if not cur_output.exists():
            propagation_stats["errors"].append(f"缺少重构结果文件: {cur_output}")
            continue

        try:
            cur_graph = _load_json(cur_output)
        except Exception as exc:
            propagation_stats["errors"].append(f"读取重构结果失败: {cur_output}，原因: {exc}")
            continue

        for child in fanout.get(cur, []):
            child_output = _derive_output_path(child)
            if not child_output.exists():
                propagation_stats["errors"].append(f"缺少下游重构文件: {child_output}")
                continue

            try:
                child_graph = _load_json(child_output)
            except Exception as exc:
                propagation_stats["errors"].append(f"读取下游重构文件失败: {child_output}，原因: {exc}")
                continue

            propagation_stats["evaluated"] += 1
            try:
                need_refactor, updated_graph = designer.should_refactor_based_on_dependency(
                    cur_graph=cur_graph,
                    dependent_graph=child_graph,
                    current_file=cur,
                    dependent_file=child,
                )
            except Exception as exc:
                propagation_stats["errors"].append(
                    f"依赖传播判定失败: {cur} -> {child}，原因: {exc}"
                )
                continue

            if not need_refactor:
                continue

            try:
                _save_json(child_output, updated_graph)
            except Exception as exc:
                propagation_stats["errors"].append(f"更新下游重构文件失败: {child_output}，原因: {exc}")
                continue

            propagation_stats["refactored"] += 1
            if child not in queue:
                queue.append(child)

    return propagation_stats

def simple_pipeline() -> Dict[str, Any]:
    """
    基于 file_status.json 与 graph_json_path 执行重构与传播流程。
    """
    start_time = time.time()

    status_list: List[Dict[str, Any]] = _load_json(STATUS_JSON_PATH)

    # 1. 从状态列表中筛选出重构范围的文件
    refactor_scope_list: List[Dict[str, Any]] = [item
        for item in status_list
        if item.get("in_refactor_scope", False)
    ]   
    # 2. 从重构范围的文件中筛选出还未重构的文件
    to_refactor_list : List[Dict[str, Any]] = [item
        for item in refactor_scope_list
        if not item.get("refactored", False)
    ]
    # 3. 按照dependency排序从小到大排序to_refactor_list
    to_refactor_list.sort(key=lambda x: x.get("dependencies", 0))
    # 4. 依次重构to_refactor_list中的文件
    designer = Designer()
    for item in to_refactor_list:
        _designer_task(designer, item.get("path"))
            # _repair_task(repairer, item.get("path"))
    
    end_time = time.time()
    print(f"重构完成，耗时: {end_time - start_time} 秒")

def simple_repair_pipeline():
    # 1. 对于GRAPH_JSON_PATH中的每个节点，在REPAIR_TEST_PATH中创建id的文件，并写入code
    graph_dict = _load_json(GRAPH_JSON_PATH)
    sources_path = REPAIR_TEST_PATH / "main" / "sources"
    sources_path.write_text("", encoding="utf-8")
    for node in graph_dict.get("nodes", []):
        node_id = node.get("id")
        node_code = node.get("code")
        # node_type = node.get("type")
        node_path = REPAIR_TEST_PATH / "source" / node_id
        node_path.write_text(node_code, encoding="utf-8")
        if node.get("type") == "source":
            with open(sources_path, "a", encoding="utf-8") as f:
                f.write(f"../source/{node_id}\n")

    # 对于
    # repairer = Repairer()
    # for node in graph_dict.get("nodes", []):
    #     node_id = node.get("id")
    #     node_type = node.get("type")
    #     if node_id == "BackgroundTask.cc":
    #         repairer.simple_repair_flow(node_id)

    # 只build

def simple_static_analysis_pipeline():
    pass

def run_refactor_pipeline(
    file_list: List[str],
    base_path: str,
    max_repair_iterations: int = 3,
) -> Dict[str, Any]:
    """
    基于 file_status.json 与依赖图执行重构与传播流程。
    file_list / project_path / max_repair_iterations 参数保留兼容性，目前不再使用。
    """
    start_time = time.time()
    base_path_obj = Path(base_path)

    results: Dict[str, Any] = {
        "designer_phase": {
            "submitted": 0,
            "completed": 0,
            "errors": [],
        },
        "propagation_phase": {
            "evaluated": 0,
            "refactored": 0,
            "errors": [],
        },
        "total_time": 0.0,
    }

    if not STATUS_JSON_PATH.exists():
        raise FileNotFoundError(f"未找到状态文件: {STATUS_JSON_PATH}")

    status_list: List[Dict[str, Any]] = _load_json(STATUS_JSON_PATH)
    in_scope_items = _build_in_scope_list(status_list)
    in_scope_paths = {_strip_file_prefix(item.get("path", "")) for item in in_scope_items}
    in_scope_paths.discard("")

    print(f"共计 {len(in_scope_paths)} 个文件在重构范围内：{in_scope_paths}")
    designer = Designer()

    pending_paths = [
        _strip_file_prefix(item["path"])
        for item in in_scope_items
        if not item.get("refactored", False)
    ]
    results["designer_phase"]["submitted"] = len(pending_paths)

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(pending_paths)))) as executor:
        future_map = {
            executor.submit(
                _designer_task,
                designer,
                base_path_obj,
                relative_path,
            ): relative_path
            for relative_path in pending_paths
        }

        completed_paths: List[str] = []
        for future in as_completed(future_map):
            relative_path, ok, error_message = future.result()
            if ok:
                completed_paths.append(relative_path)
                results["designer_phase"]["completed"] += 1
            else:
                print(f"Designer 重构失败: {relative_path}，原因: {error_message}")
                if error_message:
                    results["designer_phase"]["errors"].append(error_message)
    
    print(f"Designer 重构完成: {completed_paths}")
    print(f"results: {results}")
    exit(0)

    if completed_paths:
        _update_status_refactored(status_list, completed_paths)
        _save_json(STATUS_JSON_PATH, status_list)
        print(f"已更新 {len(completed_paths)} 个文件的重构状态。")

    if not DEPENDENCY_JSON_PATH.exists():
        print(f"⚠ 未找到依赖文件: {DEPENDENCY_JSON_PATH}，跳过传播阶段。")
        results["total_time"] = time.time() - start_time
        return results

    dependency_data = _load_json(DEPENDENCY_JSON_PATH)
    fanout = _build_fanout(dependency_data, in_scope_paths)
    initial_queue = deque(sorted(in_scope_paths))

    propagation_stats = _propagate_dependencies(designer, fanout, initial_queue)
    results["propagation_phase"].update(propagation_stats)

    results["total_time"] = time.time() - start_time
    print("Pipeline Summary")
    print("================")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results

def _save_text(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)

def convert_graph_json_code_to_markdown():
    source_cnt = 0
    for json_file in GRAPH_JSON_DIR.glob("*.json"):
        markdown_file = json_file.with_suffix(".md")
        graph_dict = _load_json(json_file)
        nodes = graph_dict.get("nodes", [])
        for node in nodes:
            if node.get("type") == "source":
                source_cnt += 1
        code = '\n'.join([f"## {node.get('id', '')}\n\n```c\n{node.get('code', '')}\n```" for node in graph_dict.get("nodes", [])])
        _save_text(markdown_file, code)
    print(f"source_cnt: {source_cnt}")


if __name__ == "__main__":
    # reference_json_path = "evox-server/.rag/xiaozhi/designer_11_04/test_design_2.json"
    # 清空app.log文件 
    # with open("app.log", "w") as f:
    #     f.write("")
    simple_pipeline()
    # simple_repair_pipeline()
    convert_graph_json_code_to_markdown()

