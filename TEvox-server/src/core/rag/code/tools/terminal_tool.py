"""
终端操作相关工具
"""
from typing import Callable
from src.core.rag.code.tools.vscode import VSCodeClient
from src.utils.log import logger

# build
def create_esp_idf_build_tool(vscode_client: VSCodeClient):
    """
    创建 ESP-IDF 编译工具的包装函数
    
    Args:
        vscode_client: VSCodeClient 实例
    
    Returns:
        包装后的函数
    """
    def esp_idf_build() -> str:
        """
        在 ESP-IDF 终端中执行 idf.py build 命令进行编译。
        
        Returns:
            编译结果字符串，包含成功/失败状态和输出内容
        """
        try:
            logger.info("Executing idf.py build in ESP-IDF terminal")
            result = vscode_client.executeCommandInEspIdfTerminal("idf.py build")
            return f"Build execution result:\n{result}"
        except Exception as e:
            error_msg = f"Error: Build execution failed: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    return esp_idf_build

