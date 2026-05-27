import json
from typing import List, Mapping
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import track
import networkx as nx

from src.core.rag.doc.model.text_unit import TextUnit
from src.core.rag.doc.pipeline.pipeline_storage import FileCache
from src.core.rag.doc.agents.knowledge_extraction.entity_extraction import (
    entity_extraction_agent,
)
from src.utils import logger


class EntityExtractor:
    def __init__(self, config: dict):
        self.config = config
        self.max_workers = config.get("max_workers", 1)
        self.cache = FileCache(config, prefix="entity_extractor")
        #self.actor = entity_extraction_agent()
        self.actor = entity_extraction_agent(
            api_base=config.get("RAG_API_BASE"),
            api_key=config.get("RAG_API_KEY"),
            model_name=config.get("RAG_MODEL")
        )

    def _extract_entities(self, text: str) -> str:
        cache_key = f"{self.actor.llm.model_name}{self.actor.prompt}{text}"

        res = self.cache.load(cache_key)
        if res:
            return res
        else:
            res = self.actor.invoke(
                {
                    "input": text,
                }
            )
            self.cache.save(cache_key, res)

        return res

    def _process_results(self, results: Mapping[str, str]) -> nx.DiGraph:
        G = nx.DiGraph()
        # 1. Adding all text units as nodes
        for textunit_id in results.keys():
            textunit = self.id_to_textunit[textunit_id]
            G.add_node(textunit_id, class_name="TextUnit", **textunit.model_dump())

        # 2. Adding all entities as nodes, and edges between text units and entities
        # Saving inferenced entity attributes on the edge
        for textunit_id, result in results.items():
            try:
                entities = json.loads(result)
                for entity in entities:
                    node = entity["name"]
                    if not G.has_node(node):
                        G.add_node(node, class_name="Entity")
                    G.add_edge(textunit_id, node, **entity)
            except Exception as e:
                logger.exception(e)

        return G

    def run(self, inputs: List[TextUnit] = None) -> List[nx.DiGraph]:
        textunits = [TextUnit(**x) for x in inputs]
        self.id_to_textunit = {textunit.id: textunit for textunit in textunits}

        group_results: dict[str, dict[str, str]] = {}  # source -> textunit_id -> result

        logger.info(f"Loaded: {len(textunits)} TextUnits")

        # Extract entities from each text unit

        def process_extraction(textunit):
            return self._extract_entities(textunit.llm_content), textunit.id

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(copy_context().run, process_extraction, textunit)
                for textunit in textunits
            ]
            for future in track(
                as_completed(futures),
                description=f"Processing `Entity Extraction`... (total: {len(futures)})",
                total=len(futures),
            ):
                try:
                    result, textunit_id = future.result()
                    source = self.id_to_textunit[textunit_id].source
                    if source not in group_results:
                        group_results[source] = {}
                    group_results[source][textunit_id] = result
                except Exception as e:
                    logger.exception(e)

        # Group the results by source
        nx_graphs = []
        for source, results in group_results.items():
            nx_graph = self._process_results(results)
            nx_graph.graph["source"] = source
            nx_graphs.append(nx_graph)

        return nx_graphs
