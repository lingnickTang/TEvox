import requests
import json
import os
import sys
import uuid
from tqdm import tqdm

# Add parent directory to sys.path to import config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import load_config

def _normalize_path(path: str) -> str:
    """标准化路径，统一使用正斜杠"""
    return os.path.normpath(path).replace('\\', '/')

def _get_relative_path(file_path: str, base_path: str) -> str:
    """获取相对于base_path的相对路径"""
    try:
        rel_path = os.path.relpath(file_path, base_path)
        return _normalize_path(rel_path)
    except ValueError:
        # 如果无法计算相对路径（比如在不同驱动器），返回文件名
        return os.path.basename(file_path)

def _generate_function_node_id(file_path: str, function_name: str, base_path: str) -> str:
    """生成与graph_constructor对齐的函数节点ID"""
    rel_path = _get_relative_path(file_path, base_path)
    return f"func:{rel_path}:{function_name}"

def getfuncbodycalls(file_path, symbolName, store_edges_file_path, api_endpoint, base_path=None):
    """
    调用 /getFunctionBody API，获取函数体
    
    :param file_path: 文件路径
    :param symbolName: 符号名称
    :param store_edges_file_path: 存储函数体的文件路径
    :param api_endpoint: API终点
    :param base_path: 项目基础路径，用于生成相对路径
    :return: 是否成功获取函数体
    """
    symbolName = symbolName.strip()
    params = {"filePath": file_path, "symbolName": symbolName}
    response = requests.get(f"{api_endpoint}/symbols/function_body", params=params)
    if response.status_code == 200:
        resp = response.json()
        resp['filepath'] = file_path
        resp['symbolName'] = symbolName
        resp['id'] = str(uuid.uuid4())
        
        # 添加与graph_constructor对齐的节点ID
        if base_path:
            resp['graph_node_id'] = _generate_function_node_id(file_path, symbolName, base_path)
            resp['relative_path'] = _get_relative_path(file_path, base_path)
        
        if resp['functionBody'].endswith(');'):
            return False  # 函数体以分号结尾，说明是函数定义，不是函数调用，跳过
        with open(store_edges_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(resp, ensure_ascii=False) + "\n")
        return True
    return False

def acquire_function_bodys(symbols_file_path, store_bodys_file_path, api_endpoint, base_path=None):
    """
    遍历symbols_file_path，获取每个symbol的出度，将出度写入store_bodys_file_path
    
    :param symbols_file_path: 符号文件路径
    :param store_bodys_file_path: 存储函数体的文件路径
    :param api_endpoint: API终点
    :param base_path: 项目基础路径，用于生成相对路径和节点ID
    """
    symbols_file_path = os.path.abspath(symbols_file_path)
    store_bodys_file_path = os.path.abspath(store_bodys_file_path)
    
    # 如果没有提供base_path，使用当前工作目录
    if base_path is None:
        base_path = os.getcwd()
    
    with open(symbols_file_path, encoding='utf-8') as f:
        datas_str = f.read()
    datas = json.loads(datas_str)['data']  # 使用 loads (load string)

    # 检查已经存在的函数体
    exsist = set()
    if os.path.exists(store_bodys_file_path):
        with open(store_bodys_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    jline = json.loads(line)
                    filepath = jline['filepath'].strip()
                    symbolName = jline['symbolName'].strip()
                    exsist.add(filepath + symbolName)
                except:
                    print('Warning: Error parsing line in function body file')
    
    # 计算总符号数
    all_symbol_number = sum([len(jdata['symbols']) for jdata in datas])
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(store_bodys_file_path), exist_ok=True)
    
    # 创建或清空输出文件
    if not os.path.exists(store_bodys_file_path):
        with open(store_bodys_file_path, 'w', encoding='utf-8') as f:
            pass
    
    success_count = 0
    print(f"Processing {all_symbol_number} symbols...")
    print(f"Base path for relative path generation: {base_path}")
    
    for jdata in tqdm(datas):
        symbols = jdata['symbols']
        filepath = jdata['filepath']

        for symbol in symbols:
            if filepath.strip() + symbol.strip() in exsist:
                success_count += 1
                continue
            
            if getfuncbodycalls(filepath, symbol, store_bodys_file_path, api_endpoint, base_path):
                success_count += 1
    
    print(f"Successfully acquired {success_count} function bodies out of {all_symbol_number} symbols")

if __name__ == "__main__":
    # 加载配置
    config = load_config()
    
    # 获取路径和API终点
    symbols_file_path = config['symbolsJsonPath']
    store_bodys_file_path = config['functionBodiesPath']
    api_endpoint = config['apiEndpoint']
    
    # 获取项目基础路径（用于生成相对路径）
    base_path = config.get('codeRepositoryPath', os.getcwd())
    
    # 获取函数体
    acquire_function_bodys(symbols_file_path, store_bodys_file_path, api_endpoint, base_path)