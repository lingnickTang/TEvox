import os

from langchain_openai.chat_models import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore

from src.base import DefaultConfig

# from langchain.globals import set_debug
# set_debug(True)


def get_llm(
    model_name: str = DefaultConfig.openai_llm_reasoning_model,
    cache_path: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../.cache/.llm.db")
    ),
    max_retries: int = 3,
    **kwargs,
):
    llm = ChatOpenAI(model=model_name, max_retries=max_retries, **kwargs)

    if cache_path:
        cache_dir = os.path.dirname(cache_path)
        os.makedirs(cache_dir, exist_ok=True)
        set_llm_cache(SQLiteCache(database_path=cache_path))

    return llm


def get_embedding(
    model_name: str = DefaultConfig.embedding_model,
    cache_path: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../.cache/.emd.db")
    ),
    **kwargs,
):
    emb = OpenAIEmbeddings(model=model_name, **kwargs)

    if cache_path:
        cache_dir = os.path.dirname(cache_path)
        os.makedirs(cache_dir, exist_ok=True)
        store = LocalFileStore(cache_path)
        emb = CacheBackedEmbeddings.from_bytes_store(
            underlying_embeddings=emb,
            document_embedding_cache=store,
            namespace=emb.model,
            query_embedding_cache=True,
        )

    return emb

import dashscope

def get_dashscope_embedding(model):
    """Get a dashscope embedding instance with the specified model."""
    return dashscope_embedding(model=model)

class dashscope_embedding:
    """DashScope embedding class for text embedding operations."""
    
    def __init__(self, model):
        """
        Initialize the dashscope embedding instance.
        
        Args:
            model (str): The embedding model to use. Defaults to "text-embedding-v4".
        """
        dashscope.api_base = DefaultConfig.dashscope_api_base
        dashscope.api_key = DefaultConfig.dashscope_api_key
        self.model = model
    
    def embed_query(self, input_text: str):
        """
        Embed a query text using DashScope TextEmbedding.
        
        Args:
            input_text (str): The text to embed.
            
        Returns:
            The response from dashscope.TextEmbedding.call
        """
        response = dashscope.TextEmbedding.call(
            model=self.model,
            input=input_text
        )
        return response["output"]["embeddings"][0]["embedding"]