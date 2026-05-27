"""
文件操作相关工具
"""
import os
from typing import Callable, Optional, List
from src.core.rag.code.tools.vscode import VSCodeClient
from src.utils.log import logger


def create_read_file_tool(vscode_client: VSCodeClient):
    """
    创建读取文件工具的包装函数
    
    Args:
        vscode_client: VSCodeClient 实例
    
    Returns:
        包装后的函数
    """
    def read_file(file_path: str) -> str:
        """
        根据文件路径读取文件内容并返回
        
        Args:
            file_path: 文件路径
        
        Returns:
            文件内容
        """
        try:
            logger.info(f"Reading file: {file_path}")
            result = vscode_client.open_file(file_path)
            return result
        except Exception as e:
            error_msg = f"Error: Failed to read file {file_path}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    return read_file

def create_write_file_tool(vscode_client: VSCodeClient):
    """
    创建写入文件工具的包装函数
    
    Args:
        vscode_client: VSCodeClient 实例
    
    Returns:
        包装后的函数
    """
    def write_file(
        file_path: str,
        content: str,
        start_line: int = 1,
        end_line: int = -1,
        edit_type: str = "replace"
    ) -> str:
        """
        将内容写入到指定文件中。
        
        Args:
            file_path: 文件路径（绝对路径或相对于工作区的路径）
            content: 要写入的内容
            start_line: 起始行号，默认为 1
            end_line: 结束行号，默认为 -1（表示文件末尾）
            edit_type: 编辑类型，"insert" 或 "replace"，默认为 "replace"
        
        Returns:
            成功消息或错误信息
        """
        try:
            result = vscode_client.write_file(
                file_path=file_path,
                content=content,
                start_line=start_line,
                end_line=end_line,
                edit_type=edit_type
            )
            return f"File written successfully: {file_path}\n{result}"
        except Exception as e:
            error_msg = f"Error: Failed to write file {file_path}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    return write_file


def create_search_files_tool(vscode_client: VSCodeClient = None):
    """
    创建搜索文件工具的包装函数
    
    Args:
        vscode_client: VSCodeClient 实例（此参数保留以保持接口一致性，但实际不使用）
    
    Returns:
        包装后的函数
    """
    def search_files(
        keyword: str,
        file_extensions: Optional[List[str]] = None,
        search_path: str = ".",
        max_results: int = 10
    ) -> List[str]:
        """
        根据关键词搜索文件名，支持文件类型过滤。
        
        Args:
            keyword: 搜索关键词，将匹配文件名中包含该关键词的文件
            file_extensions: 文件扩展名列表，如 ['.py', '.cpp', '.h']，默认为 None（不过滤）
            search_path: 搜索起始路径，默认为 "."（当前工作目录）
            max_results: 最大返回结果数量，默认为 10
        
        Returns:
            匹配的文件路径列表
        """
        try:
            logger.info(f"Searching files with keyword: {keyword}, extensions: {file_extensions}, max_results: {max_results}")
            
            # 标准化搜索路径
            if not os.path.isabs(search_path):
                search_path = os.path.abspath(search_path)
            
            if not os.path.exists(search_path):
                return []
            
            if not os.path.isdir(search_path):
                return []
            
            # 默认排除的目录
            exclude_dirs = {
                '__pycache__', '.git', '.svn', '.hg', 'node_modules', 
                '.vscode', '.idea', 'build', 'dist', '.pytest_cache',
                '.mypy_cache', '.tox', 'venv', 'env', '.venv'
            }
            
            matched_files = []
            keyword_lower = keyword.lower()
            
            # 遍历目录
            for root, dirs, files in os.walk(search_path):
                # 过滤掉排除的目录
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                
                # 检查是否已达到最大结果数
                if len(matched_files) >= max_results:
                    break
                
                for file in files:
                    # 检查是否已达到最大结果数
                    if len(matched_files) >= max_results:
                        break
                    
                    # 检查文件扩展名
                    if file_extensions:
                        _, ext = os.path.splitext(file)
                        # 标准化扩展名格式（确保以 . 开头并转为小写）
                        normalized_ext = ext.lower() if ext else ''
                        normalized_extensions = [
                            e.lower() if e.startswith('.') else f'.{e.lower()}' 
                            for e in file_extensions
                        ]
                        if normalized_ext not in normalized_extensions:
                            continue
                    
                    # 检查文件名是否包含关键词（不区分大小写）
                    if keyword_lower in file.lower():
                        file_path = os.path.join(root, file)
                        matched_files.append(file_path)
            
            # 返回结果（每行一个路径）
            if matched_files:
                logger.info(f"Found {len(matched_files)} matching files")
                return matched_files
            else:
                logger.info(f"No files found matching keyword: {keyword}")
                return []
            
        except Exception as e:
            logger.error(f"Error: Failed to search files with keyword '{keyword}': {str(e)}")
            return []
    
    return search_files


def create_get_directory_files_tool(vscode_client: VSCodeClient):
    """
    创建获取目录文件列表工具的包装函数
    
    Args:
        vscode_client: VSCodeClient 实例
    
    Returns:
        包装后的函数
    """
    def get_directory_files(path: str, recursive: str = "false") -> str:
        """
        获取目录中的文件列表
        
        Args:
            path: 目录路径（绝对路径或相对于工作区的路径）
            recursive: 是否递归搜索，"true" 或 "false"，默认为 "false"
        
        Returns:
            目录文件列表（文件内容）或错误信息
        """
        try:
            logger.info(f"Getting directory files: {path}, recursive: {recursive}")
            result = vscode_client.get_directory_files(path, recursive)
            return result
        except Exception as e:
            error_msg = f"Error: Failed to get directory files {path}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    return get_directory_files


def create_find_in_files_tool(vscode_client: VSCodeClient):
    """
    创建在文件中搜索工具的包装函数
    
    Args:
        vscode_client: VSCodeClient 实例
    
    Returns:
        包装后的函数
    """
    def find_in_files(
        query: str,
        files_to_include: str = "",
        files_to_exclude: str = "",
        is_regex: bool = True,
        is_case_sensitive: bool = False,
        match_whole_word: bool = False
    ) -> str:
        """
        在文件中搜索代码
        
        Args:
            query: 搜索查询字符串
            files_to_include: 要包含的文件（glob 模式），如 "**/*.{c,cpp,h,hpp}"
            files_to_exclude: 要排除的文件（glob 模式）
            is_regex: 是否将查询解释为正则表达式，默认为 True
            is_case_sensitive: 是否区分大小写，默认为 False
            match_whole_word: 是否仅匹配完整单词，默认为 False
        
        Returns:
            搜索结果（文件内容）或错误信息
        """
        try:
            logger.info(f"Finding in files with query: {query}, include: {files_to_include}")
            result = vscode_client.find_in_files(
                query=query,
                filesToInclude=files_to_include,
                filesToExclude=files_to_exclude,
                isRegex=is_regex,
                isCaseSensitive=is_case_sensitive,
                matchWholeWord=match_whole_word
            )
            return result
        except Exception as e:
            error_msg = f"Error: Failed to find in files with query '{query}': {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    return find_in_files


def create_find_references_tool(vscode_client: VSCodeClient):
    """
    创建查找符号引用工具的包装函数
    
    Args:
        vscode_client: VSCodeClient 实例
    
    Returns:
        包装后的函数
    """
    def find_references(
        file_path: str,
        line_number: int,
        selected_symbol: str
    ) -> str:
        """
        查找指定符号在代码库中的所有引用
        
        Args:
            file_path: 文件路径（绝对路径或相对于工作区的路径）
            line_number: 符号所在的行号
            selected_symbol: 要查找引用的符号名称
        
        Returns:
            引用位置信息（JSON字符串）或错误信息
        """
        try:
            logger.info(f"Finding references for symbol: {selected_symbol} at {file_path}:{line_number}")
            result = vscode_client.find_references(
                file_path=file_path,
                line_number=line_number,
                selected_symbol=selected_symbol
            )
            return result
        except Exception as e:
            error_msg = f"Error: Failed to find references for {selected_symbol}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    return find_references