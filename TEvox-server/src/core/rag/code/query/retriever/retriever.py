import json
import os
import numpy as np
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from src.utils import get_llm, get_dashscope_embedding, Agent
from src.base import DefaultConfig
from src.core.rag.code.query.retriever.retriever_prompt import RETRIEVER_PROMPTS

# 数据模型
class QueryDecomposition(BaseModel):
    queries: List[str] = Field(description="分解后的检索查询列表")

class Retriever:
    """
    代码检索器，支持查询分解和embedding检索
    """
    
    def __init__(self):
        """
        初始化检索器
        """
        
        # 初始化embedding模型
        self.embedding_model = get_dashscope_embedding(
            model=DefaultConfig.embedding_model,
        )
        
        # 初始化LLM和Agent
        self.llm = get_llm(
            base_url=DefaultConfig.search_api_base,
            api_key=DefaultConfig.search_api_key,
            model_name=DefaultConfig.search_model,
        )
        self.agent = Agent(self.llm)
        
        # 缓存加载的JSON数 据
        self._cached_data = {}
    def retrieve(self, text: str, json_file_path: str, top_k: int = 5, similarity_threshold: float = 0.3) -> List[str]:
        """
        基于embedding进行相似度检索
        """
        return self.embedding_retrieve(text, json_file_path, top_k, similarity_threshold)

    def query_decompose(self, query: str) -> List[str]:
        """
        将复杂查询分解为多个子查询
        
        Args:
            query: 原始查询字符串
            
        Returns:
            分解后的查询列表
        """
        try:
            prompt = RETRIEVER_PROMPTS["query_decomposition"]["decompose_query"]
            prompt = prompt.format(query=query)
            response = self.agent.invoke_with_structured_output(
                prompt,
                QueryDecomposition
            )
            return response["queries"]
        except Exception as e:
            print(f"Warning: Query decomposition failed: {e}")
            # 如果分解失败，返回原始查询
            return [query]
    
    def embedding_retrieve(
        self, 
        text: str, 
        json_file_path: str, 
        top_k: int = 3,
        similarity_threshold: float = 0.3
    ) -> List[str]:
        """
        基于embedding进行相似度检索
        
        Args:
            text: 输入文本
            json_file_path: JSON文件路径
            top_k: 返回前k个最相似的结果
            similarity_threshold: 相似度阈值，低于此值的结果将被过滤
            
        Returns:
            检索结果列表，按相似度降序排列
        """
        # 1. 获取输入文本的embedding
        query_embedding = self.embedding_model.embed_query(text)
        # print(type(query_embedding),len(query_embedding), type(query_embedding[0]))
        
        # 2. 加载JSON文件数据
        emb_data_dict = self._load_json_data(json_file_path)
        # 3. 计算相似度并排序
        results = []
        for emb_id, emb_data in emb_data_dict.items():  
            # if len(emb_data) != len(query_embedding):
            #     print("embedding length mismatch:", emb_id)
            #     continue
            similarity_score = self._calculate_cosine_similarity(
                query_embedding, 
                emb_data
            )
            
            if similarity_score >= similarity_threshold:
                results.append((emb_id, similarity_score))
        
        # 4. 按相似度降序排序并返回top_k的id
        results.sort(key=lambda x: x[1], reverse=True)
        r = [r[0] for r in results[:top_k]]
        return r
    
    def _load_json_data(self, json_file_path: str) -> Dict[str, Any]:
        """
        从JSON文件加载数据，支持缓存
        
        Args:
            json_file_path: JSON文件路径
            
        Returns:
            节点数据列表
        """
        if json_file_path in self._cached_data:
            return self._cached_data[json_file_path]
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
            
        except Exception as e:
            print(f"Error loading JSON file {json_file_path}: {e}")
            return {}
    
    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算两个向量的余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            余弦相似度分数 (0-1)
        """
        try:
            # 转换为numpy数组
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            # 计算余弦相似度
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)
            
            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0
                
            similarity = dot_product / (norm_v1 * norm_v2)
            return float(similarity)
            
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0.0
    
    def retrieve_with_decomposition(
        self, 
        query: str, 
        json_file_path: str, 
        top_k: int = 10,
        similarity_threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        结合查询分解和embedding检索的完整检索流程
        
        Args:
            query: 原始查询
            json_file_path: JSON文件路径
            top_k: 每个子查询返回的结果数量
            similarity_threshold: 相似度阈值
            
        Returns:
            包含分解查询和检索结果的字典
        """
        # 1. 查询分解
        decomposed_queries = self.query_decompose(query)
        
        # 2. 对每个子查询进行检索
        all_results = []
        query_results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "original_query": query,
                "decomposed_queries": decomposed_queries,
                "total_sub_queries": len(decomposed_queries)
            },
            "results": {}
        }
        
        for i, sub_query in enumerate(decomposed_queries):
            results = self.embedding_retrieve(
                sub_query, 
                json_file_path, 
                top_k, 
                similarity_threshold
            )
            
            query_results["results"][f"sub_query_{i}"] = {
                "query": sub_query,
                "results_count": len(results),
                "results": results
            }
            
            all_results.extend(results)
        
        # 3. 去重和重新排序
        unique_results = self._deduplicate_results(all_results)
        unique_results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        query_results["metadata"]["total_results"] = len(all_results)
        query_results["metadata"]["unique_results"] = len(unique_results)
        query_results["final_results"] = unique_results[:top_k]
        
        return query_results
    
    def _deduplicate_results(self, results: List[str]) -> List[str]:
        """
        对检索结果进行去重
        
        Args:
            results: 检索结果列表
            
        Returns:
            去重后的结果列表
        """
        seen_ids = set()
        unique_results = []
        
        for result in results:
            if result not in seen_ids:
                seen_ids.add(result)
                unique_results.append(result)
        
        return unique_results

def main():
    """测试函数"""
    # 初始化检索器
    retriever = Retriever()
    
    # 测试查询
    test_query = """
        实现ESP32 NVS（Non-Volatile Storage，非易失性存储）系统的键值对配置管理功能，主要提供以下能力：

​​核心功能：​​

1.
​​命名空间管理​​ - 支持在NVS中创建或访问独立的命名空间，实现配置的逻辑隔离
2.
​​数据持久化​​ - 提供字符串和整型数据的可靠存储与读取，保证设备重启后配置不丢失
3.
​​写保护控制​​ - 支持只读和读写两种访问模式，防止意外修改配置数据
4.
​​数据维护​​ - 支持删除单个键值对或清空整个命名空间的所有数据
"""
    json_file_path = ".rag/xiaozhi/designer_output/ssid_manager_design.json"
    
    print("=" * 80)
    print(f"测试查询: {test_query}")
    print("=" * 80)
    
    # 测试查询分解
    print("\n1. 查询分解:")
    decomposed_queries = retriever.query_decompose(test_query)
    for i, query in enumerate(decomposed_queries):
        print(f"  子查询 {i+1}: {query}")
    
    # 测试embedding检索
    print(f"\n2. Embedding检索 (top_k=5):")
    results = retriever.embedding_retrieve(test_query, json_file_path, top_k=5)
    for i, result in enumerate(results):
        print(f"\n  结果 {i+1}:")
        print(f"    ID: {result}")
    
    # 测试完整检索流程
    print(f"\n3. 完整检索流程:")
    full_results = retriever.retrieve_with_decomposition(test_query, json_file_path, top_k=3)
    
    print(f"原始查询: {full_results['metadata']['original_query']}")
    print(f"分解查询数: {full_results['metadata']['total_sub_queries']}")
    print(f"总结果数: {full_results['metadata']['total_results']}")
    print(f"去重后结果数: {full_results['metadata']['unique_results']}")
    
    print("\n最终结果:")
    for i, result in enumerate(full_results['final_results']):
        print(f"  {i+1}. {result}")

if __name__ == "__main__":
    from src.utils import get_dashscope_embedding
    input_texts = "ESP32 NVS（Non-Volatile Storage，非易失性存储）系统的键值对配置管理功能"

    embedding_model_v1 = get_dashscope_embedding(
        model=DefaultConfig.embedding_model,
    )
    embedding_v1 = embedding_model_v1.embed_query(input_texts)

    print(type(embedding_v1),len(embedding_v1), type(embedding_v1[0]))