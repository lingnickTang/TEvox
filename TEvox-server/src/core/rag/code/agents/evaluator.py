"""
评估器 Agent

用于评估代码生成质量，包含：
1. 定量评估：提取并比较函数调用和变量
2. 定性分析：语义正确性、结构相似性、功能完整性评分
"""
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.utils import get_llm, Agent
from src.base import DefaultConfig
from src.utils.log import logger
from src.core.rag.code.agents.base_agent import BaseAgent
from src.core.rag.code.agents.evaluator_prompt import EVALUATOR_PROMPTS


class EvaluatorAgent(BaseAgent):
    """
    评估器 Agent，用于评估代码生成质量
    """
    
    def __init__(self, agent: Optional[Agent] = None, benchmark_dir: str = "evox-server/.rag/benchmark/functions_all"):
        """
        初始化评估器 Agent
        
        Args:
            agent: 可选的 Agent 实例，如果为 None 则创建新实例
            benchmark_dir: benchmark YAML 文件所在目录
        """
        super().__init__()
        
        if agent is None:
            llm = get_llm(model_name=DefaultConfig.evaluator_model)
            self.agent = Agent(llm)
        else:
            self.agent = agent
        
        self.benchmark_dir = Path(benchmark_dir)
        
        logger.info(f"EvaluatorAgent initialized with benchmark_dir: {benchmark_dir}")
    
    def load_benchmark_file(self, filename: str) -> Dict[str, Any]:
        """
        加载单个 benchmark YAML 文件（新格式：字典格式，包含顶层的 file_path 和 benchmark 列表）
        
        Returns:
            包含 file_path 和 benchmark 列表的字典
        """
        file_path = self.benchmark_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Benchmark file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            raise ValueError(f"Unexpected YAML format in {filename}: expected dict, got {type(data)}")
        
        if "benchmark" not in data:
            raise ValueError(f"Missing 'benchmark' field in {filename}")
        
        return data
    
    def get_reference_file_path(self, benchmark_filename: str) -> Path:
        """获取参考数据（函数调用和变量）文件路径"""
        return self.benchmark_dir / f"{Path(benchmark_filename).stem}_reference.yaml"
    
    def extract_references(self, ground_truth: str, query: str) -> Dict[str, Any]:
        """
        从 ground_truth 中提取函数调用和变量（参考数据）
        
        Args:
            ground_truth: 标准答案代码
            query: 任务查询描述
            
        Returns:
            包含函数调用和变量的字典
        """
        prompt = EVALUATOR_PROMPTS["extract_references"].format(
            code=ground_truth,
            query=query
        )
        
        result = self.agent.invoke_with_structured_output(prompt)
        return result
    
    def load_or_extract_references(self, benchmark_filename: str, ground_truth: str, query: str) -> Dict[str, Any]:
        """
        加载或提取参考数据（函数调用和变量）
        如果文件存在则直接读取，否则提取并保存
        
        Args:
            benchmark_filename: benchmark YAML 文件名
            ground_truth: 标准答案代码
            query: 任务查询描述
        Returns:
            参考数据（函数调用和变量）
        """
        ref_file = self.get_reference_file_path(benchmark_filename)
        references = {}
        
        # 尝试从文件加载
        if ref_file.exists():
            logger.info(f"Loading references from {ref_file}")
            with open(ref_file, 'r', encoding='utf-8') as f:
                references = yaml.safe_load(f) or {}
            for item in references.keys():
                if item == query:
                    return references[item]
        
        # 如果文件不存在或者对应引用不存在，则提取并保存
        logger.info(f"Extracting references for {benchmark_filename}")
        references = self.extract_references(ground_truth, query)
        if not references:
            logger.warning(f"No references found for query: {query}")
            return {}
        # 保存到文件
        saved_data = {
            query: references
        }
        with open(ref_file, 'a+', encoding='utf-8') as f:
            yaml.dump(saved_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        logger.info(f"Saved references to {ref_file}")
        return references
    
    def quantitative_evaluation(
        self,
        generated_code: str,
        reference_data: Dict[str, Any],
        query: str
    ) -> Dict[str, Any]:
        """
        定量评估：比较生成代码与参考数据中的函数调用和变量
        
        Args:
            generated_code: 生成的代码
            reference_data: 参考数据（从ground_truth提取的函数调用和变量）
            query: 任务查询描述
            
        Returns:
            定量评估结果
        """
        reference_functions = reference_data.get("functions", [])
        reference_functions_cnt = len(reference_functions)
        reference_variables = reference_data.get("variables", [])
        reference_variables_cnt = len(reference_variables)
        
        # 将列表转换为字符串格式，便于在 prompt 中显示
        if isinstance(reference_functions, list):
            functions_str = "\n".join(f"  - {f}" for f in reference_functions) if reference_functions else "  (none)"
        else:
            functions_str = str(reference_functions)
        
        if isinstance(reference_variables, list):
            variables_str = "\n".join(f"  - {v}" for v in reference_variables) if reference_variables else "  (none)"
        else:
            variables_str = str(reference_variables)
        
        prompt = EVALUATOR_PROMPTS["quantitative_evaluation"].format(
            generated_code=generated_code,
            reference_functions=functions_str,
            reference_variables=variables_str,
            query=query
        )
        
        result = self.agent.invoke_with_structured_output(prompt)
        result["reference_functions_cnt"] = reference_functions_cnt
        result["reference_variables_cnt"] = reference_variables_cnt
        return result
    
    def qualitative_evaluation(
        self,
        generated_code: str,
        ground_truth: str,
        query: str,
    ) -> Dict[str, Any]:
        """
        定性评估：语义正确性、结构相似性、功能完整性
        
        Args:
            generated_code: 生成的代码
            ground_truth: 标准答案代码
            query: 任务查询描述
            
        Returns:
            定性评估结果
        """
        prompt = EVALUATOR_PROMPTS["qualitative_evaluation"].format(
            generated_code=generated_code,
            ground_truth=ground_truth,
            query=query,
        )
        
        result = self.agent.invoke_with_structured_output(prompt)
        return result
    
    def compare_workflow(self, ground_truth: str, workflow: str, query: str) -> Dict[str, Any]:
        """
        对比 workflow 和 ground_truth
        
        Args:
            ground_truth: 标准答案代码
            workflow: workflow 代码
            query: 任务查询描述
            
        Returns:
            对比结果
        """
        prompt = EVALUATOR_PROMPTS["compare_workflow"].format(
            ground_truth=ground_truth,
            workflow=workflow,
            query=query
        )
        
        result = self.agent.invoke_with_structured_output(prompt)
        return result
    
    def evaluate_single_query(
        self,
        query,
        benchmark_filename,
        test_type
    ) -> Dict[str, Any]:
        """
        评估单个 query 的生成代码
        
        这个方法封装了完整的评估流程，包括：
        1. 从 yaml 文件读取 test_type 字段
        2. 提取参考数据（函数调用和变量）
        3. 定量评估
        4. 定性评估
        
        Args:
            query: 任务查询描述
            benchmark_filename: benchmark 文件名
            test_type: 测试类型
        Returns:
            评估结果字典，包含 quantitative 和 qualitative 评估结果
        """
        logger.info(f"Evaluating query: {query}")
        
        generated_code = ""
        ground_truth = ""
        
        # 从 yaml 文件读取数据（如果提供了 benchmark_filename）
        if benchmark_filename:
            try:
                benchmark_data = self.load_benchmark_file(benchmark_filename)
                benchmark_list = benchmark_data.get("benchmark", [])
                for item in benchmark_list:
                    if item.get("query") == query:
                        generated_code = item.get(test_type, "")
                        ground_truth = item.get("ground_truth", "")
                        break
            except Exception as e:
                logger.warning(f"Failed to load benchmark file: {e}")
        
        if not generated_code:
            logger.warning(f"No test_type field found for query: {query}")
            return {
                "error": f"No test_type field found for query: {query}",
                "quantitative": None,
                "qualitative": None
            }
        
        if not ground_truth:
            logger.warning(f"No ground_truth found for query: {query}")
            return {
                "error": f"No ground_truth found for query: {query}",
                "quantitative": None,
                "qualitative": None
            }

        reference_data = None
        if benchmark_filename:
            # 从 benchmark 文件中加载参考数据
            reference_data = self.load_or_extract_references(benchmark_filename, ground_truth, query)
        
        # 2. 定量评估
        logger.info("Performing quantitative evaluation")
        quantitative_result = self.quantitative_evaluation(
            generated_code=generated_code,
            reference_data=reference_data,
            query=query
        )
        
        # 3. 定性评估
        logger.info("Performing qualitative evaluation")
        qualitative_result = self.qualitative_evaluation(
            query=query,
            generated_code=generated_code,
            ground_truth=ground_truth,
        )
        
        return {
            "quantitative": quantitative_result,
            "qualitative": qualitative_result
        }
    
    def evaluate_benchmark(
        self,
        benchmark_filename: str,
        test_type: str = "workflow"
    ) -> Dict[str, Any]:
        """
        评估整个 benchmark 文件
        
        该方法通过调用 evaluate_single_query 来评估每个 query，实现关注点分离。
        
        Args:
            benchmark_filename: benchmark YAML 文件名（生成的代码从 yaml 文件的 test_type 字段中获取）
            test_type: 测试类型，默认为 "workflow"
            
        Returns:
            评估结果，包含定量和定性评估
        """
        logger.info(f"Evaluating benchmark file: {benchmark_filename}")
        benchmark_data = self.load_benchmark_file(benchmark_filename)
        
        # 从顶层获取 file_path 和 benchmark 列表
        file_path = benchmark_data.get("file_path", "")
        benchmark_list = benchmark_data.get("benchmark", [])
        
        results = []
        
        for item in benchmark_list:
            query = item.get("query", "")
            ground_truth = item.get("ground_truth", "")
            test_type = item.get("test_type")
            
            if not ground_truth:
                logger.warning(f"No ground_truth for query: {query}")
                continue
            
            # 从 test_type 字段获取生成的代码
            if not test_type:
                logger.warning(f"No test_type field for query: {query}, skipping evaluation")
                continue
            
            # 使用 evaluate_single_query 进行评估（封装了定量和定性评估）
            evaluation_result = self.evaluate_single_query(
                query=query,
                benchmark_filename=benchmark_filename,
                test_type=test_type
            )
            
            # 检查评估结果是否有错误
            if "error" in evaluation_result:
                logger.warning(f"Evaluation failed for query: {query}, error: {evaluation_result.get('error')}")
                continue
            
            # workflow 对比（与 ground_truth 对比，这是额外的对比功能）
            workflow_comparison = None
            try:
                workflow_comparison = self.compare_workflow(ground_truth, test_type, query)
            except Exception as e:
                logger.warning(f"Failed to compare workflow for query {query}: {e}")
            
            result_item = {
                "query": query,
                "file_path": file_path,
                "quantitative": evaluation_result.get("quantitative"),
                "qualitative": evaluation_result.get("qualitative"),
                "test_type_comparison": test_type_comparison
            }
            
            results.append(result_item)
        
        # 计算平均分
        if results:
            # 过滤掉没有 qualitative 结果的项目
            valid_results = [r for r in results if r.get("qualitative")]
            if valid_results:
                avg_semantic = sum(r["qualitative"].get("semantic_score", 0) for r in valid_results) / len(valid_results)
                avg_structure = sum(r["qualitative"].get("structure_score", 0) for r in valid_results) / len(valid_results)
                avg_completeness = sum(r["qualitative"].get("completeness_score", 0) for r in valid_results) / len(valid_results)
            else:
                avg_semantic = avg_structure = avg_completeness = 0
        else:
            avg_semantic = avg_structure = avg_completeness = 0
        
        evaluation_result = {
            "benchmark_file": benchmark_filename,
            "total_cases": len(benchmark_list),
            "evaluated_cases": len(results),
            "average_scores": {
                "semantic_score": avg_semantic,
                "structure_score": avg_structure,
                "completeness_score": avg_completeness
            },
            "results": results
        }
        
        # 保存为 JSON 文件
        output_file = self.benchmark_dir / f"{Path(benchmark_filename).stem}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(evaluation_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Evaluation results saved to {output_file}")
        
        return evaluation_result


if __name__ == "__main__":
    evaluator = EvaluatorAgent()
    
    # 示例：评估单个 benchmark 文件（生成的代码从 yaml 文件的 workflow 字段中获取）
    result = evaluator.evaluate_benchmark("AudioDetectionTask.yaml")
    print(f"Average semantic score: {result['average_scores']['semantic_score']}")

