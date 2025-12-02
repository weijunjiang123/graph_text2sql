"""
主入口 - 基于知识图谱增强的 Text-to-SQL 系统
"""

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from src.config import Config, get_config
from src.database import DatabaseConnector, Neo4jConnector
from src.entity_linking import EntityMatcher, KeywordExtractor
from src.graph_builder import ConceptExtractor, GraphConstructor, SchemaParser
from src.graph_query import SchemaPruner, SubgraphRetriever
from src.llm_integration import PromptBuilder, SQLGenerator
from src.utils import SimpleCache, setup_logger


class GraphEnhancedText2SQL:
    """
    基于知识图谱增强的 Text-to-SQL 系统

    这是系统的主入口类，协调各个模块完成从自然语言到 SQL 的转换。

    工作流程：
    1. 用户提问 → 关键词提取 → 实体链接
    2. 实体匹配 → 图谱检索 → Schema 剪枝
    3. Prompt 构建 → LLM 生成 → SQL 返回
    """

    def __init__(self, config: Optional[Config] = None, auto_build_graph: bool = False):
        """
        初始化系统

        Args:
            config: 配置对象，如果不提供则使用默认配置
            auto_build_graph: 是否自动构建知识图谱
        """
        self.config = config or get_config()

        # 设置日志
        setup_logger(self.config)
        logger.info("初始化 Graph-Enhanced Text2SQL 系统...")

        # 初始化连接器
        self.db_connector = None
        self.neo4j_connector = None

        # 初始化各模块
        self.keyword_extractor = None
        self.entity_matcher = None
        self.concept_extractor = None
        self.subgraph_retriever = None
        self.schema_pruner = None
        self.prompt_builder = None
        self.sql_generator = None

        # 缓存
        self.cache = (
            SimpleCache(
                max_size=self.config.performance.cache.max_size,
                ttl=self.config.performance.cache.ttl,
            )
            if self.config.performance.cache.enabled
            else None
        )

        # 初始化组件
        self._initialize_components()

        # 自动构建图谱
        if auto_build_graph:
            self.build_knowledge_graph()

        logger.info("系统初始化完成")

    def _initialize_components(self):
        """初始化各个组件"""
        try:
            # 数据库连接
            self.db_connector = DatabaseConnector(self.config.source_database)

            # Neo4j 连接
            self.neo4j_connector = Neo4jConnector(
                uri=self.config.neo4j.uri,
                username=self.config.neo4j.username,
                password=self.config.neo4j.password,
                database=self.config.neo4j.database,
            )

            # 实体链接
            self.keyword_extractor = KeywordExtractor(
                method=self.config.entity_linking.keyword_extraction.method,
                spacy_model=self.config.entity_linking.spacy_model,
            )

            # 概念提取器（可选）
            self.concept_extractor = None
            # 如果配置了概念文件，加载它
            # concept_file = self.config.business_concepts.get('concept_definitions')
            # if concept_file:
            #     self.concept_extractor = ConceptExtractor(concept_file)

            # 实体匹配器
            self.entity_matcher = EntityMatcher(
                neo4j_connector=self.neo4j_connector,
                keyword_extractor=self.keyword_extractor,
                concept_extractor=self.concept_extractor,
                fuzzy_threshold=self.config.entity_linking.matching.fuzzy_threshold,
            )

            # 子图检索
            self.subgraph_retriever = SubgraphRetriever(
                neo4j_connector=self.neo4j_connector,
                max_hop_distance=self.config.graph_query.pruning.max_hop_distance,
                max_tables=self.config.graph_query.pruning.max_tables,
            )

            # Schema 剪枝
            self.schema_pruner = SchemaPruner(
                include_comments=self.config.prompt.include_schema_comments,
                include_sample_values=self.config.prompt.include_sample_values,
                highlight_relevant_columns=True,
            )

            # Prompt 构建
            self.prompt_builder = PromptBuilder(
                system_message=self.config.prompt.system_message,
                few_shot_examples=PromptBuilder.create_default_examples()[
                    : self.config.prompt.few_shot_examples
                ],
                include_tips=True,
            )

            # SQL 生成
            self.sql_generator = SQLGenerator(
                config=self.config, prompt_builder=self.prompt_builder
            )

            logger.info("所有组件初始化成功")

        except Exception as e:
            logger.error(f"组件初始化失败: {e}")
            raise

    def build_knowledge_graph(self, clear_existing: bool = False):
        """
        构建知识图谱

        Args:
            clear_existing: 是否清除现有图谱
        """
        logger.info("开始构建知识图谱...")

        try:
            # 解析 Schema
            schema_parser = SchemaParser(self.db_connector)
            schema = schema_parser.parse_database_schema()

            # 构建图谱
            graph_constructor = GraphConstructor(self.neo4j_connector)
            graph_constructor.build_schema_graph(schema, clear_existing=clear_existing)

            # 获取统计信息
            stats = graph_constructor.get_graph_statistics()
            logger.info(f"知识图谱构建完成: {stats}")

            return stats

        except Exception as e:
            logger.error(f"知识图谱构建失败: {e}")
            raise

    def generate_sql(
        self, question: str, return_context: bool = False, use_cache: bool = True
    ) -> str:
        """
        生成 SQL 查询（简化接口）

        Args:
            question: 用户问题
            return_context: 是否返回上下文信息
            use_cache: 是否使用缓存

        Returns:
            SQL 查询字符串，或包含上下文的字典
        """
        result = self.process_question(question, use_cache=use_cache)

        if result["success"]:
            if return_context:
                return result
            else:
                return result["sql"]
        else:
            error_msg = result.get("error", "Unknown error")
            raise Exception(f"SQL 生成失败: {error_msg}")

    def process_question(self, question: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        处理用户问题（完整流程）

        Args:
            question: 用户问题
            use_cache: 是否使用缓存

        Returns:
            处理结果字典
        """
        logger.info(f"处理问题: {question}")

        # 检查缓存
        if use_cache and self.cache:
            from src.utils import hash_text

            cache_key = hash_text(question)
            cached_result = self.cache.get(cache_key)

            if cached_result:
                logger.info("从缓存返回结果")
                return cached_result

        result = {
            "question": question,
            "sql": None,
            "success": False,
            "error": None,
            "metadata": {},
        }

        try:
            # 1. 实体链接
            logger.debug("步骤 1: 实体链接")
            matched_entities = self.entity_matcher.match_entities(question)
            result["metadata"]["matched_entities"] = matched_entities

            # 2. 子图检索
            logger.debug("步骤 2: 子图检索")
            subgraph = self.subgraph_retriever.retrieve_subgraph(matched_entities)
            result["metadata"]["subgraph"] = {
                "table_count": len(subgraph["tables"]),
                "relationship_count": len(subgraph["relationships"]),
            }

            if not subgraph["tables"]:
                raise Exception("未找到相关表，无法生成 SQL")

            # 3. Schema 剪枝
            logger.debug("步骤 3: Schema 剪枝")
            pruned_schema = self.schema_pruner.prune_schema(subgraph)
            schema_context = self.schema_pruner.create_prompt_context(
                pruned_schema, question
            )

            # 4. SQL 生成
            logger.debug("步骤 4: SQL 生成")
            generation_result = self.sql_generator.generate_sql(
                schema_context=schema_context, user_question=question
            )

            if generation_result["success"]:
                result["sql"] = generation_result["sql"]
                result["success"] = True
                result["metadata"]["attempts"] = generation_result["attempts"]

                logger.info(f"SQL 生成成功: {result['sql']}")

                # 缓存结果
                if use_cache and self.cache:
                    from src.utils import hash_text

                    cache_key = hash_text(question)
                    self.cache.set(cache_key, result)
            else:
                result["error"] = generation_result["error"]
                logger.error(f"SQL 生成失败: {result['error']}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"处理问题时出错: {e}")

        return result

    def execute(
        self, question: str, fetch_size: Optional[int] = 100
    ) -> Tuple[List[Dict], List[str]]:
        """
        执行查询并返回结果

        Args:
            question: 用户问题
            fetch_size: 返回结果数量限制

        Returns:
            (结果列表, 列名列表)
        """
        # 生成 SQL
        sql = self.generate_sql(question)

        # 执行 SQL
        logger.info(f"执行 SQL: {sql}")
        results, columns = self.db_connector.execute_query(sql, fetch_size=fetch_size)

        logger.info(f"查询返回 {len(results)} 条结果")
        return results, columns

    def add_business_concept(
        self,
        name: str,
        description: str,
        related_columns: List[Dict[str, str]],
        synonyms: Optional[List[str]] = None,
    ):
        """
        添加业务概念

        Args:
            name: 概念名称
            description: 描述
            related_columns: 相关列 [{'table': 'users', 'column': 'vip_level'}]
            synonyms: 同义词
        """
        related_tables = list(set(col["table"] for col in related_columns))

        graph_constructor = GraphConstructor(self.neo4j_connector)
        graph_constructor.add_business_concept(
            concept_name=name,
            description=description,
            related_columns=related_columns,
            synonyms=synonyms,
        )

        logger.info(f"已添加业务概念: {name}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取系统统计信息

        Returns:
            统计信息字典
        """
        graph_constructor = GraphConstructor(self.neo4j_connector)
        graph_stats = graph_constructor.get_graph_statistics()

        stats = {
            "graph": graph_stats,
            "cache": {"size": self.cache.size() if self.cache else 0},
        }

        return stats

    def close(self):
        """关闭所有连接"""
        if self.db_connector:
            self.db_connector.close()

        if self.neo4j_connector:
            self.neo4j_connector.close()

        logger.info("所有连接已关闭")
