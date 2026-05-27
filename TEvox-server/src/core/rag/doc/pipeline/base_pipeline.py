import json
import os
from langchain_community.callbacks import get_openai_callback

from src.core.rag.doc.index.text_splitting import DocumentLoader, TextUnitExtractor
from src.core.rag.doc.index.graph import EntityExtractor
from src.core.rag.doc.index.graph.dependency_extractor import DependencyExtractor
from src.core.rag.doc.index.graph.entity_summary import EntityDescriptionExtractor
from src.core.rag.doc.index.graph.nx_graph_embedding import NxGraphEmbedding
from src.core.rag.doc.index.graph.entity_linking import SemanticEntityLinker
from src.core.rag.doc.index.storage.nx_graphdb_creator import NxGraphDBCreator
from src.core.rag.doc.pipeline.pipeline_storage import GlobalStorage
from src.utils import logger

STEP_MAPPING = {
    "DocumentLoader": DocumentLoader,
    "TextUnitExtractor": TextUnitExtractor,
    "EntityExtractor": EntityExtractor,
    "DependencyExtractor": DependencyExtractor,
    "EntityDescriptionExtractor": EntityDescriptionExtractor,
    "NxGraphEmbedding": NxGraphEmbedding,
    "SemanticEntityLinker": SemanticEntityLinker,
    "NxGraphDBCreator": NxGraphDBCreator,
}


class BasePipeline:
    def __init__(self, config):
        self.config = config
        global_config = config.get("global")
        root_path = global_config.get("root_path")
        self.statistics_path = os.path.join(root_path, "statistics")
        os.makedirs(self.statistics_path, exist_ok=True)

        steps = []
        for step in config.get("steps", default=[]):
            name = list(step.keys())[0]
            values = step[name]
            # Add global configuration to each step
            values.update(global_config)
            steps.append(STEP_MAPPING[name](values))
        self.steps = steps
        logger.info(f"Adding steps: {[step.__class__.__name__ for step in steps]}")
        self.storage = GlobalStorage(config)

    def save_api_statistics(self, cb, step_name):
        cb_dict = {k: v for k, v in cb.__dict__.items() if not k.startswith("_")}
        logger.info(f"{step_name} - API Usage: {cb}")

        with open(f"{self.statistics_path}/{step_name}.json", "w") as f:
            json.dump(cb_dict, f, indent=4)

    def run(self):
        for step in self.steps:
            logger.info(f"Running step: {step.__class__.__name__}")
            input_key = step.config.get("input", None)

            inputs = None
            if input_key:
                if isinstance(input_key, list):
                    inputs = [self.storage.get(key) for key in input_key]
                else:
                    inputs = self.storage.get(input_key)

            with get_openai_callback() as cb:
                res = step.run(inputs)
                self.save_api_statistics(cb, step.__class__.__name__)

            if res:
                self.storage.set(step.config.get("output"), res)
            logger.info(f"Completed step: {step.__class__.__name__}")
