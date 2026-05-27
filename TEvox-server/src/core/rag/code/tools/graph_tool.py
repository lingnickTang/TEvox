"""
图操作相关工具

基于 Graph 封装，提供创建图节点、创建图边的工具接口，供 Agent 等调用。
"""
from typing import Optional

from src.core.rag.code.tools.graph import Graph
from src.utils.log import logger


def create_add_node_tool(graph: Graph):
    """
    创建「添加图节点」工具的工厂函数。

    Args:
        graph: Graph 实例，节点将添加到此图。

    Returns:
        add_node(node_id, body?, label?) -> str
    """

    def add_node(
        node_id: str,
        body: Optional[str] = None,
        label: Optional[str] = None,
    ) -> str:
        """
        向图中添加节点；若节点已存在则更新其属性。

        Args:
            node_id: 节点唯一标识，如函数签名、模块名等。
            body: 可选，节点主体内容，如代码片段、描述等。
            label: 可选，节点显示标签。

        Returns:
            成功或错误信息字符串。
        """
        try:
            attrs = {}
            if body is not None:
                attrs["body"] = body
            if label is not None:
                attrs["label"] = label
            graph.add_node(node_id, **attrs)
            logger.info("Add node: %s", node_id)
            return f"OK: Added node '{node_id}'."
        except Exception as e:
            msg = f"Error: Failed to add node '{node_id}': {e}"
            logger.error(msg)
            return msg

    return add_node


def create_add_edge_tool(graph: Graph):
    """
    创建「添加图边」工具的工厂函数。

    Args:
        graph: Graph 实例，边将添加到此图。

    Returns:
        add_edge(source, target, weight?, edge_type?) -> str
    """

    def add_edge(
        source: str,
        target: str,
        weight: Optional[float] = None,
        edge_type: Optional[str] = None,
    ) -> str:
        """
        向图中添加一条有向边 source -> target；若边已存在则更新其属性。

        Args:
            source: 源节点 ID。
            target: 目标节点 ID。
            weight: 可选，边权重，如调用频次、距离等。
            edge_type: 可选，边类型，如 "calls", "contains", "depends" 等。

        Returns:
            成功或错误信息字符串。
        """
        try:
            attrs = {}
            if weight is not None:
                attrs["weight"] = weight
            if edge_type is not None:
                attrs["edge_type"] = edge_type
            graph.add_edge(source, target, **attrs)
            logger.info("Add edge: %s -> %s", source, target)
            return f"OK: Added edge '{source}' -> '{target}'."
        except Exception as e:
            msg = f"Error: Failed to add edge '{source}' -> '{target}': {e}"
            logger.error(msg)
            return msg

    return add_edge
