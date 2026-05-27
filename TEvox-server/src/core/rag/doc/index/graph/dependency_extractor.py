import json
from typing import List, Mapping
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import track
import networkx as nx

from src.core.rag.doc.model.text_unit import TextUnit
from src.core.rag.doc.pipeline.pipeline_storage import FileCache
from src.core.rag.doc.agents.knowledge_extraction.dependency_extraction import (
    dependency_extraction_agent,
)
from src.utils import logger


class DependencyExtractor:

    SCHEMA = [
        {
            "source": "CODE",
            "relationship": "USE",
            "target": "CODE",
        },
        {
            "source": "SEMANTIC",
            "relationship": "CONTAIN",
            "target": "SEMANTIC",
        },
        {
            "source": "SEMANTIC",
            "relationship": "IMPLEMENT",
            "target": "CODE",
        },
    ]
    AVAILABLE_ENTITY_TYPE = [
        "FUNCTION",
        "STRUCT",
        "MACRO",
        "ENUM",
        "FILE_NAME",
        "PIN",
        "REGISTER_NAME",
        "DATA_TYPE",
    ] + ["TASK", "SYSTEM_MODULE"]

    def __init__(self, config: dict):
        self.config = config
        self.max_workers = config.get("max_workers", 1)
        self.cache = FileCache(config, prefix="dependency_extractor")
        self.actor = dependency_extraction_agent(
            api_base=config.get("RAG_API_BASE"),
            api_key=config.get("RAG_API_KEY"),
            model_name=config.get("RAG_MODEL")
        )

    def _extract_relations(self, document: str, entity_set_str: str) -> str:
        cache_key = (
            f"{self.actor.llm.model_name}{self.actor.prompt}{document}{entity_set_str}"
        )

        res = self.cache.load(cache_key)
        if res:
            return res
        else:
            res = self.actor.invoke(
                {"document": document, "entity_set": entity_set_str}
            )
            self.cache.save(cache_key, res)

        return res

    def validate_relation(
        self, relation: dict[str, str], textunit_id: str, G: nx.DiGraph
    ) -> bool:

        source_data = G.get_edge_data(textunit_id, relation["source"])
        target_data = G.get_edge_data(textunit_id, relation["target"])

        # Validate the node type

        if (
            source_data.get("type") not in self.AVAILABLE_ENTITY_TYPE
            or target_data.get("type") not in self.AVAILABLE_ENTITY_TYPE
        ):
            return False

        # print(source_data)
        for schema in self.SCHEMA:
            if (
                schema["relationship"] == relation["relationship"]
                and schema["source"] == source_data.get("kind")
                and schema["target"] == target_data.get("kind")
            ):
                return True

        return False

    def _process_results(self, results: Mapping[str, str], G: nx.DiGraph) -> nx.DiGraph:
        """Add dependencies to the graph"""

        for textunit_id, result in results.items():
            try:
                relations = json.loads(result)
                for rel in relations:
                    s = rel["source"]
                    t = rel["target"]
                    if not (G.has_node(s) and G.has_node(t)):
                        logger.warning(
                            f"Node not found: `{s}` or `{t}` in {textunit_id}, Graph: {G.graph['source']}. Skipping..."
                        )
                        continue

                    if not self.validate_relation(rel, textunit_id, G):
                        logger.warning(
                            f"Invalid relation: {rel} in {textunit_id}, Graph: {G.graph['source']}. Skipping..."
                        )
                        continue

                    G.add_edge(s, t, dependency=rel["relationship"])
            except Exception as e:
                logger.exception(e)

        return G

    def _get_neighbour_entities(self, G: nx.DiGraph, textunit_id: str) -> List[str]:
        neibour_edges = []
        for _, e, edge_data in G.edges(textunit_id, data=True):
            if G.nodes[e].get("class_name") == "Entity":
                neibour_edges.append(edge_data)
        return neibour_edges

    def run(self, inputs: List = None) -> List[nx.DiGraph]:
        """
        inputs[0]: List[TextUnit]
        inputs[1]: List[Graph]
        """

        textunits = [TextUnit(**x) for x in inputs[0]]
        self.id_to_textunit = {textunit.id: textunit for textunit in textunits}

        # NOTE: for test:
        if not isinstance(inputs[1], list):
            graphs = [nx.node_link_graph(inputs[1])]
            graphs[0].graph["source"] = "default"
        else:
            graphs = [nx.node_link_graph(x) for x in inputs[1]]

        self.id_to_graph: dict[str, nx.DiGraph] = {
            graph.graph["source"]: graph for graph in graphs
        }

        group_results: dict[str, dict[str, str]] = {}  # source -> textunit_id -> result

        logger.info(f"Loaded: {len(textunits)} TextUnits, {len(graphs)} Graphs")

        def process_extraction(textunit: TextUnit, entity_set_str: str):
            return (
                self._extract_relations(textunit.llm_content, entity_set_str),
                textunit.id,
            )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for textunit in textunits:
                textunit_id = textunit.id
                source = textunit.source

                neibour_edges = []
                neibour_entities = self._get_neighbour_entities(
                    self.id_to_graph[source], textunit_id
                )
                for edge_data in neibour_entities:
                    format_data = "({kind}<|>{name}<|>{type}<|>{description})##"
                    neibour_edges.append(format_data.format(**edge_data))

                entity_set_str = "\n".join(neibour_edges)
                future = executor.submit(
                    copy_context().run, process_extraction, textunit, entity_set_str
                )
                futures.append(future)

            for future in track(
                as_completed(futures),
                description=f"Processing `Relation Extraction`... (total: {len(futures)})",
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
        for source, results in group_results.items():
            self._process_results(results, self.id_to_graph[source])

        return graphs
