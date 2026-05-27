import os
import glob
import sys

# Add parent directory to sys.path to import config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import load_config

def scan_files(directory, extensions=['*.py', '*.c', '*.cpp']):
    """
    扫描指定目录及其子目录下的所有文件，匹配指定的扩展名。

    :param directory: 要扫描的文件夹路径
    :param extensions: 要匹配的文件扩展名列表，默认为 ['*.py', '*.c', '*.cpp']
    :return: 找到的文件路径列表
    """
    # 用于存储找到的文件路径
    file_paths = []
    
    # 遍历每个扩展名
    for ext in extensions:
        # 使用glob模块匹配文件
        for file_path in glob.glob(os.path.join(directory, '**', ext), recursive=True):
            # 获取文件的绝对路径并添加到列表中
            file_paths.append(os.path.abspath(file_path))
    
    return file_paths

def save_results(files, rag_output_file):
    """
    将扫描结果保存到指定路径下。

    :param files: 找到的文件路径列表
    :param rag_output_file: 输出文件路径
    """
    # 确保输出目录存在
    os.makedirs(os.path.dirname(rag_output_file), exist_ok=True)
    
    # 保存文件路径到输出文件
    with open(rag_output_file, 'w') as f:
        for file in files:
            f.write(file + "\n")

if __name__ == "__main__":
    # 加载配置
    config = load_config()
    
    # 获取扫描目录和输出路径
    directory_to_scan = config['codeRepositoryPath']
    rag_output_file = config['codeFilesPath']
    
    # 指定要扫描的扩展名
    extensions_to_scan = ['*.py', '*.c', '*.cpp', '*.h', '*.hpp', '*.cc']
    
    # 调用函数扫描文件
    print(f"Scanning files in {directory_to_scan}...")
    files = scan_files(directory_to_scan, extensions_to_scan)
    
    # 保存结果
    save_results(files, rag_output_file)
    print(f"Found {len(files)} files. Results saved to {rag_output_file}")