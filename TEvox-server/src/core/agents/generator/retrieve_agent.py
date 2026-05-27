import json
import networkx as nx
from typing import List, Dict, Any, Set, Tuple
from collections import deque
from dataclasses import dataclass
from src.core.agents.generator.document_extractor import read_graph_from_json
from src.utils import get_llm, Agent
from src.base import DefaultConfig

@dataclass
class ExplorationStep:
    """探索步骤记录"""
    node_id: str
    depth: int
    reason: str
    action: str  # "explore", "answer", "skip"

@dataclass
class RetrievalResult:
    """检索结果"""
    answer_nodes: List[str]
    exploration_path: List[ExplorationStep]
    total_explored: int
    max_depth_reached: int

class RetrieveAgent:
    """基于LLM的图节点检索代理"""
    
    def __init__(self, graph_json_path: str = "graph_with_knowledge_blocks.json"):
        """
        初始化检索代理
        
        Args:
            graph_json_path: 图数据JSON文件路径
        """
        self.graph = read_graph_from_json(graph_json_path)
        if self.graph is None:
            raise ValueError(f"Failed to load graph from {graph_json_path}")
        
        # 初始化LLM
        self.llm = get_llm(
            model_name=DefaultConfig.agent_model,
        )
        self.agent = Agent(self.llm)
        
        # 探索记录
        self.exploration_path: List[ExplorationStep] = []
        self.explored_nodes: Set[str] = set()
        self.answer_nodes: Set[str] = set()
        
    def should_explore_neighbor(self, neighbor_id: str, current_node_id: str, query: str) -> Tuple[bool, str]:
        """
        使用LLM判断是否应该探索邻居节点
        
        Args:
            neighbor_id: 邻居节点ID
            current_node_id: 当前节点ID
            query: 查询问题
            
        Returns:
            (should_explore, reason): 是否应该探索及理由
        """
        neighbor_doc = self.graph.nodes[neighbor_id].get('documentation', '')
        current_doc = self.graph.nodes[current_node_id].get('documentation', '')
        
        prompt = f"""
你是一个代码分析专家。请根据以下信息判断是否应该探索邻居节点。

查询问题：{query}

当前节点：{current_node_id}
当前节点文档：{current_doc[:500]}...

邻居节点：{neighbor_id}
邻居节点文档：{neighbor_doc[:500]}...

请判断：基于当前节点和查询问题，探索这个邻居节点是否有助于找到答案？

考虑因素：
1. 邻居节点是否与查询问题相关
2. 邻居节点是否可能包含查询所需的信息
3. 从当前节点到邻居节点的关系是否有助于理解查询问题

请返回JSON格式：
{{
    "should_explore": true/false,
    "reason": "详细的判断理由"
}}
"""
        
        try:
            response = self.agent.invoke_with_structured_output(prompt, {
                "type": "object",
                "properties": {
                    "should_explore": {"type": "boolean"},
                    "reason": {"type": "string"}
                },
                "required": ["should_explore", "reason"]
            })
            
            return response.get("should_explore", False), response.get("reason", "无法判断")
        except Exception as e:
            print(f"Error in should_explore_neighbor: {e}")
            return False, f"LLM判断失败: {e}"
    
    def can_answer_query(self, node_id: str, query: str) -> Tuple[bool, str]:
        """
        使用LLM判断节点是否能回答查询问题
        
        Args:
            node_id: 节点ID
            query: 查询问题
            
        Returns:
            (can_answer, reason): 是否能回答及理由
        """
        node_doc = self.graph.nodes[node_id].get('documentation', '')
        node_body = self.graph.nodes[node_id].get('body', '')
        
        prompt = f"""
你是一个代码分析专家。请根据以下信息判断该节点是否能回答查询问题。

查询问题：{query}

节点：{node_id}
节点代码：{node_body}
节点文档：{node_doc}

请判断：这个节点的文档和代码是否包含足够的信息来回答查询问题？

考虑因素：
1. 节点文档是否直接回答了查询问题
2. 节点代码是否实现了查询问题相关的功能
3. 节点是否包含查询问题所需的关键信息

请返回JSON格式：
{{
    "can_answer": true/false,
    "reason": "详细的判断理由"
}}
"""
        
        try:
            response = self.agent.invoke_with_structured_output(prompt, {
                "type": "object",
                "properties": {
                    "can_answer": {"type": "boolean"},
                    "reason": {"type": "string"}
                },
                "required": ["can_answer", "reason"]
            })
            
            return response.get("can_answer", False), response.get("reason", "无法判断")
        except Exception as e:
            print(f"Error in can_answer_query: {e}")
            return False, f"LLM判断失败: {e}"
    
    def retrieve_relevant_nodes(self, query: str, start_node: str = "void WifiStation::Start()", 
                              max_depth: int = 3, max_explored: int = 20) -> RetrievalResult:
        """
        检索与查询相关的节点
        
        Args:
            query: 查询问题
            start_node: 起始节点ID
            max_depth: 最大探索深度
            max_explored: 最大探索节点数
            
        Returns:
            RetrievalResult: 检索结果
        """
        # 重置状态
        self.exploration_path = []
        self.explored_nodes = set()
        self.answer_nodes = set()
        
        # 检查起始节点是否存在
        if start_node not in self.graph.nodes:
            raise ValueError(f"Start node '{start_node}' not found in graph")
        
        # 使用BFS进行探索
        queue = deque([(start_node, 0)])  # (node_id, depth)
        
        while queue and len(self.explored_nodes) < max_explored:
            current_node, depth = queue.popleft()
            
            if current_node in self.explored_nodes or depth > max_depth:
                continue
            
            # 标记为已探索
            self.explored_nodes.add(current_node)
            
            # 判断当前节点是否能回答查询
            can_answer, answer_reason = self.can_answer_query(current_node, query)
            
            if can_answer:
                self.answer_nodes.add(current_node)
                self.exploration_path.append(ExplorationStep(
                    node_id=current_node,
                    depth=depth,
                    reason=answer_reason,
                    action="answer"
                ))
                print(f"✓ Found answer node: {current_node} (depth {depth})")
                print(f"  Reason: {answer_reason}")
            else:
                self.exploration_path.append(ExplorationStep(
                    node_id=current_node,
                    depth=depth,
                    reason=answer_reason,
                    action="explore"
                ))
                print(f"○ Explored node: {current_node} (depth {depth})")
                print(f"  Reason: {answer_reason}")
            
            # 如果达到最大深度，不再探索邻居
            if depth >= max_depth:
                continue
            
            # 获取邻居节点
            neighbors = list(self.graph.successors(current_node)) + list(self.graph.predecessors(current_node))
            
            for neighbor in neighbors:
                if neighbor not in self.explored_nodes:
                    # 使用LLM判断是否应该探索这个邻居
                    should_explore, explore_reason = self.should_explore_neighbor(neighbor, current_node, query)
                    
                    if should_explore:
                        queue.append((neighbor, depth + 1))
                        print(f"  → Will explore neighbor: {neighbor}")
                        print(f"    Reason: {explore_reason}")
                    else:
                        self.exploration_path.append(ExplorationStep(
                            node_id=neighbor,
                            depth=depth + 1,
                            reason=explore_reason,
                            action="skip"
                        ))
                        print(f"  → Skipped neighbor: {neighbor}")
                        print(f"    Reason: {explore_reason}")
        
        return RetrievalResult(
            answer_nodes=list(self.answer_nodes),
            exploration_path=self.exploration_path,
            total_explored=len(self.explored_nodes),
            max_depth_reached=max(depth for _, depth in queue) if queue else max_depth
        )
    
    def print_exploration_summary(self, result: RetrievalResult):
        """打印探索摘要"""
        print("\n" + "="*60)
        print("EXPLORATION SUMMARY")
        print("="*60)
        print(f"Query: {getattr(self, '_current_query', 'Unknown')}")
        print(f"Start node: {getattr(self, '_start_node', 'Unknown')}")
        print(f"Total nodes explored: {result.total_explored}")
        print(f"Answer nodes found: {len(result.answer_nodes)}")
        print(f"Max depth reached: {result.max_depth_reached}")
        
        print(f"\nAnswer nodes:")
        for node in result.answer_nodes:
            print(f"  - {node}")
        
        print(f"\nExploration path:")
        for step in result.exploration_path:
            action_symbol = {"explore": "○", "answer": "✓", "skip": "✗"}[step.action]
            print(f"  {action_symbol} {step.node_id} (depth {step.depth})")
            print(f"    {step.reason}")
    
    def save_result_to_json(self, result: RetrievalResult, output_path: str = "retrieval_result.json"):
        """保存检索结果到JSON文件"""
        output_data = {
            "query": getattr(self, '_current_query', 'Unknown'),
            "start_node": getattr(self, '_start_node', 'Unknown'),
            "answer_nodes": result.answer_nodes,
            "total_explored": result.total_explored,
            "max_depth_reached": result.max_depth_reached,
            "exploration_path": [
                {
                    "node_id": step.node_id,
                    "depth": step.depth,
                    "reason": step.reason,
                    "action": step.action
                }
                for step in result.exploration_path
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nResult saved to: {output_path}")


def main():
    """主函数 - 测试检索代理"""
    # 从ground_truth_template.json读取查询
    with open("ground_truth_template.json", 'r', encoding='utf-8') as f:
        ground_truth_data = json.load(f)
    
    # 选择第 个查询进行测试
    test_query = ground_truth_data["queries"][0]["query"]
    expected_nodes = ground_truth_data["queries"][0]["ground_truth"]
    
    print(f"Testing query: {test_query}")
    print(f"Expected nodes: {expected_nodes}")
    print("-" * 60)
    
    # 创建检索代理
    agent = RetrieveAgent()
    agent._current_query = test_query
    agent._start_node = "void WifiStation::Start()"
    
    # 执行检索
    result = agent.retrieve_relevant_nodes(
        query=test_query,
        start_node="void WifiStation::Start()",
        max_depth=3,
        max_explored=15
    )
    
    # 打印结果
    agent.print_exploration_summary(result)
    
    # 保存结果
    agent.save_result_to_json(result)
    
    # 评估结果
    found_nodes = set(result.answer_nodes)
    expected_set = set(expected_nodes)
    
    precision = len(found_nodes & expected_set) / len(found_nodes) if found_nodes else 0
    recall = len(found_nodes & expected_set) / len(expected_set) if expected_set else 0
    
    print(f"\nEVALUATION:")
    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"Found: {found_nodes}")
    print(f"Expected: {expected_set}")
    print(f"Correct: {found_nodes & expected_set}")
    print(f"Missing: {expected_set - found_nodes}")
    print(f"Extra: {found_nodes - expected_set}")


if __name__ == "__main__":
    main()
