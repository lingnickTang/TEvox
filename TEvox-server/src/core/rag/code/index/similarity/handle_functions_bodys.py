import uuid
import json

vis = set()
datas = []

with open('../../.output/functions_bodys.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():  # Skip empty lines
            func = json.loads(line)
            dic = {}
            dic['functionBody'] = func['functionBody']
            dic['symbolName'] = func['symbolName']
            if str(dic) in vis:
                continue
            vis.add(str(dic))
            datas.append(dic)

with open('../../.output/functions_bodys_2.jsonl', 'w', encoding='utf-8') as f:
    for item in datas:
        # if item['functionBody'].startswith('public'):
            # continue
        if item['functionBody'].endswith(');'):
            continue
        
        item['id'] = str(uuid.uuid4())
        f.write(json.dumps(item) + '\n')        
