from typing import List, Mapping
import networkx as nx

from typing import List, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import track
import networkx as nx

from src.utils import logger, get_embedding
from src.base import DefaultConfig


class NxGraphEmbedding:

    def __init__(self, config: dict):
        self.config = config
        self.embed_entity = config.get("embed_entity", False)
        self.embed_text_unit = config.get("embed_text_unit", False)
        self.max_workers = config.get("max_workers", 1)

        self.emb = get_embedding(
            openai_api_base=config.get("EMBEDDING_API_BASE") or DefaultConfig.embedding_api_base,
            openai_api_key=config.get("EMBEDDING_API_KEY") or DefaultConfig.embedding_api_key,
            model_name=config.get("EMBEDDING_MODEL") or DefaultConfig.embedding_model,
        )

    def embed_property(self, obj_list: List[dict], format_func: callable):
        if not obj_list:
            return obj_list

        def _process(obj):
            text = format_func(obj)

            if not text:
                logger.warning(f"{obj} is empty.")
                return
            embedding = self.emb.embed_documents([text])[0]
            obj["embedding"] = embedding
            return

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(_process, obj) for obj in obj_list]

            for i, future in enumerate(
                track(
                    as_completed(futures),
                    total=len(futures),
                    description=f"Embedding ...",
                )
            ):
                try:
                    future.result()

                except Exception as e:
                    logger.exception(e)
        return obj_list

    def run(self, inputs=None) -> List[nx.DiGraph]:
        if isinstance(inputs, list):
            G_list = []
            for input in inputs:
                G = self.run_single(input)
                G_list.append(G)
            return G_list
        else:
            return self.run_single(input)

    def run_single(self, inputs: Mapping = None) -> nx.DiGraph:
        G = nx.node_link_graph(inputs)
        logger.info(f"Loaded Graph: {len(G.nodes)} nodes, {len(G.edges)} edges")

        if self.embed_entity:
            logger.info("Embedding entities...")

            def format_entity(obj):
                description = obj.get("description")
                name = obj.get("name")
                if not description or not name:
                    return None
                return f"{name}: {description}"

            self.embed_property(
                [
                    G.nodes[node]
                    for node in G.nodes
                    if G.nodes[node].get("class_name") == "Entity"
                ],
                format_entity,
            )

        if self.embed_text_unit:
            logger.info("Embedding text units...")

            def format_text_unit(obj):
                return obj.get("content")

            self.embed_property(
                [
                    G.nodes[node]
                    for node in G.nodes
                    if G.nodes[node].get("class_name") == "TextUnit"
                ],
                format_text_unit,
            )

        return G
