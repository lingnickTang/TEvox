import requests
import json
import threading
import re
import os
import sys
import hashlib
from datetime import datetime
from tqdm import tqdm

# Add parent directory to sys.path to import config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import load_config

lock = threading.Lock()

def get_cache_key(path, api_endpoint):
    """生成缓存的唯一键"""
    cache_key = f"{path}_{api_endpoint}"
    return hashlib.md5(cache_key.encode()).hexdigest()

def load_from_cache(cache_dir, cache_key):
    """从缓存加载数据"""
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def save_to_cache(cache_dir, cache_key, data):
    """保存数据到缓存"""
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{cache_key}.json")
    with open(cache_file, 'w') as f:
        json.dump(data, f)

def process_file(files_path, output_file, api_endpoint, use_cache=True, cache_dir=None):
    """
    Process all files listed in files_path to extract symbols
    
    :param files_path: Path to the file containing list of code files
    :param output_file: Path to save the extracted symbols
    :param api_endpoint: API endpoint for the VSCode extension
    :param use_cache: Whether to use cache
    :param cache_dir: Directory to store cache files
    """
    # 设置默认缓存目录
    if cache_dir is None:
        cache_dir = os.path.join(os.path.dirname(output_file), "cache")
    
    with open(files_path, 'r') as f:
        file_paths_list = [line.strip() for line in f]
    
    datas = {}
    datas['files_path'] = files_path
    datas['create_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    datas['data'] = []
    
    print(f"Processing {len(file_paths_list)} files...")
    for path in tqdm(file_paths_list):
        # 检查缓存
        cache_key = get_cache_key(path, api_endpoint)
        cached_data = None
        if use_cache:
            cached_data = load_from_cache(cache_dir, cache_key)
        
        if cached_data:
            datas['data'].append(cached_data)
            continue
            
        response = requests.get(f'{api_endpoint}/symbols/outline?filePath={path}')
        if response.status_code == 200:
            try:
                res = json.loads(response.text)['outline']
                symbols = res.split('\n')
                print("In find_all_symbols, symbols:",symbols, "length:",len(symbols))
                symbol_names = []
                symbol_kinds = []
                for symbol in symbols:
                    if len(symbol) == 0:
                        continue
                    # Parse format like "GPIO_TAG (Variable)"
                    match = re.match(r'(.*?)\s+\((.*?)\)$', symbol)
                    if match:
                        symbol_name = match.group(1).strip()
                        symbol_kind = match.group(2).strip()
                        symbol_names.append(symbol_name)
                        symbol_kinds.append(symbol_kind)
                
                data = {
                    'symbols': symbol_names,
                    'symbolKinds': symbol_kinds,
                    'filepath': path
                }
                
                # 保存到缓存
                if use_cache:
                    save_to_cache(cache_dir, cache_key, data)
                    
                datas['data'].append(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing {path}: {str(e)}")
        else:
            print(f"Error: {response.status_code} - {response.text} for {path}")
    
    # Write JSON data to file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    json_data = json.dumps(datas, indent=2)
    with open(output_file, 'w') as f:
        f.write(json_data)
    print(f"Symbols have been saved to {output_file}")

if __name__ == "__main__":
    # Load configuration
    config = load_config()
    
    # Get paths from config
    code_files_path = config['codeFilesPath']
    symbols_json_path = config['symbolsJsonPath']
    api_endpoint = config['apiEndpoint']
    cache_dir = config['cacheDir']
    # Process files
    process_file(code_files_path, symbols_json_path, api_endpoint, cache_dir=cache_dir)