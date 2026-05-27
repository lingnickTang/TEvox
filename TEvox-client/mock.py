from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import random

app = FastAPI()


class TaskRequest(BaseModel):
    task_id: str
    task_spec: str
    feedback: Optional[str] = None


class MockAgentServe:
    def __init__(self, task_id: str, task_spec: str):
        self.task_id = task_id
        self.task_spec = task_spec
        
    def serve(self, feedback: Optional[str] = None) -> str:
        # 模拟不同类型的 markdown 响应
        responses = [
            # 响应模板1：任务分析
            f"""# Task Analysis for {self.task_id}
## Understanding the Request
- Task Specification: {self.task_spec}
- Feedback Status: {"With feedback" if feedback else "No feedback provided"}

## Proposed Solution
1. First step of the solution
2. Second step of the solution
3. Final implementation

## Code Example
```python
def example_function():
    return "Hello World"

Conclusion
Task analysis completed successfully.
                """,
                # 响应模板2：技术文档
                f"""# Technical Documentation
Overview

This document addresses: {self.task_spec}

Key Components

Component A
Component B
Component C

Implementation Details
| Feature | Status |
|---------|--------|
| Core Logic | Complete |
| Testing | Pending |
| Documentation | In Progress |
Next Steps

[ ] Review implementation
[ ] Add test cases
[ ] Deploy solution
                """,
                # 响应模板3：问题解决方案
                f"""# Solution Proposal

Problem Statement
{self.task_spec}
Approach

Analyzed requirements
Designed solution
Implemented core features

Code Snippet
class Solution:
    def solve(self):
        pass


Note: This is a preliminary solution that can be refined based on feedback.
                """
                ]
        # 随机选择一个响应
        return random.choice(responses)

@app.post("/process-task")
async def process_task(request: TaskRequest):
    """
    模拟处理任务请求的端点
    """
    try:
        agent = MockAgentServe(task_id=request.task_id, task_spec=request.task_spec)
        result = agent.serve(feedback=request.feedback)
        return {"task_id": request.task_id, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
