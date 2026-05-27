import json
from typing import List, Mapping
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import track
import networkx as nx

from src.core.rag.doc.agents.entity_summary.entity_summary import entity_summary_agent
from src.core.rag.doc.pipeline.pipeline_storage import FileCache
from src.utils import logger


class EntityDescriptionExtractor:
    def __init__(self, config: dict):
        self.config = config
        self.max_workers = config.get("max_workers", 1)
        self.cache = FileCache(config, prefix="entity_summary")
        self.entity_summarizer = entity_summary_agent(
            api_base=config.get("RAG_API_BASE"),
            api_key=config.get("RAG_API_KEY"),
            model_name=config.get("RAG_MODEL")
        )

    def _summarize_description(
        self, entity_name: str, description_list: List[str]
    ) -> str:
        description_list.sort()
        cache_key = f"{self.entity_summarizer.llm.model_name}{self.entity_summarizer.prompt}{entity_name}{description_list}"

        res = self.cache.load(cache_key)
        if res:
            return res
        else:
            res = self.entity_summarizer.invoke(
                {
                    "entity_name": entity_name,
                    "description_list": description_list,
                }
            )
            self.cache.save(cache_key, res)

        return res

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

        nodes_to_process = []  # List of <node, description_list> pair to process

        # 1. Update node attributes
        for node in G.nodes:
            if G.nodes[node].get("class_name") != "Entity":
                continue
            in_edges = G.in_edges(node, data=True)

            in_edges = [
                (u, v, data) for u, v, data in in_edges if data.get("document_relation")
            ]
            if not in_edges:
                continue

            description_setted = False
            # Directly set the description if there is a DEFINE relation
            for _, _, data in in_edges:
                if data.get("document_relation") == "DEFINE" or len(in_edges) == 1:
                    G.nodes[node].update(data)
                    description_setted = True
                    break
            # Otherwise, call the entity summarizer later to generate a description
            # Prepare the data here.
            if not description_setted:
                temp_data = in_edges[0][2]
                G.nodes[node].update(
                    temp_data
                )  # Temporarily update the node with the first candidate
                candidates = [
                    f"{data.get('type')}: {data.get('description')}"
                    for _, _, data in in_edges
                ]
                nodes_to_process.append((node, candidates))

        # 2. Process the entity summarizer
        def process_extraction(pair):
            return self._summarize_description(pair[0], pair[1]), pair[0]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(copy_context().run, process_extraction, pair)
                for pair in nodes_to_process
            ]
            for future in track(
                as_completed(futures),
                description=f"Processing `EntityDescriptionExtractor`... (total: {len(nodes_to_process)})",
                total=len(futures),
            ):
                try:
                    result, node = future.result()
                    result = json.loads(result)
                    G.nodes[node].update(result)
                except Exception as e:
                    logger.exception(e)

        return G
