from typing import List, Mapping
import networkx as nx
import numpy as np

from src.utils import logger


class SemanticEntityLinker:

    def __init__(self, config: dict):
        self.config = config
        self.max_workers = config.get("max_workers", 1)
        self.threshold = config.get("threshold", 0.8)

    def group_entities_by_document(
        self, G: nx.DiGraph, entity_filter: dict[str, str] = None
    ) -> dict[str, set[str]]:
        document_to_entities = {}

        def match_filter(node):
            if entity_filter:
                for key, value in entity_filter.items():
                    if G.nodes[node].get(key) != value:
                        return False
            return True

        for text_node, data in G.nodes(data=True):
            if data.get("class_name") == "TextUnit":
                document_id = data.get("document_id")
                if document_id not in document_to_entities:
                    document_to_entities[document_id] = set()
                for neighbor in G.neighbors(text_node):
                    neighbor_data = G.nodes[neighbor]
                    if (
                        neighbor_data.get("class_name") == "Entity"
                        and neighbor_data.get("embedding") is not None
                    ):
                        if match_filter(neighbor):
                            document_to_entities[document_id].add(neighbor)

        return document_to_entities

    def process_entity_linking_by_embedding(
        self, G: nx.DiGraph, entities: List[str], threshold: float = 0.8
    ) -> None:
        """Link entities by comparing their embeddings and add "EQUAL" relations to the graph"""
        embeddings = [G.nodes[entity]["embedding"] for entity in entities]
        embeddings = np.array(embeddings)
        similarity_matrix = np.dot(embeddings, embeddings.T)

        for i in range(similarity_matrix.shape[0]):
            for j in range(i + 1, similarity_matrix.shape[1]):
                if similarity_matrix[i][j] < threshold:
                    continue

                # Add EQUAL relation
                G.add_edge(entities[i], entities[j], kind="EQUAL")
                G.add_edge(entities[j], entities[i], kind="EQUAL")

                # print(f"{entities[i]} <--> {entities[j]} ({similarity_matrix[i][j]})")

    def link_entity_by_embedding(
        self,
        G: nx.DiGraph,
        node_kind="SEMANTIC",
        threshold=0.8,
    ) -> None:
        document_to_entities = self.group_entities_by_document(
            G, entity_filter={"kind": node_kind}
        )
        for document_id, entities in document_to_entities.items():
            if len(entities) < 2:
                logger.warning(
                    f"Document {document_id} has less than 2 entities, skipping..."
                )
                continue
            logger.info(
                f"Processing {len(entities)} entities in document {document_id}"
            )
            self.process_entity_linking_by_embedding(G, list(entities), threshold)

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

        self.link_entity_by_embedding(G, threshold=self.threshold)

        return G
