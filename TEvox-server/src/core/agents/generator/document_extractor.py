import json
import os
from datetime import datetime
from src.core.agents.generator.graph_builder import get_incoming_nodes, get_outgoing_nodes, dfs_pre_order, graph, KnowledgeItem, Evidence
import pickle
from typing import List, Dict, Any, Optional
from src.utils import get_embedding
from src.base import DefaultConfig
RETRY_COUNT = 3

# Initialize embedding model
try:
    EMBEDDING_MODEL = get_embedding(
        model_name=DefaultConfig.embedding_model,
        openai_api_base=DefaultConfig.embedding_api_base,
        openai_api_key=DefaultConfig.embedding_api_key,
    )
except Exception as e:
    print(f"Warning: Failed to initialize embedding model: {e}")
    EMBEDDING_MODEL = None

def get_context_for_question(question: str, top_k: int = 5, min_similarity: float = 0.3) -> str:
    """
    Retrieve relevant context for a given question using embedding-based similarity search.
    
    Args:
        question (str): The question to find context for
        top_k (int): Number of top similar nodes to retrieve
        min_similarity (float): Minimum similarity threshold (0-1)
        
    Returns:
        str: Concatenated context from relevant nodes
    """
    try:
        # Check if embedding model is available
        if EMBEDDING_MODEL is None:
            return "Embedding model not available for context retrieval."
        
        # Check if graph is available and has nodes
        if not hasattr(graph, 'nodes') or len(graph.nodes) == 0:
            return "No graph data available for context retrieval."
        
        # Generate embedding for the question
        question_embedding = EMBEDDING_MODEL.embed_query(question)
        
        # Get all nodes from the graph
        all_nodes = list(graph.nodes(data=True))
        
        # Calculate similarities and collect relevant nodes
        node_similarities = []
        
        for node_id, node_data in all_nodes:
            # Get node content for similarity calculation
            node_content = ""
            
            # Combine different content sources for better matching
            if 'body' in node_data:
                node_content += node_data['body'] + " "
            
            if 'documentation' in node_data:
                node_content += node_data['documentation'] + " "
                
            if 'knowledge_blocks' in node_data:
                for kb in node_data['knowledge_blocks']:
                    if hasattr(kb, 'question') and kb.question:
                        node_content += kb.question + " "
                    if hasattr(kb, 'conclusion') and kb.conclusion:
                        node_content += kb.conclusion + " "
            
            if not node_content.strip():
                continue
                
            # Generate embedding for node content
            try:
                node_embedding = EMBEDDING_MODEL.embed_query(node_content)
                
                # Calculate cosine similarity
                similarity = _cosine_similarity(question_embedding, node_embedding)
                
                if similarity >= min_similarity:
                    node_similarities.append({
                        'node_id': node_id,
                        'similarity': similarity,
                        'content': node_content,
                        'node_data': node_data
                    })
                    
            except Exception as e:
                # Skip nodes that fail embedding generation
                continue
        
        # Sort by similarity and get top_k results
        node_similarities.sort(key=lambda x: x['similarity'], reverse=True)
        top_nodes = node_similarities[:top_k]
        
        # Build context string
        context_parts = []
        
        if not top_nodes:
            return f"No relevant context found for question: {question}"
        
        for i, node_info in enumerate(top_nodes, 1):
            node_id = node_info['node_id']
            similarity = node_info['similarity']
            content = node_info['content']
            
            context_parts.append(f"=== Relevant Node {i} (Similarity: {similarity:.3f}) ===")
            context_parts.append(f"Node ID: {node_id}")
            context_parts.append(f"Content: {content.strip()}")
            context_parts.append("")
        
        # Also include neighboring nodes for broader context
        neighbor_context = _get_neighbor_context(top_nodes)
        if neighbor_context:
            context_parts.append("=== Neighboring Context ===")
            context_parts.append(neighbor_context)
            context_parts.append("")
        
        return "\n".join(context_parts)
        
    except Exception as e:
        # Log the error and return a fallback context
        log_llm_interaction(
            f"Error in get_context_for_question for question: {question}",
            f"Error: {str(e)}",
            "context_retrieval",
            "error"
        )
        return f"Error retrieving context: {str(e)}"

def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        float: Cosine similarity score between 0 and 1
    """
    import math
    
    if len(vec1) != len(vec2):
        return 0.0
    
    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    
    # Calculate vector norms
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    
    # Avoid division by zero
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    
    return dot_product / (norm1 * norm2)

def _get_neighbor_context(top_nodes: List[Dict[str, Any]], max_neighbors: int = 3) -> str:
    """
    Get context from neighboring nodes of the top similar nodes.
    
    Args:
        top_nodes: List of top similar nodes
        max_neighbors: Maximum number of neighbors to include per node
        
    Returns:
        str: Context from neighboring nodes
    """
    neighbor_context_parts = []
    
    for node_info in top_nodes:
        node_id = node_info['node_id']
        
        # Get incoming and outgoing neighbors
        incoming_nodes = get_incoming_nodes(graph, node_id)
        outgoing_nodes = get_outgoing_nodes(graph, node_id)
        
        # Combine and limit neighbors
        all_neighbors = list(set(incoming_nodes + outgoing_nodes))[:max_neighbors]
        
        for neighbor_id in all_neighbors:
            if neighbor_id in graph.nodes:
                neighbor_data = graph.nodes[neighbor_id]
                neighbor_content = ""
                
                if 'body' in neighbor_data:
                    neighbor_content += neighbor_data['body']
                
                if neighbor_content.strip():
                    neighbor_context_parts.append(f"Neighbor {neighbor_id}: {neighbor_content.strip()}")
    
    return "\n".join(neighbor_context_parts)

def log_llm_interaction(prompt, response, node_id, interaction_type):
    """记录LLM的输入输出到文件
    
    Args:
        prompt (str): 输入的prompt
        response (str/object): LLM的响应（可能是字符串或结构化对象）
        node_id (str, optional): 当前处理的节点ID
        interaction_type (str, optional): 交互类型（如'question_generation', 'validation', 'documentation'）
    """
    # 创建logs目录（如果不存在）
    log_dir = "llm_interaction_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 生成日志文件名（使用日期）
    current_date = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"llm_interactions_{current_date}_{hash(node_id)}.jsonl")
    
    # 准备日志内容
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "node_id": node_id,
        "interaction_type": interaction_type,
        "prompt": prompt,
        "response": response if isinstance(response, str) else response.dict() if hasattr(response, 'dict') else str(response)
    }
    
    # 追加写入日志文件
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

from src.utils import get_llm, Agent
from src.base import DefaultConfig
LLM = get_llm(
    model_name=DefaultConfig.agent_model,
)
# LLM = get_llm(
#     model_name=DefaultConfig.agent_model,
#     api_key=DefaultConfig.agent_api_key,
#     base_url=DefaultConfig.agent_api_base,
# )

class CustomAgent(Agent):
    """扩展Agent类以添加日志记录功能"""
    def __init__(self, llm, node_id=None):
        super().__init__(llm)
        self.node_id = node_id
    
    def invoke_with_logging(self, input, interaction_type):
        """带日志记录的invoke方法"""
        response = super().invoke(input)
        if interaction_type is not None:
            log_llm_interaction(input, response, self.node_id, interaction_type)
        return response
    
    def invoke_with_structured_output_and_logging(self, input, schema, interaction_type):
        """带日志记录的invoke_with_structured_output方法"""
        response = super().invoke_with_structured_output(input, schema)
        if interaction_type is not None:
            log_llm_interaction(input, response, self.node_id, interaction_type)
        return response

def generate_causal_hypothesis(node, current_question_list):
    """生成新的因果假设问题，确保不重复且语义不重复"""
    
    prompt = f"""
你是一个代码分析专家。请为节点 {node} 生成深入的因果逻辑问题，目标是理解代码的设计意图、执行流程和潜在问题。

当前节点内容：
{graph.nodes[node].get('body', '')}

已存在的问题（避免重复）：
{chr(10).join(current_question_list)}

请从以下6个维度系统性地分析代码，生成可验证的因果假设问题：

## 1. 实现流程与执行逻辑
- 这个函数的完整执行流程是什么？每个步骤的触发条件和执行顺序？
- 不同的执行路径分别对应什么场景？路径之间的优先级和互斥关系如何？
- 执行过程中可能出现的中断、异常或提前返回的情况有哪些？

## 2. 数据流分析（前因后果）
- 数据的来源是什么？从哪里获取？通过什么方式获取？
- 数据在函数内部如何流转？经过哪些处理步骤？
- 数据的去向是什么？如何输出？输出到哪里？
- 什么条件下数据流会发生？数据流的影响范围是什么？
- 数据流中断或异常时会产生什么后果？

## 3. 控制流分析（前因后果）
- 控制流的来源是什么？谁决定了执行路径？
- 控制流的去向是什么？会影响哪些后续操作？
- 什么条件下控制流会发生转移？转移的触发机制是什么？
- 控制流的影响范围是什么？会影响到哪些其他组件？
- 控制流异常时的恢复机制是什么？

## 4. External Dependencies（外部依赖）
- 依赖了哪些外部组件、库或系统资源？
- 这些外部依赖的可用性如何影响当前函数的行为？
- 外部依赖失败时的处理策略是什么？
- 如何确保外部依赖的正确性和时序？

## 5. Internal Dependencies（内部依赖）
- 调用了哪些其他函数/组件？调用的时机和条件？
- 被哪些其他函数/组件调用？调用的上下文是什么？
- 与其他组件的协作模式和通信机制？
- 内部依赖的故障传播机制是什么？

## 6. 功能职责与设计意图
- 这个函数的核心职责是什么？为什么要这样设计？
- 在整个系统中扮演什么角色？解决了什么问题？
- 设计的权衡考虑是什么？有哪些潜在的设计缺陷？
- 状态管理和副作用如何确保正确性？

要求：
1. 每个问题都要具体且可通过代码验证
2. 问题要探索具体的因果关系链，特别关注数据流和控制流的前因后果
3. 避免与已存在问题语义重复
4. 优先生成能够揭示潜在问题和深层逻辑的问题
5. 如果某个维度没有相关问题，跳过该维度

输出格式：每行一个问题，按维度分组，不要有额外说明。如果没有新问题，返回空。

请生成新的问题：
"""

    agent = CustomAgent(LLM, node_id=node)
    response = agent.invoke_with_logging(prompt, "question_generation")
    
    # 解析问题，每行一个
    new_questions = [q.strip() for q in response.strip().split('\n') if q.strip()]

    # 使用LLM判断语义相似性，去除与current_question_list语义重复的问题
    if not new_questions:
        return []

    dedup_prompt = f"""
你是一个因果问题去重专家。请根据已存在的问题列表，对新生成的问题列表进行语义去重，去除与已存在问题语义相似或关注同一因果链的问题，仅保留与已存在问题关注点不同的新问题。

已存在的问题列表：
{chr(10).join(current_question_list) if current_question_list else "无"}

新生成的问题列表：
{chr(10).join(new_questions)}

判断标准：
1. 问题探索的因果关系链是否相同（特别关注数据流和控制流的前因后果）
2. 问题关注的代码部分和逻辑是否重叠
3. 问题的验证方法和证据来源是否一致
4. 问题分析的流程维度是否相同（实现流程/数据流/控制流/依赖关系等）

请返回最终去重后的新问题列表，每行一个问题，不要有任何额外说明或解释。如果没有可保留的新问题，请返回空。
"""

    dedup_agent = CustomAgent(LLM, node_id=node)
    dedup_response = dedup_agent.invoke_with_logging(dedup_prompt, "question_semantic_deduplication")
    deduplicated_new_questions = [q.strip() for q in dedup_response.strip().split('\n') if q.strip()]

    return deduplicated_new_questions

def validate_in_context(question, context_info, context_node_list, current_node):
    """在上下文中验证问题，返回Evidence对象"""
    
    validation_prompt = f"""
你是一个专业的代码分析专家。请根据以下信息，判断是否能够找到足够的证据来回答给定的问题。

当前节点内容：
{graph.nodes[current_node].get('body', '')}

上下文信息：
{context_info}

问题：
{question}

请仔细分析：
1. 当前节点和上下文中是否包含回答这个问题所需的信息
2. 证据是否充分且可信
3. 是否能够建立完整的因果关系链
4. 可以基于上下文节点中已验证的因果关系来构建证据

请提供你的判断结果，格式如下：
```json
{{
    "valid": true/false,
    "content": "简略的证据描述，包括涉及到的代码片段、逻辑关系等",
    "source": {','.join(context_node_list)}
}}
```
"""

    agent = CustomAgent(LLM, node_id=current_node)
    result = agent.invoke_with_structured_output_and_logging(validation_prompt, Evidence, "context_validation")
    
    return result

def validate_node_by_question_block(node):
    """基于问题块的验证函数"""
    # 获取上下文节点
    upstream_nodes = get_incoming_nodes(graph, node)  # 调用我的节点 + 引用我的节点
    downstream_nodes = get_outgoing_nodes(graph, node)  # 我调用的节点 + 我引用的节点
    context_node_list = upstream_nodes + downstream_nodes
    
    # 直接构建上下文字符串信息
    context_info = ""
    
    # 添加当前节点信息
    context_info += f"当前节点: {node}\n"
    context_info += f"内容: {graph.nodes[node].get('body', '')}\n\n"
    
    # 添加上下文节点中已经达成因果链闭环的问题+结论
    for ctx_node in context_node_list:
        context_info += f"节点: {ctx_node}\n"
        context_info += f"内容: {graph.nodes[ctx_node].get('body', '')}\n"
        
        # 获取该节点已经闭环的知识块
        closed_knowledge_blocks = [item for item in graph.nodes[ctx_node].get("knowledge_blocks", []) if item.causal_chain_closed]
        
        if closed_knowledge_blocks:
            context_info += "已验证的因果关系:\n"
            for item in closed_knowledge_blocks:
                context_info += f"  问题: {item.question}\n"
                context_info += f"  结论: {item.conclusion}\n"
                context_info += "\n"
        else:
            context_info += "暂无已验证的因果关系\n"
        
        context_info += "\n"
    
    # 获取当前所有问题列表（用于去重）
    current_question_list = [item.question for item in graph.nodes[node]["knowledge_blocks"]]
    
    # 生成新的因果假设问题（已去重）
    new_question_list = generate_causal_hypothesis(node, current_question_list)
    
    # 直接添加新问题到知识块（已确保不重复）
    for question in new_question_list:
        graph.nodes[node]["knowledge_blocks"].append(KnowledgeItem(
            question=question,
            evidence=None,
            conclusion=None,
            causal_chain_closed=False
        ))
    
    # 验证所有待验证问题(未闭环且未搁置的问题)
    questions_to_validate = [
        item.question for item in graph.nodes[node]["knowledge_blocks"] 
        if not item.causal_chain_closed and not item.is_suspended
    ]
    
    for question in questions_to_validate:
        # 找到对应的知识块项
        knowledge_item = None
        for item in graph.nodes[node]["knowledge_blocks"]:
            if item.question == question:
                knowledge_item = item
                break
        
        if knowledge_item is None:
            continue
            
        # 增加验证尝试次数
        knowledge_item.validation_attempts += 1
        
        evidence = validate_in_context(question, context_info, context_node_list, node)
        
        if evidence is not None and evidence.get("valid", False):
            knowledge_item.evidence = evidence.get("content")
            knowledge_item.conclusion = "验证通过"
            knowledge_item.causal_chain_closed = True
        else:
            knowledge_item.evidence = evidence.get("content") if evidence else None
            knowledge_item.conclusion = "未验证"
            
            # 检查是否达到最大尝试次数
            if knowledge_item.validation_attempts >= knowledge_item.max_attempts:
                knowledge_item.is_suspended = True
                knowledge_item.conclusion = f"搁置状态（尝试{knowledge_item.validation_attempts}次后未通过）"
                print(f"Question suspended after {knowledge_item.validation_attempts} attempts: {question}")
    
    return len(questions_to_validate) > 0

def validate_node_by_document(node):
    """基于文档的验证函数"""
    # 确保节点有文档字段
    generate_node_documentation(node)
    for i in range(RETRY_COUNT):
        isvalidated = validate_causal_chains_from_documentation(node)
        if(isvalidated):
            break
        else:
            generate_node_documentation(node)
    return isvalidated

def generate_node_documentation(node):
    """为节点生成详细文档"""
    
    # 获取上下文节点
    outgoing_nodes = get_outgoing_nodes(graph, node)
    incoming_nodes = get_incoming_nodes(graph, node)
    
    # 构建上下文信息
    outgoing_context = ""
    for out_node in outgoing_nodes:
        outgoing_context += f"节点: {out_node}\n"
        outgoing_context += f"代码: {graph.nodes[out_node].get('body', '')}\n\n"
        # 实验发现，不需要相邻节点的文档信息也能验证因果链，且，文档信息会影响当前代码块的文档的输出，所以暂时不使用相邻节点的文档信息
        #outgoing_context += f"文档: {graph.nodes[out_node].get('documentation', '')}\n\n"
    
    incoming_context = ""
    for in_node in incoming_nodes:
        incoming_context += f"节点: {in_node}\n"
        incoming_context += f"代码: {graph.nodes[in_node].get('body', '')}\n\n"
        #incoming_context += f"文档: {graph.nodes[in_node].get('documentation', '')}\n\n"
    
    generate_document_prompt = """
当前代码块的名称：
{node_name}

当前代码块的内容：
{code}

当前代码块的文档：
{docs}    
    
当前代码块引用或者调用的其它代码块:
{outgoing_nodes}

引用或者调用当前代码块的其它代码块：
{incoming_nodes}

当前代码块的未验证的因果链：
{unvalidated_causal_chains}

为了深度理解当前代码块及其上下文, 请为其写一个更细化的文档（根据上下文中的证据来写，不要编造内容）。要理解实现了什么，如何实现的。深入理解其前因后果（前置条件、后置影响），数据流和控制流（要根据引用/调用，被引用/被调用的代码块的内容，在更大的范围内即多个代码块内描述完整的流程）等。注意，当前代码块的名称是：{node_name}，文档模板如下：
### 全部的实现流程
### 全部的数据流（描述数据流的来源，去向， 内容，什么条件下数据流会发生，数据流的影响范围是什么，即前因后果）
### 全部的控制流 (描述控制流的来源，去向，内容，什么条件下控制流会发生，控制流的影响范围是什么，即前因后果)
### 全部的External Dependencies
### 全部的Internal Dependencies
### 全部的功能职责
""".format(
        node_name=node,
        code=graph.nodes[node].get('body', ''),
        docs=graph.nodes[node].get('documentation', ''),
        outgoing_nodes=outgoing_context,
        incoming_nodes=incoming_context, 
        unvalidated_causal_chains=graph.nodes[node].get('unvalidated_causal_chains', '')
    )
    
    agent = CustomAgent(LLM, node_id=node)
    documentation = agent.invoke_with_logging(generate_document_prompt, "documentation_generation")
    
    # 保存文档
    graph.nodes[node]["documentation"] = documentation
    
    return documentation

def validate_causal_chains_from_documentation(node):
    """基于文档验证因果链"""
    
    # 步骤1：让LLM基于文档提出因果链
    documentation = graph.nodes[node]["documentation"]
    causal_chain_prompt = f"""
基于以下节点文档，请提出具体的因果链假设。每个因果链应该描述一个明确的因果关系。

节点文档：
{documentation}

请提出因果链假设，格式为：
因果链1：[前置条件] → [触发事件] → [后果/影响]
因果链2：[前置条件] → [触发事件] → [后果/影响]
...

要求：
1. 每个因果链都要具体可验证
2. 基于文档中的证据，不要编造
3. 关注数据流和控制流的因果关系
4. 每行一个因果链，不要有额外说明

请提出因果链：
"""
    
    agent = CustomAgent(LLM, node_id=node)
    causal_chains_response = agent.invoke_with_logging(causal_chain_prompt, "causal_chain_generation")
    
    # 解析因果链
    causal_chains = [line.strip() for line in causal_chains_response.strip().split('\n') if line.strip()]
    
    # 步骤2：验证每个因果链
    unvalidated_chains = []
    
    for chain in causal_chains:
        # 获取上下文信息进行验证
        code_context_info = get_code_context_for_validation(node)
        
        validation_prompt = f"""
你是一个代码分析专家。请根据以下信息，验证这个因果链是否符合代码图的上下文。

待验证的因果链：
{chain}

当前节点内容：
{graph.nodes[node].get('body', '')}

上下文信息：
{code_context_info}

请判断：
1. 这个因果链是否有足够的代码证据支持？
2. 前置条件、触发事件、后果/影响是否在代码中能找到对应的实现？
3. 因果关系是否符合代码的实际逻辑？

请提供你的判断结果，格式如下：
```json
{{
    "valid": true/false,
    "content": "简略的证据描述，包括涉及到的代码片段、逻辑关系等",
    "source": "验证的推理过程"
}}
```
"""
        
        validation_result = agent.invoke_with_structured_output_and_logging(
            validation_prompt, Evidence, "causal_chain_validation"
        )
        
        if validation_result.get("valid", False):
            unvalidated_chains.append({
                "chain": chain,
                "evidence": validation_result.get("content", ""),
                "reasoning": validation_result.get("source", "")
            })
    graph.nodes[node]["unvalidated_causal_chains"] = unvalidated_chains
    return len(unvalidated_chains) > 0

def get_code_context_for_validation(node):
    """获取用于验证的上下文信息"""
    upstream_nodes = get_incoming_nodes(graph, node)
    downstream_nodes = get_outgoing_nodes(graph, node)
    context_node_list = upstream_nodes + downstream_nodes
    
    context_info = ""
    for ctx_node in context_node_list:
        context_info += f"节点: {ctx_node}\n"
        context_info += f"内容: {graph.nodes[ctx_node].get('body', '')}\n"
        context_info += "\n"
    
    return context_info

def is_node_validated_by_question_block(node):
    """检查基于问题块的验证是否完成"""
    all_questions = graph.nodes[node]["knowledge_blocks"]
    completed_questions = [item for item in all_questions if item.causal_chain_closed or item.is_suspended]
    return len(completed_questions) == len(all_questions)

def print_validation_status_by_question_block(node):
    """输出基于问题块的验证状态"""
    print(f"Node: {node}")
    all_questions = graph.nodes[node].get('knowledge_blocks', [])
    
    # 已闭环的问题
    closed_questions = [item.question for item in all_questions if item.causal_chain_closed]
    print(f"已闭环的问题: {closed_questions}")
    
    # 未闭环且未搁置的问题（活跃问题）
    active_questions = [item.question for item in all_questions if not item.causal_chain_closed and not item.is_suspended]
    print(f"未闭环的问题: {active_questions}")
    
    # 已搁置的问题
    suspended_questions = [f"{item.question} (尝试{item.validation_attempts}次)" for item in all_questions if item.is_suspended]
    print(f"已搁置的问题: {suspended_questions}")
    
    print("-" * 100)

def print_validation_status_by_document(node):
    """输出基于文档的验证状态"""
    print(f"Node: {node}") 
    print("documentation: ", graph.nodes[node].get("documentation", ""))

# 统一的验证回调函数
def validation_callback(node):
    """统一的验证回调函数，根据策略选择执行不同的验证逻辑"""
    # 如果节点已经通过验证，则跳过
    if node in validated_nodes:
        return

    # 检查验证完成条件（根据当前策略）
    if current_validate_function(node):
        print(f"Node {node} validation completed successfully")
        validated_nodes.add(node)
    else:
        print(f"Node {node} still needs validation")

# ================== 策略选择 ==================
# 选择验证策略（只需要修改这几行来切换策略）

# # 策略1: 基于问题块的验证
# current_validate_function = validate_node_by_question_block
# current_is_validated_function = is_node_validated_by_question_block
# current_print_status_function = print_validation_status_by_question_block

#策略2: 基于文档的验证
current_validate_function = validate_node_by_document
# current_is_validated_function = is_node_validated_by_document
current_print_status_function = print_validation_status_by_document

# ================== 主循环 ==================

validated_nodes = set()
def traverse_graph():

    while True:
        print("\nDFS Pre-order Traversal:")
        visited_nodes = set()

        for root in graph.nodes:
            if graph.in_degree(root) == 0:  # 找到根节点
                dfs_pre_order(graph, root, visited_nodes, callback=validation_callback)

        # 检查是否所有节点都已通过验证
        if len(validated_nodes) == len(graph.nodes): 
            print("All nodes validated successfully!")
            break
        else:
            print(f"Validation incomplete. {len(validated_nodes)}/{len(graph.nodes)} nodes validated.")
            print("validated_nodes: ", validated_nodes)
            
            # 输出所有节点的验证状态（根据当前策略）
            for node in graph.nodes:
                current_print_status_function(node)
            
            user_input = input("Try again? (y/n): ")
            if user_input.lower() != 'y':
                break
            break
    # 保存graph到文件
    with open("graph_with_knowledge_blocks.pkl", "wb") as f:
        pickle.dump(graph, f)
    print("Graph saved to graph_with_knowledge_blocks.pkl")



def read_graph_and_output_documentation(pickle_file_path="graph_with_knowledge_blocks.pkl", json_output_path="graph_with_knowledge_blocks.json"):
    """读取pickle文件中的graph并输出其中的文档，并将graph以json格式保存
    
    Args:
        pickle_file_path (str): pickle文件路径，默认为"graph_with_knowledge_blocks.pkl"
        json_output_path (str): 输出的json文件路径，默认为"graph_with_knowledge_blocks.json"
    """
    import networkx as nx
    def node_to_serializable(node_data):
        # 处理节点数据为可序列化格式
        result = {}
        for k, v in node_data.items():
            if k == "knowledge_blocks":
                # knowledge_blocks为对象列表，转为dict
                result[k] = [item.__dict__ if hasattr(item, "__dict__") else str(item) for item in v]
            elif k == "unvalidated_causal_chains":
                # 直接转为list/dict
                result[k] = v
            else:
                try:
                    json.dumps(v)
                    result[k] = v
                except Exception:
                    result[k] = str(v)
        return result

    try:
        # 读取pickle文件
        with open(pickle_file_path, "rb") as f:
            loaded_graph = pickle.load(f)
        print(f"Successfully loaded graph from {pickle_file_path}")
        print(f"Graph contains {len(loaded_graph.nodes)} nodes")
        print("=" * 80)

        # 遍历所有节点并输出文档
        for node_id in loaded_graph.nodes:
            node_data = loaded_graph.nodes[node_id]
            documentation = node_data.get('documentation', '')
            if documentation:
                print(f"Node: {node_id}")
                print("-" * 40)
                print(f"Documentation:\n{documentation}")
                print("=" * 80)
            else:
                print(f"Node: {node_id} - No documentation available")
                print("-" * 40)

        # 输出为json格式
        graph_json = {
            "nodes": [
                {"id": node_id, **node_to_serializable(loaded_graph.nodes[node_id])}
                for node_id in loaded_graph.nodes
            ],
            "edges": [
                {"source": u, "target": v, **loaded_graph.edges[u, v]} if loaded_graph.edges[u, v] else {"source": u, "target": v}
                for u, v in loaded_graph.edges
            ]
        }
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(graph_json, f, ensure_ascii=False, indent=2)
        print(f"Graph saved to {json_output_path} (json format)")

    except FileNotFoundError:
        print(f"Error: File {pickle_file_path} not found")
    except Exception as e:
        print(f"Error loading graph: {e}")


def read_graph_from_json(json_file_path="graph_with_knowledge_blocks.json"):
    """从json文件中读取graph，返回networkx.DiGraph对象
    Args:
        json_file_path (str): json文件路径
    Returns:
        nx.DiGraph: 还原的有向图
    """
    import networkx as nx
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            graph_json = json.load(f)
        G = nx.DiGraph()
        # 还原节点
        for node in graph_json["nodes"]:
            node_id = node["id"]
            node_data = {k: v for k, v in node.items() if k != "id"}
            G.add_node(node_id, **node_data)
        # 还原边
        for edge in graph_json["edges"]:
            source = edge["source"]
            target = edge["target"]
            edge_data = {k: v for k, v in edge.items() if k not in ["source", "target"]}
            G.add_edge(source, target, **edge_data)
        print(f"Graph loaded from {json_file_path}, nodes: {len(G.nodes)}, edges: {len(G.edges)}")
        return G
    except Exception as e:
        print(f"Error loading graph from json: {e}")
        return None

# 调用函数读取并输出文档
if __name__ == "__main__":
    read_graph_and_output_documentation()
    #traverse_graph()

    #validation_callback("struct WifiApRecord")

def test_get_context_for_question():
    """Test function for get_context_for_question"""
    test_questions = [
        "How does the reward function work?",
        "What is the data flow in the training process?",
        "Explain the control flow of the agent system",
        "What are the external dependencies?",
        "How does the validation process work?"
    ]
    
    print("Testing get_context_for_question function...")
    print("=" * 60)
    
    for i, question in enumerate(test_questions, 1):
        print(f"\nTest {i}: {question}")
        print("-" * 40)
        
        try:
            context = get_context_for_question(question, top_k=3, min_similarity=0.2)
            print(f"Context retrieved (length: {len(context)} chars):")
            print(context[:500] + "..." if len(context) > 500 else context)
        except Exception as e:
            print(f"Error: {e}")
        
        print()

# Uncomment the line below to run the test
# test_get_context_for_question()