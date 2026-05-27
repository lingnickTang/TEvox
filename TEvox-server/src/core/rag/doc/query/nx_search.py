import json
import os
from typing import List, Dict, Tuple
import ordered_set
import networkx as nx
import glob

from src.core.rag.doc.index.storage.dbs.lance import LanceDB
from src.core.rag.doc.pipeline.pipeline_storage import FileCache
from src.core.rag.doc.model import TextUnit, Entity
from src.core.rag.doc.agents.user_query.query_separation import query_seperation_agent
from src.utils import logger, get_embedding, get_llm, Agent
from src.base import DefaultConfig

class Retriever:
    def __init__(self, config: dict):
        self.config = config
        self.root_path = config.get("root_path")
        self.GRAPH_MAP = {}
        
        # 扫描可用文档库
        self.available_doc_repos = self._scan_available_doc_repos()
        
        # 记录上次选择的文档库
        self.last_selected_repo = None
        
        # 初始化时不立即创建cache和db，等选择文档库后再创建
        self.cache = None
        self.db = None
        
        # 只初始化embedding模型，这是共用的
        self.emb = get_embedding(
            openai_api_base=config.get("EMBEDDING_API_BASE") or DefaultConfig.embedding_api_base,
            openai_api_key=config.get("EMBEDDING_API_KEY") or DefaultConfig.embedding_api_key,
            model_name=config.get("EMBEDDING_MODEL") or DefaultConfig.embedding_model,
        )

    def _scan_available_doc_repos(self) -> List[str]:
        """扫描root_path下所有可用的文档库"""
        available_repos = []
        if os.path.exists(self.root_path):
            # 查找所有包含output/linked_graph.json的子目录
            for item in os.listdir(self.root_path):
                doc_path = os.path.join(self.root_path, item)
                if os.path.isdir(doc_path):
                    graph_path = os.path.join(doc_path, "output", "linked_graph.json")
                    if os.path.exists(graph_path):
                        available_repos.append(item)
        
        logger.info(f"Available document repositories: {available_repos}")
        return available_repos
    
    def _load_graph(self, doc_repo: str) -> None:
        """加载指定文档库的图"""
        if doc_repo in self.GRAPH_MAP:
            return  # 已经加载过
            
        nx_json_path = os.path.join(self.root_path, doc_repo, "output/linked_graph.json")
        if not os.path.exists(nx_json_path):
            logger.warning(f"Graph file does not exist: {nx_json_path}")
            return
            
        try:
            nx_dicts = json.load(open(nx_json_path, encoding="utf-8"))
            for nx_dict in nx_dicts:
                G = nx.node_link_graph(nx_dict)
                self.GRAPH_MAP[G.graph["source"]] = G
            logger.info(f"Loaded graph for {doc_repo}: {list(self.GRAPH_MAP.keys())}")
        except Exception as e:
            logger.error(f"Failed to load graph for {doc_repo}: {str(e)}")

    def select_doc_repo_agent(self, api_base=None, api_key=None, model_name=None, query=None, available_repos=None):
        """使用Agent选择最合适的文档库"""
        prompt = f"""
Please analyze the user query and select the most appropriate document repository from the available options. Return only the repository name without explanation.

Available repositories: {', '.join(available_repos)}

User query: {query}
"""
        return Agent(
            llm=get_llm(
                base_url=api_base or DefaultConfig.search_api_base,
                api_key=api_key or DefaultConfig.search_api_key,
                model_name=model_name or DefaultConfig.search_model,
            ),
            msgs=[],
        ).invoke(prompt).strip()

    def select_doc_repo(self, query: str) -> str:
        """根据查询选择最合适的文档库"""
        # 如果只有一个文档库，直接返回
        if len(self.available_doc_repos) == 1:
            selected_repo = self.available_doc_repos[0]
            return selected_repo
        
        # 如果没有文档库，返回错误
        if not self.available_doc_repos:
            raise ValueError("No document repositories available")
        
        try:
            # 使用Agent选择文档库
            response = self.select_doc_repo_agent(
                api_base=self.config.get("SEARCH_API_BASE"),
                api_key=self.config.get("SEARCH_API_KEY"),
                model_name=self.config.get("SEARCH_MODEL"),
                query=query,
                available_repos=self.available_doc_repos
            )
            
            # 检查响应是否为有效的文档库名称
            for repo in self.available_doc_repos:
                if repo in response:
                    selected_repo = repo
                    logger.info(f"Selected repo: {repo} for query: {query}")
                    return selected_repo
            
            # LLM未返回有效名称，使用第一个文档库
            selected_repo = self.available_doc_repos[0]
            logger.warning(f"LLM response invalid: {response}. Using first repo: {selected_repo}")
            return selected_repo
            
        except Exception as e:
            logger.error(f"Error selecting repo: {str(e)}")
            
            # 使用上次选择的文档库，若没有则使用第一个
            if self.last_selected_repo and self.last_selected_repo in self.available_doc_repos:
                return self.last_selected_repo
            else:
                selected_repo = self.available_doc_repos[0]
                return selected_repo

    # == APIs ==
    def retrieve(
        self,
        query: str,
        entry_limit: int = 3,
        max_depth=3,
        query_seperation=True,
        similarity_threshold=0.4,
        doc_repo=None,
    ) -> list[TextUnit]:
        """Retrieve the textunits for the given query."""
        # 选择文档库
        if doc_repo is None:
            doc_repo = self.select_doc_repo(query)
        
        # 确保已为该文档库初始化缓存和数据库
        self._ensure_cache_and_db(doc_repo)
        
        # 加载图
        self._load_graph(doc_repo)
        
        group_textunits, _ = self.retrieve_textunit_with_entities_by_group(
            query,
            entry_limit=entry_limit,
            max_depth=max_depth,
            query_seperation=query_seperation,
            similarity_threshold=similarity_threshold,
            verbose=False,
            doc_repo=doc_repo,
        )
        merged_text_units: list[TextUnit] = []

        # Get the maximum length among all groups
        max_group_length = max(
            len(text_units) for text_units in group_textunits.values()
        ) if group_textunits else 0

        # Interleave the text units from different groups
        for i in range(max_group_length):
            for group_text_units in group_textunits.values():
                if i < len(group_text_units):
                    merged_text_units.append(group_text_units[i])

        return merged_text_units

    def retrieve_by_textunit_embedding(
        self, query: str, query_seperation=True, doc_repo=None
    ) -> list[TextUnit]:
        """Retrieve the textunits by textunit embedding."""
        # 如果没有指定文档库，根据查询选择最合适的文档库
        if doc_repo is None:
            doc_repo = self.select_doc_repo(query)
        
        # 确保已为该文档库初始化缓存和数据库
        self._ensure_cache_and_db(doc_repo)
        
        # 加载指定文档库的图
        self._load_graph(doc_repo)
        
        if query_seperation:
            group_queries = self.seperate_user_query(query)
        else:
            group_queries = {graph_name: query for graph_name in self.GRAPH_MAP.keys()}

        group_textunits = self._retrieve_textunits_with_seperate_queries(
            group_queries, limit=20, threshold=0.3
        )

        # Merge the text units from different graphs
        merged_text_units: list[TextUnit] = []
        for text_units in group_textunits.values():
            merged_text_units.extend(text_units)

        # sort by score
        merged_text_units.sort(key=lambda x: x.score, reverse=True)
        return merged_text_units

    def retrieve_textunit_with_entities_by_group(
        self,
        query: str,
        entry_limit: int = 5,
        max_depth=3,
        query_seperation=False,
        similarity_threshold=0.4,
        verbose=True,
        doc_repo=None,
    ) -> tuple[dict[str, List[TextUnit]], dict[str, List[str]]]:
        """
        Retrieve the textunits and entities for the given query.
        Return the textunits and entities for each graph."""
        # 如果没有指定文档库，根据查询选择最合适的文档库
        if doc_repo is None:
            doc_repo = self.select_doc_repo(query)
        
        # 确保已为该文档库初始化缓存和数据库
        self._ensure_cache_and_db(doc_repo)
        
        # 加载指定文档库的图
        self._load_graph(doc_repo)
        
        if query_seperation:
            group_queries = self.seperate_user_query(query)
            if verbose:
                logger.info(f"Group sub_queries: {group_queries}")
            group_entities = self._retrieve_entities_with_seperate_queries(
                group_queries, limit=entry_limit, threshold=similarity_threshold
            )
        else:
            group_entities = self._retrieve_entities_for_each_graph(
                query, limit=entry_limit, threshold=similarity_threshold
            )

        final_group_entities = {}
        final_group_textunits = {}
        for graph_name, entities in group_entities.items():
            entry_entity_ids = [row.id for row in entities]

            if verbose:
                entry_with_score = [(row.id, row.score) for row in entities]
                logger.info(f"Entry nodes for {graph_name}: {entry_with_score}")
            selected_entity_ids = self._bfs_find_entities(
                graph_name, entry_entity_ids, max_depth=max_depth
            )
            selected_textunits = self._get_definition_textunits(
                graph_name, selected_entity_ids
            )
            final_group_entities[graph_name] = selected_entity_ids
            final_group_textunits[graph_name] = selected_textunits

        return final_group_textunits, final_group_entities

    # == Agents ==
    def seperate_user_query(self, query: str) -> dict[str, str]:
        """Use LLM to seperate the user query into subqueries for each graph."""
        graph_sources = self.GRAPH_MAP.keys()
        document_list = list(graph_sources)
        document_list.sort()
        res = query_seperation_agent(
            api_base=self.config.get("SEARCH_API_BASE"),
            api_key=self.config.get("SEARCH_API_KEY"),
            model_name=self.config.get("SEARCH_MODEL"),
            document_list=document_list,
            user_query=query,
        ).model_dump()
        group_queries = {r["document"]: r["sub_query"] for r in res["sub_queries"]}
        return group_queries

    # == Group Search Algorithms ==
    def _retrieve_entities_for_each_graph(
        self, query: str, limit: int = 5, threshold=0.5
    ) -> dict[str, List[Entity]]:
        """Use the embedding of the query to search entities in each graph."""
        emb_query = self.emb.embed_query(query)
        group_results = {}
        
        # 为每个已加载的图搜索对应的表
        for graph_name in self.GRAPH_MAP.keys():
            results = self.db.vector_search(emb_query, graph_name, limit)
            group_results[graph_name] = results
        
        group_entities = {}
        for graph_name, results in group_results.items():
            if results:  # 如果有结果
                entities = [Entity(**row) for row in results if row["score"] > threshold]
                group_entities[graph_name] = entities
            else:
                logger.warning(f"No results found for graph: {graph_name}")
                group_entities[graph_name] = []
        return group_entities

    def _retrieve_entities_with_seperate_queries(
        self, group_queries: dict[str, str], limit: int = 5, threshold=0.5
    ) -> dict[str, List[Entity]]:
        """Use seperate queries to search entities in corresponding graph."""
        group_entities = {}
        for graph_name, query in group_queries.items():
            if not query:
                continue
            emb_query = self.emb.embed_query(query)
            results = self.db.vector_search(emb_query, graph_name, limit)
            if results:  # 如果有结果
                entities = [Entity(**row) for row in results if row["score"] > threshold]
                group_entities[graph_name] = entities
            else:
                logger.warning(f"No results found for graph: {graph_name}")
                group_entities[graph_name] = []
        return group_entities

    def _bfs_find_entities(
        self, graph_source: str, start_nodes: List[str], max_depth: int = 5
    ) -> list[str]:
        """Find all reachable entities from start_nodes in the graph."""
        G = self.GRAPH_MAP[graph_source]
        reachable_nodes = ordered_set.OrderedSet()
        # breadth first search
        queue = [(node, 0) for node in start_nodes]
        while queue:
            node, depth = queue.pop(0)
            if depth > max_depth:
                continue
            reachable_nodes.add(node)
            for neighbor in G.neighbors(node):
                if neighbor not in reachable_nodes:
                    queue.append((neighbor, depth + 1))

        return list(reachable_nodes)

    def _get_definition_textunits(
        self, graph_source: str, entity_ids: List[str]
    ) -> list[TextUnit]:
        G = self.GRAPH_MAP[graph_source]
        textunit_nodes = []
        visited_textunits = set()
        for entity_id in entity_ids:
            for source, _, edge_data in G.in_edges(entity_id, data=True):
                if (
                    edge_data.get("document_relation") == "DEFINE"
                    and G.nodes[source].get("class_name") == "TextUnit"
                ):
                    if source in visited_textunits:
                        continue
                    visited_textunits.add(source)
                    node_data = dict(G.nodes[source])
                    node_data.pop("embedding", None)
                    textunit_nodes.append(TextUnit(**node_data))
        return textunit_nodes

    def _retrieve_textunits_with_seperate_queries(
        self, group_queries: dict[str, str], limit: int = 20, threshold=0.3
    ) -> dict[str, List[Entity]]:
        group_textunits = {}
        for graph_name, query in group_queries.items():
            if not query:
                continue
            emb_query = self.emb.embed_query(query)
            results = self.db.vector_search(emb_query, graph_name + "_textunit", limit)
            if results:  # 如果有结果
                textunits = [TextUnit(**row) for row in results if row["score"] > threshold]
                group_textunits[graph_name] = textunits
            else:
                logger.warning(f"No results found for graph: {graph_name}_textunit")
                group_textunits[graph_name] = []
        return group_textunits

    def _init_cache_and_db(self, doc_repo: str):
        """为指定文档库初始化缓存和数据库"""
        if doc_repo is None:
            raise ValueError("Document repository must be specified")
        
        # 创建特定于文档库的配置
        repo_config = self.config.copy()
        repo_config["root_path"] = os.path.join(self.root_path, doc_repo)
        
        # 初始化缓存和数据库
        self.cache = FileCache(repo_config, prefix="retrieval")
        self.db = LanceDB(repo_config)
        logger.info(f"Initialized cache and database for repository: {doc_repo}")
    
    def _ensure_cache_and_db(self, doc_repo: str):
        """确保为当前文档库正确初始化了缓存和数据库"""
        # 如果当前没有初始化缓存和数据库，则重新初始化
        if self.cache is None or self.db is None or self.last_selected_repo != doc_repo:
            # 如果切换了文档库，清除之前的图
            if self.last_selected_repo != doc_repo:
                self.GRAPH_MAP.clear()
                logger.info(f"Cleared graph cache when switching from {self.last_selected_repo} to {doc_repo}")
            
            self._init_cache_and_db(doc_repo)
            # 更新 last_selected_repo 为当前使用的文档库
            self.last_selected_repo = doc_repo


if __name__ == "__main__":
    config = {"root_path": ".rag"}
    retriever = Retriever(config)
    
    # 显示所有可用文档库
    print(f"Available repositories: {retriever.available_doc_repos}")
    
    # 测试不同查询
    test_queries = [
        "How to initialize GPIO by I2C?",
        "ESP32 GPIO configuration",
        #"JLAC7013 earphone datasheet description",
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        
        # 选择并显示所选的文档库
        selected_repo = retriever.select_doc_repo(query)
        print(f"Selected repository: {selected_repo}")
        
        # 检索结果
        texts = retriever.retrieve(
            query,
            entry_limit=3,
            query_seperation=True,
            similarity_threshold=0.4,
            max_depth=1,
            doc_repo=selected_repo,  # 明确传入已选择的文档库
        )
        
        # 显示结果
        print(f"Found {len(texts)} relevant text units:")
        for i, text in enumerate(texts[:3]):  # 只显示前3个结果
            print(f"\n=== Result {i+1} " + "="*50)
            # 显示文本单元的源信息
            if hasattr(text, 'source'):
                print(f"Source: {text.source}")
            
            # 显示文本单元的元数据
            if hasattr(text, 'metadata') and text.metadata:
                print(f"Metadata: {text.metadata}")
            
            # 显示分数（如果有）
            if hasattr(text, 'score') and text.score is not None:
                print(f"Relevance Score: {text.score:.4f}")
            
            # 显示完整内容
            print("\nContent:")
            print("-" * 70)
            content = text.llm_content if hasattr(text, 'llm_content') and text.llm_content else text.content
            
            # 显示更多内容
            max_display_length = 1000  # 显示更多字符
            if len(content) > max_display_length:
                print(f"{content[:max_display_length]}...\n[Content truncated, total length: {len(content)} chars]")
            else:
                print(content)
            print("-" * 70)

    # textunits = retriever.retrieve_by_textunit_embedding(query, query_seperation=True)
    # print(textunits)

    # texts = retriever.retrieve(
    #     query,
    #     entry_limit=3,
    #     query_seperation=True,
    #     similarity_threshold=0.4,
    #     max_depth=1,
    # )
    # for i, text in enumerate(texts):
    #     logger.info(f"{i}: {text.llm_content}")
    # print(len(texts))

    # group_entities = retriever.retrieve_entities(query, limit=5, threshold=0.5)
    # print(group_entities)

    # direct search by textunit embedding
