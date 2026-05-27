import yaml
import os


class ConfigParser:

    def __init__(self, config_file: str):
        with open(config_file, "r", encoding="utf-8") as file:
            self.config = yaml.safe_load(file)

    def get(self, *keys, default=None):
        value = self.config
        for key in keys:
            if value and key in value:
                value = value[key]
            else:
                return default
        return value


class Config:

    def __init__(
        self,
        config_file: str = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../default.yaml")
        ),
    ):
        self.config = ConfigParser(config_file)
        os.environ["OPENAI_API_BASE"] = self.config.get("OPENAI_API_BASE")
        os.environ["OPENAI_API_KEY"] = self.config.get("OPENAI_API_KEY")
        self.openai_llm_chat_model = self.config.get("OPENAI_LLM_CHAT_MODEL")
        self.openai_llm_reasoning_model = self.config.get("OPENAI_LLM_REASONING_MODEL")
        self.rag_api_base = self.config.get("RAG_API_BASE")
        self.rag_api_key = self.config.get("RAG_API_KEY")
        self.rag_model = self.config.get("RAG_MODEL")
        self.embedding_api_base = self.config.get("EMBEDDING_API_BASE")
        self.embedding_api_key = self.config.get("EMBEDDING_API_KEY")
        self.embedding_model = self.config.get("EMBEDDING_MODEL")
        self.vscode_api_base = self.config.get("VSCODE_API_BASE")
        self.agent_api_base = self.config.get("AGENT_API_BASE")
        self.agent_api_key = self.config.get("AGENT_API_KEY")
        self.agent_model = self.config.get("AGENT_MODEL")
        self.evaluator_model = self.config.get("EVALUATOR_MODEL")
        self.code_api_base = self.config.get("CODE_API_BASE")
        self.code_api_key = self.config.get("CODE_API_KEY")
        self.code_model = self.config.get("CODE_MODEL")
        self.search_api_base = self.config.get("SEARCH_API_BASE")
        self.search_api_key = self.config.get("SEARCH_API_KEY")
        self.search_model = self.config.get("SEARCH_MODEL")
        self.dashscope_api_base = self.config.get("DASHSCOPE_API_BASE")
        self.dashscope_api_key = self.config.get("DASHSCOPE_API_KEY")


DefaultConfig = Config()
