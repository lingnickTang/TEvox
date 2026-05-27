import requests
import json
from typing import List, Dict, Any

class VSCodeSymbolsClient:
    def __init__(self, base_url: str = "http://localhost:6789"):
        """
        初始化 VSCode 符号客户端
        
        Args:
            base_url: VSCode 扩展服务的基础 URL
        """
        self.base_url = base_url.rstrip('/')
        self.symbols_endpoint = f"{self.base_url}/symbols"
    
    def get_outgoing_calls(self, file_path: str, symbol_name: str) -> List[Dict[str, Any]]:
        """
        获取函数的出站调用（该函数调用了哪些其他函数）
        
        Args:
            file_path: 文件路径
            symbol_name: 符号名称（函数名）
            
        Returns:
            出站调用列表
            
        Raises:
            requests.RequestException: 请求失败
            ValueError: 参数错误
        """
        if not file_path or not symbol_name:
            raise ValueError("File path and symbol name are required")
        
        url = f"{self.symbols_endpoint}/outgoing_calls"
        params = {
            'filePath': file_path,
            'symbolName': symbol_name
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('outgoingCalls', [])
            
        except requests.RequestException as e:
            print(f"Error getting outgoing calls: {e}")
            raise
    
    def get_incoming_calls(self, file_path: str, symbol_name: str) -> List[Dict[str, Any]]:
        """
        获取函数的入站调用（哪些函数调用了该函数）
        
        Args:
            file_path: 文件路径
            symbol_name: 符号名称（函数名）
            
        Returns:
            入站调用列表
            
        Raises:
            requests.RequestException: 请求失败
            ValueError: 参数错误
        """
        if not file_path or not symbol_name:
            raise ValueError("File path and symbol name are required")
        
        url = f"{self.symbols_endpoint}/incoming_calls"
        params = {
            'filePath': file_path,
            'symbolName': symbol_name
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('incomingCalls', [])
            
        except requests.RequestException as e:
            print(f"Error getting incoming calls: {e}")
            raise
    
    def get_all_calls(self, file_path: str, symbol_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        同时获取函数的入站和出站调用
        
        Args:
            file_path: 文件路径
            symbol_name: 符号名称（函数名）
            
        Returns:
            包含 outgoing 和 incoming 调用的字典
        """
        return {
            'outgoing': self.get_outgoing_calls(file_path, symbol_name),
            'incoming': self.get_incoming_calls(file_path, symbol_name)
        }

# 使用示例
def main():
    # 创建客户端实例
    client = VSCodeSymbolsClient()
    
    try:
        # 示例：获取函数的出站调用
        outgoing_calls = client.get_outgoing_calls(
            file_path="main/hello_world_main.c",
            symbol_name="func3()"
        )
        
        print("Outgoing calls:")
        for call in outgoing_calls:
            print(f"  -> {call['to']['name']} in {call['to']['uri']}")
        
        # 示例：获取函数的入站调用
        incoming_calls = client.get_incoming_calls(
            file_path="main/hello_world_main.c",
            symbol_name="func3()"
        )
        
        print("\nIncoming calls:")
        for call in incoming_calls:
            print(f"  <- {call['from']['name']} in {call['from']['uri']}")
        
        # 示例：同时获取两种调用
        all_calls = client.get_all_calls(
            file_path="main/hello_world_main.c",
            symbol_name="func3()"
        )
        
        print(f"\nFunction analysis for handleRequest:")
        print(f"  Calls {len(all_calls['outgoing'])} other functions")
        print(f"  Called by {len(all_calls['incoming'])} functions")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()