import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from src.utils import get_llm, Agent
from src.base import DefaultConfig
from src.core.rag.code.query.retriever.retriever import Retriever
from src.core.rag.code.query.evaluator.evaluator_prompt import EVALUATOR_PROMPTS

# 简化的数据模型
class EvaluationResult(BaseModel):
    query: str = Field(description="原始查询")
    retrieved_results: List[str] = Field(description="检索到的结果ID列表")
    #effective_block_ids: List[str] = Field(description="有效context块ID列表")
    generated_answer: str = Field(description="基于检索结果生成的答案")
    
    # 基础统计
    total_blocks_count: int = Field(description="总context块数量")
    #effective_blocks_count: int = Field(description="有效context块数量")
    
    # 相关性指标
    average_query_relevance: float = Field(description="平均query相关性得分")
    average_code_relevance: float = Field(description="平均代码相关性得分")
    
    # 块相关性评分
    block_relevance_scores: List[Dict[str, Any]] = Field(description="各块的相关性评分列表")
    
    # 新生代码分析
    function_novelty_scores: List[Dict[str, Any]] = Field(description="各函数的新生程度评分列表")
    average_novelty_score: float = Field(description="平均新生程度得分")

# 有效context块输出模型    
# class ContextBlocks(BaseModel):
#     effective_block_ids: List[str] = Field(description="有效context块ID列表")

class BlockRelevanceScores(BaseModel):
    block_scores: List[Dict[str, Any]] = Field(description="各块的相关性打分列表")

class FunctionNoveltyScores(BaseModel):
    """函数新生程度评分结果"""
    function_scores: List[Dict[str, Any]] = Field(description="各函数的新生程度评分列表")

class ReuseEvaluation(BaseModel):
    """复用评估结果模型"""
    tp: int
    fp: int
    fn: int

class Evaluator:
    """
    代码检索评估器，用于评估检索质量和答案生成质量
    """
    
    def __init__(self):
        # 初始化LLM和Agent
        self.llm = get_llm(
            model_name=DefaultConfig.agent_model,
        )
        self.agent = Agent(self.llm)
        
        # 初始化检索器
        self.retriever = Retriever()
        
    def evaluate_queries(
        self, 
        graph_json_path: str, 
        embedding_json_path: str,
        query_json_path: str,
        top_k: int = 5,
        similarity_threshold: float = 0.3
    ) -> List[EvaluationResult]:
        """
        评估查询集合的检索和答案生成质量
        
        Args:
            graph_json_path: 图数据JSON文件路径
            query_json_path: 查询数据JSON文件路径
            top_k: 检索返回的结果数量
            similarity_threshold: 相似度阈值
            
        Returns:
            评估结果列表
        """
        # 1. 加载查询数据
        queries_data = self._load_queries(query_json_path)
        
        # 2. 依次处理每个查询
        evaluation_results = []
        for query_item in queries_data[:1]:
            result = self._evaluate_single_query(
                query_item, 
                graph_json_path, 
                embedding_json_path,
                top_k, 
                similarity_threshold
            )
            evaluation_results.append(result)
            
        return evaluation_results
    
    def _evaluate_single_query(
        self, 
        query_item: Dict[str, Any], 
        graph_json_path: str,
        embedding_json_path: str, 
        top_k: int,
        similarity_threshold: float
    ) -> EvaluationResult:
        """
        评估单个查询 - 按照步骤逐步处理
        """
        query_text = query_item.get("query", "")
        
        # 步骤1: 检索
        retrieved_ids = self.retriever.retrieve(
            query_text, 
            embedding_json_path,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )
        
        # 步骤2: 获取context块
        graph_data = self._load_graph_data(graph_json_path)
        context_blocks = self._get_context_blocks(retrieved_ids, graph_data)
        
        # 步骤3: 评估与query的相关性
        query_relevance_scores = self._evaluate_query_relevance(query_text, context_blocks)
        
        # 步骤4: 生成代码
        generated_code = self._generate_answer_with_effective_context(query_text, context_blocks)
        
        # 步骤5: 评估与生成代码的相关性
        code_relevance_scores = self._evaluate_code_relevance(generated_code, context_blocks)
        
        # 步骤6: 新生代码分析
        function_novelty_scores = self._evaluate_code_novelty(generated_code, context_blocks)
        
        # 步骤7: 合并评分并计算平均值
        combined_scores = self._combine_relevance_scores(query_relevance_scores, code_relevance_scores)
        
        # 步骤8: 计算统计指标
        stats = self._calculate_relevance_stats(combined_scores)
        novelty_stats = self._calculate_novelty_stats(function_novelty_scores)
        
        return EvaluationResult(
            query=query_text,
            retrieved_results=retrieved_ids,
            #effective_block_ids=[score['block_id'] for score in combined_scores if score.get('query_relevance', 0) >= 5.0],
            generated_answer=generated_code,
            total_blocks_count=len(context_blocks),
            #effective_blocks_count=len([s for s in combined_scores if s.get('query_relevance', 0) >= 5.0]),
            average_query_relevance=stats['avg_query_relevance'],
            average_code_relevance=stats['avg_code_relevance'],
            block_relevance_scores=combined_scores,
            function_novelty_scores=function_novelty_scores,
            average_novelty_score=novelty_stats['avg_novelty_score']
        )
    
    def _generate_answer(
        self, 
        query: str, 
        retrieved_ids: List[str], 
        graph_json_path: str
    ) -> str:
        """
        基于检索结果生成答案
        """
        # 1. 加载图数据
        graph_data = self._load_graph_data(graph_json_path)
        
        # 2. 根据检索到的ID获取相关代码片段
        retrieved_code = []
        for code_id in retrieved_ids:
            if code_id in graph_data:
                code_info = graph_data[code_id]
                retrieved_code.append({
                    "id": code_id,
                    "description": code_info.get("description", ""),
                    "code": code_info.get("code", "")
                })
        
        # 3. 使用LLM生成答案
        prompt = EVALUATOR_PROMPTS["generation"]["generate_answer"]
        prompt = prompt.format(
            query=query,
            retrieved_code=json.dumps(retrieved_code, ensure_ascii=False, indent=2)
        )
        
        response = self.agent.invoke(prompt)
        return response
    
    def _load_queries(self, query_json_path: str) -> List[Dict[str, Any]]:
        """加载查询数据"""
        with open(query_json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_graph_data(self, graph_json_path: str) -> Dict[str, Any]:
        """加载图数据"""
        with open(graph_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    
    def _get_context_blocks(self, retrieved_ids: List[str], graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取context块信息（仅包含code）"""
        context_blocks = []
        nodes = graph_data.get("nodes", [])
        for node_id in retrieved_ids:
            for node in nodes:
                if node.get("id") == node_id:
                    context_blocks.append({
                        "id": node.get("id"),
                        "code": node.get("code", "")
                    })
                    break
        
        return context_blocks

    # def _evaluate_context_blocks(self, query: str, context_blocks: List[Dict[str, Any]]) -> ContextBlocks:
    #     """评估context块有效性"""
    #     prompt = EVALUATOR_PROMPTS["context_blocks"]
    #     prompt = prompt.format(
    #         query=query,
    #         context_blocks=json.dumps(context_blocks, ensure_ascii=False, indent=2)
    #     )
        
    #     response = self.agent.invoke_with_structured_output(prompt, schema=ContextBlocks)
    #     return response

    def _evaluate_query_relevance(
        self, 
        query: str, 
        context_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """评估context块与query的相关性"""
        prompt = EVALUATOR_PROMPTS["query_relevance_scoring"]
        prompt = prompt.format(
            query=query,
            context_blocks=json.dumps(context_blocks, ensure_ascii=False, indent=2)
        )
        
        response = self.agent.invoke_with_structured_output(prompt, schema=BlockRelevanceScores)
        return response.block_scores

    def _evaluate_code_relevance(
        self, 
        generated_code: str,
        context_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """评估context块与生成代码的相关性"""
        prompt = EVALUATOR_PROMPTS["code_relevance_scoring"]
        prompt = prompt.format(
            generated_code=generated_code,
            context_blocks=json.dumps(context_blocks, ensure_ascii=False, indent=2)
        )
        
        response = self.agent.invoke_with_structured_output(prompt, schema=BlockRelevanceScores)
        return response.block_scores

    def _combine_relevance_scores(
        self, 
        query_scores: List[Dict[str, Any]], 
        code_scores: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """合并query相关性和代码相关性评分"""
        # 创建block_id到评分的映射
        query_score_map = {score['block_id']: score.get('query_relevance', 0) for score in query_scores}
        code_score_map = {score['block_id']: score.get('code_relevance', 0) for score in code_scores}
        
        # 获取所有block_id
        all_block_ids = set(query_score_map.keys()) | set(code_score_map.keys())
        
        combined_scores = []
        for block_id in all_block_ids:
            query_relevance = query_score_map.get(block_id, 0)
            code_relevance = code_score_map.get(block_id, 0)
            
            combined_scores.append({
                'block_id': block_id,
                'query_relevance': query_relevance,
                'code_relevance': code_relevance
            })
        
        return combined_scores

    def _calculate_relevance_stats(self, scores: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算相关性统计指标"""
        if not scores:
            return {
                'avg_query_relevance': 0.0,
                'avg_code_relevance': 0.0
            }
        
        query_scores = [score.get('query_relevance', 0) for score in scores]
        code_scores = [score.get('code_relevance', 0) for score in scores]
        
        return {
            'avg_query_relevance': sum(query_scores) / len(query_scores),
            'avg_code_relevance': sum(code_scores) / len(code_scores)
        }


    def _generate_answer_with_effective_context(self, query: str, effective_context_blocks: List[Dict[str, Any]]) -> str:
        """基于有效context生成答案"""
        prompt = EVALUATOR_PROMPTS["generate_answer"]
        prompt = prompt.format(
            query=query,
            effective_context=json.dumps(effective_context_blocks, ensure_ascii=False, indent=2)
        )
        
        response = self.agent.invoke(prompt)
        return response

    def _evaluate_code_novelty(
        self, 
        generated_code: str, 
        context_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """评估生成代码中每个函数的新生程度"""
        prompt = EVALUATOR_PROMPTS["function_novelty_scoring"]
        prompt = prompt.format(
            generated_code=generated_code,
            context_blocks=json.dumps(context_blocks, ensure_ascii=False, indent=2)
        )
        
        response = self.agent.invoke_with_structured_output(prompt, schema=FunctionNoveltyScores)
        return response.function_scores

    def _calculate_novelty_stats(self, function_scores: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算新生代码统计指标"""
        if not function_scores:
            return {
                'avg_novelty_score': 0.0
            }
        
        novelty_scores = [score.get('novelty_score', 0) for score in function_scores]
        
        return {
            'avg_novelty_score': sum(novelty_scores) / len(novelty_scores)
        }
    
    def save_evaluation_results(
        self, 
        results: List[EvaluationResult], 
        output_path: str
    ) -> None:
        """保存评估结果"""
        results_data = [result.dict() for result in results]
        # 确保目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)

def main():
    """测试函数"""
    try:
        # 初始化评估器
        evaluator = Evaluator()
        
        print("开始执行评估...")

        # 设置参数
        import datetime
        name = "baseline"
        top_k = 5
        similarity_threshold = 0.5
        date = datetime.datetime.now().strftime("%m_%d")
        output_path = f"evox-server/.rag/xiaozhi/queries/evaluation_{date}/evaluation_results_{name}_{top_k}_{similarity_threshold}.json"

        # 设置图数据路径
        if name == "baseline":
            graph_json_path = "evox-server/.rag/xiaozhi/full_code/functions_what_graph_concurrent.json"
        else:
            graph_json_path = "evox-server/.rag/xiaozhi/designer_9_23/test_design_3.json"

        # 执行评估
        results = evaluator.evaluate_queries(
            graph_json_path=graph_json_path,
            embedding_json_path=graph_json_path.replace(".json", ".emb.json"),
            query_json_path="evox-server/.rag/xiaozhi/queries/test_queries_11_28.json",
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )
        
        print("保存评估结果...")
        # 保存结果

        evaluator.save_evaluation_results(results, output_path)
        
        print(f"评估完成，共处理 {len(results)} 个查询")
        for i, result in enumerate(results):
            print(f"\n查询 {i+1}: {result.query}")
            print(f"检索结果: {result.retrieved_results}")
            print(f"总context块: {result.total_blocks_count}")
            print(f"平均query相关性: {result.average_query_relevance:.2f}, 平均代码相关性: {result.average_code_relevance:.2f}")
            print(f"平均新生程度: {result.average_novelty_score:.2f}")
            print(f"函数新生程度评分: {result.function_novelty_scores}")
            print(f"生成答案: {result.generated_answer[:100]}...")
            
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()

class ReuseEvaluator:
    """
    代码复用评估器
    用于评估生成代码与实际代码的复用情况
    """
    
    def __init__(self, agent: Optional[Agent] = None):
        """
        初始化评估器
        
        Args:
            agent: Optional Agent实例，如果为None则创建新的
        """
        if agent is None:
            llm = get_llm(model_name=DefaultConfig.agent_model)
            self.agent = Agent(llm)
        else:
            self.agent = agent
    
    def evaluate_reuse_with_llm(
        self, 
        generated_code: str, 
        actual_code: str
    ) -> Dict[str, Any]:
        """
        使用LLM提取复用信息并评估TP/FP/FN/TN
        
        Args:
            generated_code: 生成的C++代码
            actual_code: 实际的C++代码
            
        Returns:
            包含tp, fp, fn, tn的字典
        """
        prompt = EVALUATOR_PROMPTS["reuse_evaluation"].format(
            actual_code=actual_code,
            generated_code=generated_code,
        )
        
        result = self.agent.invoke_with_structured_output(
            prompt, 
            schema=ReuseEvaluation
        )
        
        # 转换为字典格式
        if isinstance(result, ReuseEvaluation):
            return {
                "tp": result.tp,
                "fp": result.fp,
                "fn": result.fn,
            }
        return result
    
    def calculate_metrics(self, llm_evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算复用感知度指标
        
        Args:
            llm_evaluation: LLM评估结果，包含tp, fp, fn, tn
            
        Returns:
            包含复用感知度指标的字典
        """
        tp = llm_evaluation.get("tp", 0)
        fp = llm_evaluation.get("fp", 0)
        fn = llm_evaluation.get("fn", 0)
        
        # 计算复用感知度指标
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + fn) / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
        }
    
    def analyze_and_compare_function(
        self,
        generated_code: str,
        actual_code: str
    ) -> Dict[str, Any]:
        """
        完整评估流程：LLM评估 -> 计算指标
        
        Args:
            generated_code: 生成的C++代码
            actual_code: 实际的C++代码
            
        Returns:
            完整的分析报告
        """
        # 1. LLM评估复用情况
        llm_evaluation = self.evaluate_reuse_with_llm(generated_code, actual_code)
        
        # 2. 计算指标
        metrics = self.calculate_metrics(llm_evaluation)
        
        return {
            "generated_code": generated_code,
            "actual_code": actual_code,
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1_score": metrics["f1_score"],
            "llm_evaluation": llm_evaluation
        }

if __name__ == "__main__":
    main()