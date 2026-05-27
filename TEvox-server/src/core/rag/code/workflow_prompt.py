# evox-server/src/core/rag/code/workflow_prompt.py

WORKFLOW_PROMPTS = {
    "generate_code": """
Context:
{context}
First generate the analysis based on the context above, and then generate the code inside the ```cpp ``` mark based on the following requirement:
{requirement}
"""
}

