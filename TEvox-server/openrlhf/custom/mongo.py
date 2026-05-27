import pymongo


class MongoClient:
    def __init__(self, host="localhost", port=27017):
        self.mongo_client = pymongo.MongoClient(host=host, port=port)

    def get_client(self):
        return self.mongo_client

    def get_collection(
        self,
        collection_name: str,
        database_name: str = "evox",
    ):
        return self.mongo_client[database_name][collection_name]


MongoClientProxy = MongoClient()
