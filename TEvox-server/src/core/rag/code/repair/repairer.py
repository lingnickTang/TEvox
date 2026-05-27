# evox-server/src/core/rag/code/repair/repairer.py

from typing import Dict, List, Tuple, Any
from src.utils import get_llm, Agent
from src.base import DefaultConfig
from src.core.rag.code.esp_idf_terminal import ESPIDFTerminal
from src.core.rag.code.repair.repairer_prompt import REPAIRER_PROMPTS
from src.core.rag.code.storage import GraphJsonManager
from src.core.rag.code.PATH import BASE_PATH, GRAPH_JSON_DIR
from pydantic import BaseModel, Field
import os
import json
from pathlib import Path

class AnalysisResult(BaseModel):
    has_errors: bool
    error_node_ids: List[str]
    error_analysis: dict[str, str]

class Repairer:
    """Code repairer supporting test generation, execution, and code repair"""
    
    def __init__(self, max_retries: int = 3):
        self.agent = Agent(get_llm(model_name=DefaultConfig.agent_model))
        self.terminal = None
        self.max_retries = max_retries
        self.graph_manager = GraphJsonManager()

    def generate_test(self, node_id: str, test_filename: str, code: str, description: str, project_path: str) -> str:
        """Generate test code"""
        # Create directory structure
        test_dir = os.path.join(project_path, "test", "test_files")
        # Path for the test file
        test_filepath = os.path.join(test_dir, test_filename)
        # If test file already exists, return its content directly
        if os.path.exists(test_filepath):
            with open(test_filepath, 'r', encoding='utf-8') as f:
                return f.read()
        # else generate test and return
        implementations_file_list = self._get_implementations_context(project_path)
        interfaces_file_list = self._get_interfaces_context(project_path)
        prompt = REPAIRER_PROMPTS["test_generation"].format(
            description=description,
            code=code,
            filename=node_id, # node_id is the file name
            implementations_file_list=implementations_file_list,
            interfaces_file_list=interfaces_file_list
        )
        return self.agent.invoke_with_code_block(prompt)
    
    def simple_generate_test(self, node_code, node_header) -> str:
        prompt = REPAIRER_PROMPTS["simple_test_generation"].format(
            code=node_code,
            header=node_header
        )
        return self.agent.invoke_with_code_block(prompt)

    def execute_test(self, test_code: str, test_filename: str, project_path: str) -> str:
        """Execute tests using ESP-IDF terminal with specific file placement"""
        if not self.terminal:
            self.terminal = ESPIDFTerminal(project_path=os.path.join(project_path, "test"))
        
        # Create directory structure
        test_files_dir = os.path.join(project_path, "test", "test_files")
        main_dir = os.path.join(project_path, "test", "main")

        # Write test files to test/test_files/{test_file_name}
        test_filepath = os.path.join(test_files_dir, test_filename)
        with open(test_filepath, 'w', encoding='utf-8') as f:
            f.write(test_code)
        
        # Overwrite test/main/main.cc with test file content
        main_cc_path = os.path.join(main_dir, "main.cc")
        with open(main_cc_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
        
        # Execute build and test
        success, stdout, stderr = self.terminal.build_flash_monitor()
        execution_result = f"Success: {success}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        return execution_result
    
    def analyze_test_results(self, test_results: str, nodes_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test results to identify nodes with errors"""
        prompt = REPAIRER_PROMPTS["test_analysis"].format(
            test_results=test_results,
            nodes_info=json.dumps(nodes_info)
        )
        result = self.agent.invoke_with_structured_output(prompt, schema=AnalysisResult)
        print(f"Analysis result: {result}")
        return result
    
    def repair_code(self, code: str, analysis_result: str, project_path: str = None) -> str:
        """Repair code based on test results"""
        implementations_file_list = ""
        interfaces_file_list = ""
        if project_path:
            implementations_file_list = self._get_implementations_context(project_path)
            interfaces_file_list = self._get_interfaces_context(project_path)
        prompt = REPAIRER_PROMPTS["code_repair"].format(
            code=code,
            analysis_result=analysis_result,
            implementations_file_list=implementations_file_list,
            interfaces_file_list=interfaces_file_list
        )
        return self.agent.invoke_with_code_block(prompt)
    
    def _get_dir_for_node_type(self, base_path: str, node_type: str) -> str:
        """
        根据节点类型返回对应的路径
        
        Args:
            node_type: 节点类型
            base_path: 基础路径
            
        Returns:
            对应的路径目录
        """
        type_dir_map = {
            'interface': os.path.join(base_path, "test/source/interfaces"),
            'implementation': os.path.join(base_path, "test/source/implementations"),
            'header': os.path.join(base_path, "test/source"),
            'source': os.path.join(base_path, "test/source")
        }
        return type_dir_map.get(node_type, os.path.join(base_path, "test/source"))

    def _read_file(self, filepath: str) -> str:
        """
        通用的文件读取方法
        
        Args:
            filepath: 文件路径
            
        Returns:
            文件内容
        """
        if not filepath.exists():
            return ""
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    def _write_file(self, node_id: str, code: str, dir_path: str):
        """
        通用的文件写入方法
        
        Args:
            node_id: 节点ID
            code: 代码内容
            dir_path: 目录路径
            
        Returns:
            写入的文件路径
        """        
        filepath = os.path.join(dir_path, node_id)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
    
    def _get_directory_file_list(self, project_path: str, subdirectory: str) -> str:
        """
        获取指定目录下的文件列表作为上下文
        
        Args:
            project_path: 项目根路径
            subdirectory: 相对于 project_path/test/source 的子目录名
            
        Returns:
            格式化的文件列表字符串
        """
        target_dir = os.path.join(project_path, "test", "source", subdirectory)
        
        if os.path.exists(target_dir):
            # 获取所有文件（仅文件名，不读取内容）
            files = [f for f in os.listdir(target_dir) 
                    if os.path.isfile(os.path.join(target_dir, f))]
            
            if files:
                # 返回排序后的文件列表，每行一个文件名
                return "\n".join(sorted(files))
            else:
                return ""
        else:
            return ""
    
    def _get_implementations_context(self, project_path: str) -> str:
        """
        获取 implementations 目录下的文件列表作为上下文
        
        Args:
            project_path: 项目根路径
            
        Returns:
            格式化的 implementations 文件列表字符串
        """
        return self._get_directory_file_list(project_path, "implementations")
    
    def _get_interfaces_context(self, project_path: str) -> str:
        """
        获取 interfaces 目录下的文件列表作为上下文
        
        Args:
            project_path: 项目根路径
            
        Returns:
            格式化的 interfaces 文件列表字符串
        """
        return self._get_directory_file_list(project_path, "interfaces")
    
    def _update_sources_file(self, node_id: str, project_path: str):
        """
        更新 test/main/sources 文件，如果节点对应的文件路径不存在则添加到最后一行
        
        Args:
            node_id: 节点ID（文件名）
            project_path: 项目根路径
        """
        sources_file_path = os.path.join(project_path, "test", "main", "sources")
        source_entry = f"../source/{node_id}"
        
        # 读取现有内容
        existing_lines = []
        if os.path.exists(sources_file_path):
            with open(sources_file_path, 'r', encoding='utf-8') as f:
                existing_lines = [line.strip() for line in f.readlines() if line.strip()]
        
        # 检查是否已存在
        if source_entry not in existing_lines:
            # 确保目录存在
            os.makedirs(os.path.dirname(sources_file_path), exist_ok=True)
            
            # 追加到文件末尾
            with open(sources_file_path, 'a', encoding='utf-8') as f:
                f.write(f"{source_entry}\n")
            
            print(f"Added {source_entry} to sources file")
        else:
            print(f"{source_entry} already exists in sources file")
    
    def simple_execute_test(self, test_code: str, node_id: str):
        test_filepath = REPAIR_TEST_PATH / "test_files" / node_id.replace(".cc", "_test.cc")
        test_filepath.write_text(test_code, encoding='utf-8')
        test_main_filepath = REPAIR_TEST_PATH / "main" / "main.cc"
        test_main_filepath.write_text(test_code, encoding='utf-8')
        if not self.terminal:
            self.terminal = ESPIDFTerminal(project_path=REPAIR_TEST_PATH)
        return self.terminal.build()

    def simple_repair_flow(self, relative_path: str, max_iterations: int = 3) -> bool:
        json_path = GRAPH_JSON_DIR / f"{Path(relative_path).stem}.json"
        node_graph = self.graph_manager.load(str(json_path))

        # 把所有文件写到relative_path(去除末尾文件，比如main/application.cc->main)+node_id文件中；
        for node in node_graph.get('nodes', []):
            node_id = node.get('id')
            path = BASE_PATH / relative_path.parent / node_id
            with open(path, 'w', encoding='utf-8') as f:
                f.write(node.get('code', ''))
        
        if not self.terminal:
            self.terminal = ESPIDFTerminal(project_path=BASE_PATH)
        for i in range(max_iterations):
            result = self.terminal.build_flash_monitor()
            if result[0]: continue
            analysis_result = self.analyze_test_results(result[1], result[2])

        # 判断是否修复成功，如果修复成功，则返回True，否则返回False
        return False if i == max_iterations - 1 else True
        

    def _repair_flow(self, node_graph: Dict[str, Any], project_path: str, max_iterations: int = 3) -> Dict[str, Any]:
        """
        Complete repair flow with retry logic
        
        Args:
            node_graph: Complete node graph with nodes and edges
            project_path: Project root path
            max_iterations: Maximum repair iterations
            
        Returns:
            Dictionary containing repair results
        """
        all_nodes = {node['id']: node for node in node_graph.get('nodes', [])}
        testable_nodes = [
            node for node in node_graph.get('nodes', [])
            if node.get('type') in ['implementation', 'source']
        ]

        # First pass: write all files to their appropriate directories
        # if the file already exists, skip
        for node in all_nodes.values():
            node_type = node.get('type', '')
            node_id = node.get('id')
            node_code = node.get('code', '')
            
            dir_path = self._get_dir_for_node_type(project_path, node_type)
            if not os.path.exists(os.path.join(dir_path, node_id)):
                self._write_file(node_id, node_code, dir_path)
            else:
                print(f"File {node_id} already exists, skipping")
            
            # 如果节点类型是 source，更新 sources 文件
            if node_type == 'source':
                self._update_sources_file(node_id, project_path)
        
        # Iteratively test and repair
        for node in testable_nodes:
            node_id = node.get('id')
            node_type = node.get('type', '')
            dir_path = self._get_dir_for_node_type(project_path, node_type)

            if not os.path.exists(os.path.join(dir_path, node_id)):
                node_code = node.get('code', '')
            else:
                node_code = self._read_file(os.path.join(dir_path, node_id))

            node_description = node.get('description', '')

            # Generate test code for this node
            # node_id is expected to be in the format "name.cc/h"
            test_filename = f"{os.path.splitext(node_id)[0]}_test.cc"
            test_code = self.generate_test(node_id, test_filename, node_code, node_description, project_path)
            
            nodes_info = {
                node_id: node_code,
                test_filename: test_code,
            }
            for i in range(max_iterations):
                execution_result = self.execute_test(nodes_info[test_filename], test_filename, project_path)
                print(f"Execution result: {execution_result}")
                analysis_result = self.analyze_test_results(execution_result, nodes_info)
                if analysis_result.has_errors:
                    for error_node_id in analysis_result.error_node_ids:
                        nodes_info[error_node_id] = self.repair_code(
                            nodes_info[error_node_id], 
                            analysis_result.error_analysis[error_node_id],
                            project_path  # 添加 project_path 参数
                        )
                        if not error_node_id == test_filename: # update source code into files
                            node_type = all_nodes[error_node_id].get('type', '')
                            dir_path = self._get_dir_for_node_type(project_path, node_type)
                            self._write_file(error_node_id, nodes_info[error_node_id], dir_path)
                else:
                    break
            
            # update node graph with the repaired source code
            for node in node_graph['nodes']:
                if node.get('id') == node_id:
                    node['code'] = nodes_info[node_id]
                    break

            if analysis_result.has_errors:
                return {
                    'success': False,
                    'status': 'failed',
                    'error_node_ids': analysis_result.error_node_ids,
                    'error_analysis': analysis_result.error_analysis,
                }
            # Max iterations reached
        return True

if __name__ == "__main__": 
    repairer = Repairer()
    graph_manager = GraphJsonManager()
    
    json_path = "evox-server/.rag/xiaozhi/designer_11_04/test_design_1.json"
    node_graph = graph_manager.load(json_path)
    
    project_path = "D:/Download/github/xiaozhi-esp32" 
    results = repairer._repair_flow(node_graph, project_path, max_iterations=10)
    # save the repaired node graph to the json file
    graph_manager.save(node_graph, json_path)
    
    print(f"Repair completed: {results}")
