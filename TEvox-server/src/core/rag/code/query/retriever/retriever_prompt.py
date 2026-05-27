# evox-server/src/core/rag/code/query/retriever_prompt.py

RETRIEVER_PROMPTS = {
    "query_decomposition": {
        "decompose_query": """请分析以下的设计文档包含哪些功能模块，并将其拆分：
  
{query}

输出格式要求：


{{
    "queries": [
        "功能模块1",
        "功能模块2", 
        ...
    ]   
}}
"""
    }
}
