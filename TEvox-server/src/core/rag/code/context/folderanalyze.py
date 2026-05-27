import json
import os
from pathlib import Path
from typing import Dict, Set, List
from dataclasses import dataclass
from tqdm import tqdm

from fileanalyze import (
    FileAnalyzer,
    FileAnalysisResult
)


@dataclass
class FolderAnalysisResult:
    folder_path: str
    files_analyzed: List[str]
    referenced_folders: Set[str]  # 这个文件夹引用的其他文件夹
    referencing_folders: Set[str]  # 引用这个文件夹的其他文件夹
    file_analysis_results: Dict[str, FileAnalysisResult]  # 每个文件的分析结果

class FolderAnalyzer:
    def __init__(self, file_analyzer: FileAnalyzer):
        self.file_analyzer = file_analyzer

    def _get_folder_path(self, file_path: str) -> str:
        """获取文件所在的文件夹路径"""
        return str(Path(file_path).parent)

    def analyze_folder(self, folder_path: str, use_cache: bool = True, cache_dir: str = None) -> FolderAnalysisResult:
        """分析文件夹中的所有文件"""
        if cache_dir is None:
            cache_dir = "./cache"

        folder_path = os.path.abspath(folder_path)
        print(f"\nAnalyzing folder: {folder_path}")

        # 获取文件夹中的所有文件
        files = []
        for entry in os.scandir(folder_path):
            if entry.is_file() and entry.name.endswith(('.c', '.h', '.cc', '.cpp')):  # 可以根据需要调整文件类型
                files.append(entry.path)

        # 分析每个文件
        file_results = {}
        referenced_folders = set()
        referencing_folders = set()

        for file_path in tqdm(files, desc="Analyzing files"):
            result = self.file_analyzer.analyze_file(file_path, use_cache, cache_dir)
            if result:
                file_results[file_path] = result

                # 收集文件夹引用关系
                for ref_file in result.referenced_files:
                    ref_folder = self._get_folder_path(ref_file)
                    if ref_folder != folder_path:
                        referenced_folders.add(ref_folder)

                for ref_file in result.referencing_files:
                    ref_folder = self._get_folder_path(ref_file)
                    if ref_folder != folder_path:
                        referencing_folders.add(ref_folder)

        return FolderAnalysisResult(
            folder_path=folder_path,
            files_analyzed=files,
            referenced_folders=referenced_folders,
            referencing_folders=referencing_folders,
            file_analysis_results=file_results
        )

    def generate_folder_summary(self, result: FolderAnalysisResult) -> str:
        """生成文件夹分析摘要"""
        summary = f"""
文件夹分析报告: {result.folder_path}
==========================================

分析的文件数量: {len(result.files_analyzed)}
分析的文件列表:
{chr(10).join(f"  - {os.path.basename(f)}" for f in result.files_analyzed)}

文件夹依赖关系:
-----------------------------------------
引用的文件夹 ({len(result.referenced_folders)}个):
{chr(10).join(f"  - {folder}" for folder in sorted(result.referenced_folders))}

被引用的文件夹 ({len(result.referencing_folders)}个):
{chr(10).join(f"  - {folder}" for folder in sorted(result.referencing_folders))}

文件级别统计:
-----------------------------------------"""

        # 统计所有函数和全局变量
        all_functions = set()
        all_globals = set()
        file_summaries = []

        for file_path, file_result in result.file_analysis_results.items():
            all_functions.update(file_result.functions)
            all_globals.update(file_result.global_variables)
            
            # 生成每个文件的简要统计
            file_summary = f"""
  {os.path.basename(file_path)}:
    函数数量: {len(file_result.functions)}
    全局变量数量: {len(file_result.global_variables)}
    引用的文件数: {len(file_result.referenced_files)}
    被引用的文件数: {len(file_result.referencing_files)}"""
            file_summaries.append(file_summary)

        summary += f"""
总函数数量: {len(all_functions)}
总全局变量数量: {len(all_globals)}

文件详细统计:
{chr(10).join(file_summaries)}
"""
        return summary

# 使用示例
if __name__ == "__main__":
    file_analyzer = FileAnalyzer("http://localhost:6789")
    folder_analyzer = FolderAnalyzer(file_analyzer)
    
    folder_path = "D:\\Download\\github\\code_base\\xiaozhi\\xiaozhi-esp32-display"
    # 分析文件夹
    folder_result = folder_analyzer.analyze_folder(
        folder_path = folder_path,
        use_cache=True,
        cache_dir="cache"
    )
    
    # 生成并打印摘要
    print(folder_analyzer.generate_folder_summary(folder_result))
