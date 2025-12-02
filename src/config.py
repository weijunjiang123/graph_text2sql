"""
配置管理模块
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class Neo4jConfig(BaseSettings):
    """Neo4j 配置"""

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"


class SourceDatabaseConfig(BaseSettings):
    """源数据库配置"""

    type: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    database: str = "business_db"
    username: str = "db_user"
    password: str = "db_password"
    pool_size: int = 5
    max_overflow: int = 10

    def get_connection_string(self) -> str:
        """生成数据库连接字符串"""
        if self.type == "postgresql":
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.type == "mysql":
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.type == "oracle":
            return f"oracle+cx_oracle://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.type}")


class LLMConfig(BaseSettings):
    """LLM 配置"""

    provider: str = "openai"

    class OpenAIConfig(BaseSettings):
        api_key: str = ""
        model: str = "gpt-4-turbo-preview"
        temperature: float = 0.0
        max_tokens: int = 2000
        base_url: Optional[str] = None

    class AnthropicConfig(BaseSettings):
        api_key: str = ""
        model: str = "claude-3-sonnet-20240229"
        temperature: float = 0.0
        max_tokens: int = 4000

    class OpenAICompatibleConfig(BaseSettings):
        api_key: str = "sk-dummy-key"
        base_url: str = "http://localhost:8000/v1"
        model: str = "llama-3-8b"
        temperature: float = 0.0
        max_tokens: int = 2000

    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    openai_compatible: OpenAICompatibleConfig = Field(default_factory=OpenAICompatibleConfig)


class EntityLinkingConfig(BaseSettings):
    """实体链接配置"""

    spacy_model: str = "zh_core_web_sm"

    class KeywordExtractionConfig(BaseSettings):
        method: str = "hybrid"
        min_keyword_length: int = 2
        max_keywords: int = 10

    class MatchingConfig(BaseSettings):
        fuzzy_threshold: float = 0.85
        enable_synonym_matching: bool = True

    keyword_extraction: KeywordExtractionConfig = Field(
        default_factory=KeywordExtractionConfig
    )
    matching: MatchingConfig = Field(default_factory=MatchingConfig)


class GraphQueryConfig(BaseSettings):
    """图查询配置"""

    class PruningConfig(BaseSettings):
        max_tables: int = 10
        max_hop_distance: int = 2
        include_related_concepts: bool = True

    class RetrievalConfig(BaseSettings):
        strategy: str = "path_based"
        min_relevance_score: float = 0.6

    pruning: PruningConfig = Field(default_factory=PruningConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)


class PromptConfig(BaseSettings):
    """Prompt 配置"""

    few_shot_examples: int = 3
    system_message: str = """You are a SQL expert. Generate accurate SQL queries based on the provided schema and user question.
Always follow these rules:
1. Use standard SQL syntax
2. Include table aliases for clarity
3. Add appropriate WHERE clauses
4. Consider NULL handling"""
    include_schema_comments: bool = True
    include_sample_values: bool = False


class PerformanceConfig(BaseSettings):
    """性能配置"""

    class CacheConfig(BaseSettings):
        enabled: bool = True
        ttl: int = 3600
        max_size: int = 1000

    class TimeoutConfig(BaseSettings):
        graph_query: int = 5
        llm_generation: int = 30
        sql_execution: int = 60

    cache: CacheConfig = Field(default_factory=CacheConfig)
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)


class LoggingConfig(BaseSettings):
    """日志配置"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "logs/text2sql.log"
    max_bytes: int = 10485760
    backup_count: int = 5


class BusinessConceptsConfig(BaseSettings):
    """业务概念配置"""

    concept_definitions: str = "data/concepts.yaml"
    synonym_dict: str = "data/synonyms.yaml"

    class AutoExtractionConfig(BaseSettings):
        enabled: bool = False
        doc_path: str = "docs/business/"

    auto_extraction: AutoExtractionConfig = Field(default_factory=AutoExtractionConfig)


class DevelopmentConfig(BaseSettings):
    """开发模式配置"""

    debug: bool = False
    verbose_logging: bool = False
    save_intermediate_results: bool = True
    output_dir: str = "debug_output/"


class Config(BaseSettings):
    """主配置类"""

    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    source_database: SourceDatabaseConfig = Field(default_factory=SourceDatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    entity_linking: EntityLinkingConfig = Field(default_factory=EntityLinkingConfig)
    graph_query: GraphQueryConfig = Field(default_factory=GraphQueryConfig)
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    business_concepts: BusinessConceptsConfig = Field(default_factory=BusinessConceptsConfig)
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig)

    @classmethod
    def from_yaml(cls, config_path: str = "config.yaml") -> "Config":
        """从 YAML 文件加载配置"""
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_file, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        return cls()


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取配置实例（单例模式）"""
    global _config

    if _config is None:
        # 尝试从配置文件加载
        if os.path.exists("config.yaml"):
            _config = Config.from_yaml("config.yaml")
        else:
            # 使用默认配置
            _config = Config()

    return _config


def set_config(config: Config):
    """设置配置实例"""
    global _config
    _config = config
