# evox-server/src/core/rag/code/storage/graph_json_manager.py

import json
import os
from typing import Dict, Any
from pathlib import Path
class GraphJsonManager:
    """图结构 JSON 文件管理器，负责图的保存、加载和更新操作"""
    
    def save(self, graph: Dict[str, Any], filepath: str) -> bool:
        """
        将图结构字典保存为 JSON 文件
        
        Args:
            graph: 要保存的图结构字典
            filepath: 保存路径
            
        Returns:
            保存是否成功
        """
        dir_path = os.path.dirname(filepath)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(graph, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存图到JSON失败: {e}")
            return False
    
    def load(self, filepath: str) -> Dict[str, Any]:
        """
        从 JSON 文件加载图结构字典
        
        Args:
            filepath: JSON 文件路径
            
        Returns:
            加载的图结构字典，失败时返回 {}
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
            return graph_data
        except Exception as e:
            print(f"从JSON加载图失败: {e}")
            return {}
    
    def update_code(self, reference_json_path: str, node_graph: Dict[str, Any]) -> bool:
        """
        更新 reference_json_path 指向的参考图中的节点代码
        """
        ref = self.load(reference_json_path) or {'nodes': [], 'edges': []}
        for node in node_graph['nodes']:
            for ref_node in ref['nodes']:
                # 可以原地更新节点代码
                if ref_node['id'] == node['id']:
                    ref_node['code'] = node['code']
                    break
        self.save(ref, reference_json_path)
        return True

    def update(self, reference_json_path: Path, new_graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 new_graph 合并/更新到 reference_json_path 指向的参考图中，返回新增的节点
        节点去重，去除自环边
        
        Args:
            reference_json_path: 参考图 JSON 文件路径
            new_graph: 新的图结构（包含 'nodes'）
            
        Returns:
            包含新增节点的图结构字典: {"nodes": [...]}
        """
        ref = self.load(reference_json_path) or {'nodes': []}
        
        # 节点去重，去除自环边以及重复边
        seen_ids = set([node['id'] for node in ref['nodes']])
        deduped_new_nodes = []
        for node in new_graph.get('nodes', []):
            if node['id'] not in seen_ids:
                deduped_new_nodes.append(node)
                seen_ids.add(node['id'])
        
        # 合并去重后的新内容到ref
        ref['nodes'].extend(deduped_new_nodes)
        self.save(ref, reference_json_path)
        
        # 返回新增的节点
        return deduped_new_nodes
    
    def get_embed_path(self, reference_json_path: str) -> str:
        """
        获取 embedding sidecar 文件路径
        
        Args:
            reference_json_path: 参考图 JSON 文件路径
            
        Returns:
            embedding sidecar 文件路径
        """
        base, ext = os.path.splitext(reference_json_path)
        emb_path = f"{base}.emb{ext}" if ext else f"{reference_json_path}.emb.json"
        return emb_path
    
    def update_embeddings_sidecar(self, reference_json_path: str, embedding_graph: Dict[str, Any]) -> bool:
        """
        将 embedding sidecar 图保存为与参考图同名的 .emb.json 文件
        
        Args:
            reference_json_path: 参考图 JSON 文件路径
            embedding_graph: embedding 图字典
            
        Returns:
            更新是否成功
        """
        emb_path = self.get_embed_path(reference_json_path)
        ref = self.load(emb_path) or {}
        ref.update(embedding_graph)
        result = self.save(ref, emb_path)
        if result:
            print(f"更新embedding sidecar 图: {emb_path}")
        return result

