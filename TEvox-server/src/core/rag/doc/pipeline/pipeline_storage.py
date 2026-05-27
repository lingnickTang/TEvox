import hashlib
import json
import os
from typing import Union
from pydantic import BaseModel
import networkx as nx


class GlobalStorage:
    def __init__(self, config):
        self.data = {}
        root_path = config.get("global", "root_path")
        self.output_path = os.path.join(root_path, "output")
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)

    def set(
        self,
        key: str,
        value: Union[
            dict, list[dict], BaseModel, list[BaseModel], nx.DiGraph, list[nx.DiGraph]
        ],
    ):
        """Set data in the global storage."""
        if isinstance(value, BaseModel):
            value = value.model_dump()
        elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
            value = [v.model_dump() for v in value]
        elif isinstance(value, nx.DiGraph):
            value = nx.node_link_data(value)
        elif isinstance(value, list) and value and isinstance(value[0], nx.DiGraph):
            value = [nx.node_link_data(v) for v in value]
        self.data[key] = value
        self._save_to_file(key, value)

    def _save_to_file(self, key: str, value: Union[dict, list[dict]]):
        value_str = json.dumps(value, ensure_ascii=False)

        file = os.path.join(self.output_path, f"{key}.json")
        with open(file, "w", encoding="utf-8") as f:
            f.write(value_str)

    def _load_from_file(self, key: str):
        file = os.path.join(self.output_path, f"{key}.json")
        if not os.path.exists(file):
            return None
        with open(file, "r", encoding="utf-8") as f:
            value_str = f.read()
        return json.loads(value_str)

    def get(self, key: str):
        """Get data from the global storage."""
        if key not in self.data:
            self.data[key] = self._load_from_file(key)
        return self.data.get(key, None)

    def clear(self):
        """Clear the global storage."""
        self.data.clear()


class FileCache:
    """
    Set a file cache by hash key.
    """

    def __init__(self, config, prefix: str = "cache"):
        self.prefix = prefix
        self.cache_path = config.get("cache_path")
        if not self.cache_path:
            root_path = config.get("root_path")
            if root_path is None:
                root_path = config.get("global", "root_path")
            self.cache_path = os.path.join(root_path, "cache")
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)

    def _hash(self, key: str):
        return hashlib.md5(key.encode()).hexdigest()

    def save(self, key: str, value: str):
        key = self._hash(key)
        filename = self.prefix + "-" + key
        with open(os.path.join(self.cache_path, filename), "w") as f:
            f.write(value)

    def load(self, key: str) -> str:
        key = self._hash(key)
        filename = self.prefix + "-" + key
        path = os.path.join(self.cache_path, filename)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return f.read()
