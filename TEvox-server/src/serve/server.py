from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import subprocess
import sys
import shutil

from src.core.agents.planner.serve import AgentServe
from src.base import ConfigParser
from src.core.rag.doc.pipeline.base_pipeline import BasePipeline
from src.utils.log import logger

app = FastAPI()


class TaskRequest(BaseModel):
    task_id: str
    task_spec: str
    feedback: Optional[str] = None


class IntegratedIndexingRequest(BaseModel):
    docs_path: str
    repo_path: str
    rag_path: Optional[str] = None
    yaml_path: Optional[str] = None
    api_endpoint: Optional[str] = "http://localhost:6789"

@app.post("/process-task")
async def process_task(request: TaskRequest):
    """
    处理任务请求的端点，参数包含：
    - task_id: 唯一任务标识符
    - task_spec: 任务规范描述
    - feedback: 可选的人类反馈（用于迭代改进）
    """
    try:
        agent = AgentServe(task_id=request.task_id, task_spec=request.task_spec)
        if request.feedback == "continue" or request.feedback == "继续":
            request.feedback = ""
        result = agent.serve(feedback=request.feedback)
        return {"task_id": request.task_id, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/indexing/integrated")
async def integrated_indexing(request: IntegratedIndexingRequest):
    """
    进行集成索引（文档+代码）的端点
    - docs_path: 文档文件夹路径
    - repo_path: 代码仓库路径
    - rag_path: 索引输出目录路径 （默认是 .rag/{文档文件夹名称}）
    - yaml_path: YAML配置文件路径（默认是 default.yaml）
    - api_endpoint: client的API端点（默认是 http://localhost:6789）
    """
    try:
        # 获取文档库的名称
        docs_name = os.path.basename(os.path.normpath(request.docs_path))
        # 设置默认输出目录为 .rag/{文档库名称}
        rag_path = request.rag_path or os.path.join(".rag", docs_name)
        
        # 确保输出目录存在
        os.makedirs(rag_path, exist_ok=True)
        
        yaml_path = request.yaml_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "rag", "doc", "default.yaml"
        )
        
        # 检查输出目录中是否已有base_text_units.json和linked_graph.json文件，若有则跳过文档索引
        rag_output_dir = os.path.join(rag_path, "output")
        has_json_files = False
        if os.path.exists(rag_output_dir):
            required_json_files = ["base_text_units.json", "linked_graph.json"]
            existing_json_files = [f for f in os.listdir(rag_output_dir) if f in required_json_files]
            has_json_files = len(existing_json_files) == len(required_json_files)
        
        # 只有在没有json文件时才进行文档索引
        doc_success = True
        if not has_json_files:
            doc_success = await run_doc_indexing(request.docs_path, rag_output_dir, yaml_path)
            if not doc_success:
                raise HTTPException(status_code=500, detail="Document indexing failed")
        else:
            logger.info("JSON files already exist in output directory, skipping document indexing")
        
        # 检查输出目录中是否已有graphml文件，若有则跳过代码索引
        has_graphml_files = False
        if os.path.exists(rag_output_dir):
            graphml_files = [f for f in os.listdir(rag_output_dir) if f.endswith('.graphml')]
            has_graphml_files = len(graphml_files) > 0
        
        # 只有在没有graphml文件时才进行代码索引
        code_success = True
        if not has_graphml_files:
            code_success = await run_code_indexing(request.repo_path, rag_path, request.api_endpoint)
            if not code_success:
                raise HTTPException(status_code=500, detail="Code indexing failed")
        else:
            logger.info("GraphML files already exist in output directory, skipping code indexing")
        
        return {"message": "Integrated indexing completed successfully"}
    except Exception as e:
        logger.error(f"Error running integrated indexing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running integrated indexing: {str(e)}")


async def run_code_indexing(repo_path: str, rag_path: str, api_endpoint: str) -> bool:
    """
    运行代码索引流程
    """
    try:
        # 获取脚本的绝对路径
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "rag", "code", "run_pipeline.py"
        )
        
        # 确保输出目录存在
        os.makedirs(rag_path, exist_ok=True)
        
        # 构建命令
        cmd = [
            sys.executable,
            script_path,
            "--repo-path", repo_path,
            "--rag-path", rag_path,
            "--api-endpoint", api_endpoint
        ]
        
        logger.info(f"Running code indexing command: {' '.join(cmd)}")
        # 执行命令
        process = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        # 检查执行结果
        if process.returncode != 0:
            logger.error(f"Code indexing failed with code {process.returncode}")
            logger.error(f"Error output: {process.stderr}")
            return False
        
        logger.info("Code indexing completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Code indexing process error: {e}")
        logger.error(f"Command output: {e.stdout}")
        logger.error(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in code indexing: {e}")
        return False


async def run_doc_indexing(docs_path: str, output_path: str, yaml_path: str) -> bool:
    """
    运行文档索引流程
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_path, exist_ok=True)
        
        # 创建输入目录
        output_input_dir = os.path.join(output_path, "input")
        os.makedirs(output_input_dir, exist_ok=True)
        
        # 复制输入文档到新的输入目录
        if os.path.isdir(docs_path):
            for item in os.listdir(docs_path):
                src_path = os.path.join(docs_path, item)
                dst_path = os.path.join(output_input_dir, item)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)
                    logger.info(f"Copied {src_path} to {dst_path}")
        else:
            logger.error(f"Input path {docs_path} is not a directory")
            return False
        
        # 加载配置
        config = ConfigParser(yaml_path)
        config.config["global"]["root_path"] = output_path
        
        # 运行管道
        pipeline = BasePipeline(config)
        pipeline.run()
        
        logger.info("Document indexing completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error in document indexing: {e}")
        return False


def install_playwright():
    logger.info("Starting Playwright installation...")
    try:
        # subprocess.run(["playwright", "install"], check=True)

        if os.path.isdir(".env") and os.path.isdir(os.path.join(".env", "Scripts")):
            for file_name in os.listdir(os.path.join(".env", "Scripts")):
                if file_name.startswith("playwright"):
                    playwright_path = os.path.join(".env", "Scripts", file_name)
                    logger.info(f"Found playwright executable: {playwright_path}")
                    subprocess.run([playwright_path, "install"], check=True)
                    return

        logger.info("Using system-wide playwright command")
        subprocess.run(["playwright", "install"], check=True)

    except subprocess.CalledProcessError as e:
        raise RuntimeError("Playwright installation failed") from e


if __name__ == "__main__":
    import uvicorn

    # install_playwright()

    uvicorn.run(app, host="0.0.0.0", port=8000)
