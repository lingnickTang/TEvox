import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor

response = requests.get('http://localhost:3000/helloWorld')
print(response.text)

BASE_URL = 'http://localhost:3000'

cnt = 0

def call_get_function_calls(file_path, symbolName , store_edges_file_path ):
    '''
    调用 /getFunctionCalls 接口，获取函数调用关系
    '''
    global errors , cnt
    symbolName = symbolName.strip()
    store_symbolName = symbolName
    if symbolName.find('(') != -1:
        symbolName = symbolName[:symbolName.find('(')]
    params = {"filePath": file_path, "symbolName": symbolName}
    response = requests.get(f"{BASE_URL}/getFunctionCalls", params=params)
    cache = []
    if response.status_code == 200:
        resp = response.json()
        if 'calledFunctions' not in resp:
            resp['calledFunctions'] = []
        if 'message' in resp:
            del resp['message']
        resp['filepath'] = file_path
        resp['symbolName'] = store_symbolName
        cnt += 1
        with open(store_edges_file_path, 'a') as f:
            f.write(json.dumps(resp) + "\n")
    else:
        pass

def acquire_edges(symbols_file_path = '../../.output/symbols.json', store_edges_file_path = "../../.output/functions_edges.json"):
    '''
    遍历symbols_file_path，获取每个symbol的出度，将出度写入store_edges_file_path
    '''
    global cnt
    symbols_file_path = os.path.abspath(symbols_file_path)
    store_edges_file_path = os.path.abspath(store_edges_file_path)
    datas_str = ''
    with open(symbols_file_path) as f:
        datas_str = f.read()
    datas = json.loads(datas_str)['data']  # 使用 loads (load string)

    exsist = set()
    if os.path.exists(store_edges_file_path):
        with open(store_edges_file_path, 'r') as f:
            for line in f:
                jline = json.loads(line)
                try:
                    exsist.add(jline['filepath'] + jline['symbolName'])
                except:
                    print('Info : ' , "json.loads(line) error")
    all_symbol_number = 0
    for jdata in datas:
        all_symbol_number += len(jdata['symbols'])
    for jdata in datas:
        symbols = jdata['symbols']
        filepath = jdata['filepath']

        for symbol in symbols:
            if filepath + symbol in exsist:
                cnt += 1
                # print('continue')
                continue
            call_get_function_calls(filepath , symbol , store_edges_file_path)
            print('Success acquire edges : ', cnt, '/', all_symbol_number)


symbols_file_path = '../../.output/symbols.json'
store_edges_file_path = "../../.output/functions_edges.json"
acquire_edges(symbols_file_path , store_edges_file_path)