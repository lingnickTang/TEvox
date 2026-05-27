import hashlib

def calculate_md5(file_path):
    """计算文件的 MD5 哈希值"""
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        # 分块读取文件，避免大文件占用过多内存
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

# 使用示例
file_path = "/Users/littlexi/work/memx/rag/vscode_dep/rag_file_code/rag_file_code/ragfileprocess/evox-ai-master/evox-server/src/core/rag/code/.output/functions_bodys.jsonl"  # 替换为你的文件路径
md5_value = calculate_md5(file_path)
print(f"文件的 MD5 值为: {md5_value}")