import os
from typing import List
import networkx as nx
import lancedb
import numpy as np

from src.utils import logger


class LanceDB:
    def __init__(self, config: dict):
        self.config = config
        lance_config = config.get("lancedb", {})
        root_path = config.get("root_path")
        url = lance_config.get("url", "storage/lancedb")
        url = os.path.join(root_path, url)
        self.store = lancedb.connect(url)

    def get_table_names(self, type: str = "Entity") -> List[str]:
        sources = []
        for t in self.store.table_names():
            if type == "Entity":
                if not t.endswith("_textunit"):
                    sources.append(t)
            elif type == "TextUnit":
                if t.endswith("_textunit"):
                    sources.append(t)
            else:
                raise ValueError(f"Invalid table type: {type}")

        return sources

    def import_base_graph(self, graph: nx.DiGraph):
        # Extract node data
        table_name = graph.graph.get("source", "Graph")

        node_list = []
        for node, data in graph.nodes(data=True):
            if data.get("class_name") == "Entity":
                embedding = data.get("embedding")
                if embedding is None:
                    continue
                data.pop("embedding")
                node_list.append(
                    {
                        "id": node,
                        **data,
                        "vector": np.array(embedding, dtype=np.float32),
                    }
                )
        # Create or overwrite the table
        if table_name in self.get_table_names(type="Entity"):
            self.store.drop_table(table_name)

        table = self.store.create_table(table_name, data=node_list, mode="overwrite")

        # NOTE: Only if the size of the table is large enough, you should create an index
        # table.create_index(
        #     replace=True,
        #     metric="cosine",
        #     num_sub_vectors=1,
        #     num_partitions=1
        # )

        logger.info(
            f"LanceDB: Successfully imported {len(node_list)} entities to table '{table_name}'."
        )

    def import_textunits(self, graph: nx.DiGraph):

        table_name = graph.graph.get("source", "Graph") + "_textunit"
        node_list = []
        for node, data in graph.nodes(data=True):
            if data.get("class_name") == "TextUnit":
                embedding = data.get("embedding")
                if embedding is None:
                    continue
                data.pop("embedding")
                node_list.append(
                    {
                        "id": node,
                        **data,
                        "vector": np.array(embedding, dtype=np.float32),
                    }
                )

        if table_name in self.get_table_names(type="TextUnit"):
            self.store.drop_table(table_name)

        table = self.store.create_table(table_name, data=node_list, mode="overwrite")
        logger.info(
            f"LanceDB: Successfully imported {len(node_list)} textunits to table '{table_name}'."
        )

    def vector_search(
        self, embedding: List[float], table_name: str, limit=10
    ) -> List[dict]:
        """Return: List of (node, score)"""
        try:
            table = self.store.open_table(table_name)
            
            results = table.search(embedding).metric("cosine").limit(limit).to_pandas()
            
            # remove the vector column
            results = results.drop(columns=["vector"])
            # rename the _distance column to score
            results = results.rename(columns={"_distance": "score"})
            # change score to 1 - score
            results["score"] = 1 - results["score"]
            return results.to_dict(orient="records")
        except Exception as e:
            logger.error(f"Error searching table {table_name}: {str(e)}")
            return []  # 返回空列表而不是抛出异常

    def vector_search_all_tables(
        self, embedding: List[float], limit=10, type="Entity"
    ) -> dict:
        """Return: {table_name: List of (node, score)}"""
        results = {}
        for table_name in self.get_table_names(type=type):
            results[table_name] = self.vector_search(embedding, table_name, limit)
        return results
