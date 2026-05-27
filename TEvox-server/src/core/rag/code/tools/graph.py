"""
基于 networkx 的图封装类

提供节点/边增删、属性、遍历（DFS/BFS）、序列化等能力，适用于代码依赖图、调用图等场景。
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, Union

import networkx as nx

from src.utils.log import logger


class Graph:
    """
    基于 networkx 的图封装。

    默认使用有向图 (DiGraph)；可切换为无向图 (Graph)。
    支持节点/边属性、DFS/BFS 遍历、根节点查询、图导出/导入等。
    """

    def __init__(self, directed: bool = True):
        """
        初始化图。

        Args:
            directed: 若为 True 使用有向图 (nx.DiGraph)，否则使用无向图 (nx.Graph)。
        """
        self._directed = directed
        self._g: Union[nx.DiGraph, nx.Graph] = (
            nx.DiGraph() if directed else nx.Graph()
        )

    # -------------------------------------------------------------------------
    # 底层图访问
    # -------------------------------------------------------------------------

    @property
    def nx_graph(self) -> Union[nx.DiGraph, nx.Graph]:
        """获取底层 networkx 图对象，用于调用 nx 算法或高级操作。"""
        return self._g

    @property
    def is_directed(self) -> bool:
        """是否为有向图。"""
        return self._directed

    # -------------------------------------------------------------------------
    # 节点
    # -------------------------------------------------------------------------

    def add_node(self, node_id: str, **attrs: Any) -> None:
        """
        添加节点；若已存在则更新属性。

        Args:
            node_id: 节点标识（须可哈希，通常为 str）。
            **attrs: 节点属性，如 body, metadata 等。
        """
        self._g.add_node(node_id, **attrs)

    def remove_node(self, node_id: str) -> None:
        """删除节点及其关联边。"""
        self._g.remove_node(node_id)

    def has_node(self, node_id: str) -> bool:
        """判断节点是否存在。"""
        return self._g.has_node(node_id)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        获取节点属性字典；若不存在返回 None。
        返回的 dict 可修改，修改会反映到图中。
        """
        if not self._g.has_node(node_id):
            return None
        return dict(self._g.nodes[node_id])

    def nodes(self) -> Iterator[str]:
        """迭代所有节点 ID。"""
        return iter(self._g.nodes())

    def node_count(self) -> int:
        """节点数量。"""
        return self._g.number_of_nodes()

    # -------------------------------------------------------------------------
    # 边
    # -------------------------------------------------------------------------

    def add_edge(self, u: str, v: str, **attrs: Any) -> None:
        """
        添加边 (u -> v)；若已存在则更新属性。

        Args:
            u: 源节点。
            v: 目标节点。
            **attrs: 边属性，如 weight, edge_type 等。
        """
        self._g.add_edge(u, v, **attrs)

    def remove_edge(self, u: str, v: str) -> None:
        """删除边 (u -> v)。"""
        self._g.remove_edge(u, v)

    def has_edge(self, u: str, v: str) -> bool:
        """判断边 (u -> v) 是否存在。"""
        return self._g.has_edge(u, v)

    def get_edge(self, u: str, v: str) -> Optional[Dict[str, Any]]:
        """
        获取边 (u -> v) 的属性字典；若不存在返回 None。
        """
        data = self._g.get_edge_data(u, v)
        return dict(data) if data is not None else None

    def edges(self) -> Iterator[Tuple[str, str]]:
        """迭代所有边 (u, v)。"""
        return iter(self._g.edges())

    def edge_count(self) -> int:
        """边数量。"""
        return self._g.number_of_edges()

    # -------------------------------------------------------------------------
    # 邻接与度
    # -------------------------------------------------------------------------

    def successors(self, node_id: str) -> List[str]:
        """有向图中该节点的后继（出边目标）；无向图中为邻居。"""
        return list(self._g.successors(node_id))

    def predecessors(self, node_id: str) -> List[str]:
        """有向图中该节点的前驱（入边来源）；无向图中为邻居。"""
        return list(self._g.predecessors(node_id))

    def neighbors(self, node_id: str) -> List[str]:
        """邻居节点。有向图中等价于 successors。"""
        return list(self._g.neighbors(node_id))

    def in_degree(self, node_id: str) -> int:
        """节点入度。"""
        return self._g.in_degree(node_id)

    def out_degree(self, node_id: str) -> int:
        """节点出度。"""
        return self._g.out_degree(node_id)

    def roots(self) -> List[str]:
        """有向图中入度为 0 的节点（根节点）；无向图返回空列表。"""
        if not self._directed:
            return []
        return [n for n in self._g.nodes() if self._g.in_degree(n) == 0]

    # -------------------------------------------------------------------------
    # 遍历
    # -------------------------------------------------------------------------

    def dfs_pre_order(
        self,
        start: str,
        visited: Optional[Set[str]] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> List[str]:
        """
        从 start 开始深度优先前序遍历（先访问当前节点，再访问后继）。

        Args:
            start: 起始节点。
            visited: 已访问集合，可传入以支持多起点；默认新建。
            callback: 每访问一个节点时调用 callback(node_id)。

        Returns:
            访问顺序的节点 ID 列表。
        """
        if visited is None:
            visited = set()
        order: List[str] = []

        def _visit(n: str) -> None:
            if n in visited:
                return
            visited.add(n)
            if callback:
                callback(n)
            order.append(n)
            for succ in self.successors(n):
                _visit(succ)

        _visit(start)
        return order

    def dfs_post_order(
        self,
        start: str,
        visited: Optional[Set[str]] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> List[str]:
        """
        从 start 开始深度优先后序遍历（先访问后继，再访问当前节点）。

        Args:
            start: 起始节点。
            visited: 已访问集合；默认新建。
            callback: 每访问一个节点时调用 callback(node_id)。

        Returns:
            访问顺序的节点 ID 列表。
        """
        if visited is None:
            visited = set()
        order: List[str] = []

        def _visit(n: str) -> None:
            if n in visited:
                return
            visited.add(n)
            for succ in self.successors(n):
                _visit(succ)
            if callback:
                callback(n)
            order.append(n)

        _visit(start)
        return order

    def bfs(
        self,
        start: str,
        visited: Optional[Set[str]] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> List[str]:
        """
        从 start 开始广度优先遍历。

        Args:
            start: 起始节点。
            visited: 已访问集合；默认新建。
            callback: 每访问一个节点时调用 callback(node_id)。

        Returns:
            访问顺序的节点 ID 列表。
        """
        if visited is None:
            visited = set()
        order: List[str] = []
        q: deque = deque([start])
        visited.add(start)
        while q:
            n = q.popleft()
            if callback:
                callback(n)
            order.append(n)
            for succ in self.successors(n):
                if succ not in visited:
                    visited.add(succ)
                    q.append(succ)
        return order

    # -------------------------------------------------------------------------
    # 复制与序列化
    # -------------------------------------------------------------------------

    def copy(self) -> "Graph":
        """深拷贝图，得到独立的 Graph 实例。"""
        other = Graph(directed=self._directed)
        other._g = self._g.copy()
        return other

    def to_dict(self) -> Dict[str, Any]:
        """
        导出为可 JSON 序列化的字典。

        结构: {"directed": bool, "nodes": [{id, ...attrs}], "edges": [{u, v, ...attrs}]}
        属性值需为 JSON 可序列化类型。
        """
        nodes = []
        for n in self._g.nodes():
            attrs = self.get_node(n)
            d = {"id": n}
            if attrs:
                d.update(attrs)
            nodes.append(d)
        edges = []
        for u, v in self._g.edges():
            attrs = self.get_edge(u, v)
            d = {"u": u, "v": v}
            if attrs:
                d.update(attrs)
            edges.append(d)
        return {"directed": self._directed, "nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Graph":
        """
        从 to_dict 导出的字典构造图。

        Args:
            data: 须包含 "directed", "nodes", "edges"。
        """
        g = cls(directed=data.get("directed", True))
        for raw in data.get("nodes", []):
            node = dict(raw)
            nid = node.pop("id", None)
            if nid is not None:
                g.add_node(nid, **node)
        for raw in data.get("edges", []):
            edge = dict(raw)
            u = edge.pop("u", None)
            v = edge.pop("v", None)
            if u is not None and v is not None:
                g.add_edge(u, v, **edge)
        return g

    def to_graphml(self, path: Union[str, Path]) -> None:
        """
        导出为 GraphML 文件。

        Args:
            path: 输出文件路径。
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        nx.write_graphml(self._g, str(path))
        logger.info("Graph exported to GraphML: %s", path)

    @classmethod
    def from_graphml(cls, path: Union[str, Path], directed: bool = True) -> "Graph":
        """
        从 GraphML 文件加载图。

        Args:
            path: GraphML 文件路径。
            directed: 是否按有向图加载；若文件中含 directed 信息，以文件为准，
                      此处仅用于默认为有向图时新建 Graph 的类型。
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"GraphML file not found: {path}")
        nx_g = nx.read_graphml(str(path))
        g = cls(directed=directed)
        g._g = nx_g
        g._directed = nx_g.is_directed()
        logger.info("Graph loaded from GraphML: %s", path)
        return g

    def to_json(self, path: Optional[Union[str, Path]] = None) -> str:
        """
        导出为 JSON。若提供 path 则写入文件并返回路径字符串；否则返回 JSON 字符串。

        Args:
            path: 可选，输出文件路径。

        Returns:
            写入文件时返回 path 字符串，否则返回 JSON 字符串。
        """
        data = self.to_dict()
        if path is not None:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Graph exported to JSON: %s", path)
            return str(path)
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, source: Union[str, Path, Dict[str, Any]]) -> "Graph":
        """
        从 JSON 字符串、文件路径或字典加载图。

        Args:
            source: JSON 字符串、文件路径或 to_dict 格式的字典。
        """
        if isinstance(source, dict):
            return cls.from_dict(source)
        if isinstance(source, (str, Path)):
            p = Path(source)
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls.from_dict(data)
            data = json.loads(source)
            return cls.from_dict(data)
        raise TypeError("source must be str, Path, or dict")
