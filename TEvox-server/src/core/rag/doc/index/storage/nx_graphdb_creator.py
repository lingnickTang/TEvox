from typing import Mapping
import networkx as nx

from src.core.rag.doc.index.storage.dbs.lance import LanceDB


class NxGraphDBCreator:
    def __init__(self, config: dict):
        self.config = config
        self.db = LanceDB(config)
        self.import_textunits = config.get("import_textunits", False)

    def run(self, inputs: Mapping) -> None:

        for input in inputs:
            G = nx.node_link_graph(input)
            self.db.import_base_graph(G)
            if self.import_textunits:
                self.db.import_textunits(G)

        return None
