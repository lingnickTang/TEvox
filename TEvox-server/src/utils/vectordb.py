from typing import List, Union

import lancedb

from src.utils import logger


class LanceDB:
    def __init__(self, url: str):
        self.store = lancedb.connect(url)

    def get_table_names(self, tables: Union[str, List[str]]) -> List[str]:
        all_tables = self.store.table_names()

        if tables is None:
            return all_tables

        if isinstance(tables, str):
            tables = [tables]

        return [t for t in all_tables if t in tables]

    def append_data(self, table: str, data: List[dict]):
        table_exists = table in self.store.table_names()

        if table_exists:
            logger.info(f"Opening existing table '{table}' to append data")
            table = self.store.open_table(table)
            logger.info(f"Appending {len(data)} records to table '{table}'")
            table.add(data)
            logger.info(f"Successfully appended data to table '{table}'")
        else:
            logger.info(f"Creating new table '{table}' with initial data")
            table = self.store.create_table(table, data)
            logger.info(
                f"Successfully created table '{table}' with {len(data)} records"
            )

    def vector_search(self, table: str, embedding: List[float], limit=10) -> List[dict]:
        # check if table exist, if not, return none
        table_exists = table in self.store.table_names()
        if not table_exists:
            return None

        table = self.store.open_table(table)
        results = table.search(embedding).metric("cosine").limit(limit).to_pandas()
        # remove the vector column
        results = results.drop(columns=["vector"])
        # rename the _distance column to score
        results = results.rename(columns={"_distance": "score"})
        # change score to 1 - score
        results["score"] = 1 - results["score"]
        return results.to_dict(orient="records")

    def vector_search_all_tables(
        self,
        tables: Union[str, List[str]],
        embedding: List[float],
        limit=10,
    ) -> dict:
        results = {}
        for table_name in self.get_table_names(tables):
            results[table_name] = self.vector_search(table_name, embedding, limit)
        return results


if __name__ == "__main__":
    db_url = ".rag/experience"
    lance = LanceDB(db_url)

    # 测试用例1: 测试get_table_names方法
    print("测试get_table_names方法:")
    test_tables = lance.get_table_names(None)
    print(f"所有表名: {test_tables}")

    # 测试用例2: 测试append_data方法
    print("\n测试append_data方法:")
    test_data = [
        {"vector": [1.1, 1.2], "text": "测试数据1"},
        {"vector": [0.5, 0.8], "text": "测试数据2"},
    ]
    lance.append_data("test_table", test_data)

    # 测试用例3: 测试vector_search方法
    print("\n测试vector_search方法:")
    test_embedding = [1.0, 1.0]
    search_results = lance.vector_search("test_table", test_embedding)
    print(f"搜索结果: {search_results}")

    # 测试用例4: 测试vector_search_all_tables方法
    print("\n测试vector_search_all_tables方法:")
    all_results = lance.vector_search_all_tables("test_table", test_embedding)
    print(f"所有表搜索结果: {all_results}")
