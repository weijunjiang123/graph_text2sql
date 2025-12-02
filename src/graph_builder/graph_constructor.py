"""
图谱构建器 - 将解析后的 Schema 构建为知识图谱
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from src.database import Neo4jConnector
from src.graph_builder.schema_parser import SchemaParser


class GraphConstructor:
    """
    图谱构建器

    负责将解析后的 Schema 信息构建为 Neo4j 知识图谱
    """

    # 节点标签
    LABEL_TABLE = "Table"
    LABEL_COLUMN = "Column"
    LABEL_CONCEPT = "Concept"
    LABEL_VALUE = "Value"

    # 关系类型
    REL_HAS_COLUMN = "HAS_COLUMN"
    REL_FOREIGN_KEY = "FOREIGN_KEY"
    REL_RELATED_TO = "RELATED_TO"
    REL_MEANS = "MEANS"
    REL_SYNONYM_OF = "SYNONYM_OF"
    REL_HAS_VALUE = "HAS_VALUE"

    def __init__(self, neo4j_connector: Neo4jConnector):
        """
        初始化图谱构建器

        Args:
            neo4j_connector: Neo4j 连接器
        """
        self.neo4j = neo4j_connector

    def build_schema_graph(self, schema: Dict[str, Any], clear_existing: bool = False):
        """
        构建 Schema 知识图谱

        Args:
            schema: 解析后的 Schema 信息
            clear_existing: 是否清除现有图谱
        """
        logger.info("开始构建知识图谱...")

        if clear_existing:
            logger.warning("清除现有图谱...")
            self.neo4j.clear_database()

        # 创建约束和索引
        self._create_constraints_and_indexes()

        # 创建表节点
        for table in schema["tables"]:
            self._create_table_node(table)

        # 创建列节点和关系
        for table in schema["tables"]:
            self._create_column_nodes(table)

        # 创建表间关系
        for relationship in schema["relationships"]:
            self._create_table_relationship(relationship)

        # 创建值节点（可选）
        for table in schema["tables"]:
            self._create_value_nodes(table)

        logger.info("知识图谱构建完成")

    def _create_constraints_and_indexes(self):
        """创建约束和索引以提高查询性能"""
        logger.info("创建约束和索引...")

        constraints = [
            # 表名唯一约束
            f"CREATE CONSTRAINT table_name_unique IF NOT EXISTS "
            f"FOR (t:{self.LABEL_TABLE}) REQUIRE t.name IS UNIQUE",
            # 列的复合约束（表名+列名）
            f"CREATE CONSTRAINT column_unique IF NOT EXISTS "
            f"FOR (c:{self.LABEL_COLUMN}) REQUIRE (c.table_name, c.name) IS UNIQUE",
        ]

        for constraint in constraints:
            try:
                self.neo4j.execute_write(constraint)
                logger.debug(f"创建约束: {constraint[:50]}...")
            except Exception as e:
                logger.debug(f"约束已存在或创建失败: {e}")

        # 创建索引
        indexes = [
            f"CREATE INDEX table_comment_idx IF NOT EXISTS FOR (t:{self.LABEL_TABLE}) ON (t.comment)",
            f"CREATE INDEX column_name_idx IF NOT EXISTS FOR (c:{self.LABEL_COLUMN}) ON (c.name)",
            f"CREATE INDEX column_type_idx IF NOT EXISTS FOR (c:{self.LABEL_COLUMN}) ON (c.type)",
        ]

        for index in indexes:
            try:
                self.neo4j.execute_write(index)
                logger.debug(f"创建索引: {index[:50]}...")
            except Exception as e:
                logger.debug(f"索引已存在或创建失败: {e}")

    def _create_table_node(self, table: Dict[str, Any]):
        """
        创建表节点

        Args:
            table: 表信息
        """
        query = f"""
        MERGE (t:{self.LABEL_TABLE} {{name: $name}})
        SET t.comment = $comment,
            t.row_count = $row_count,
            t.has_data = $has_data,
            t.primary_keys = $primary_keys,
            t.created_at = datetime()
        RETURN t
        """

        params = {
            "name": table["name"],
            "comment": table.get("comment", ""),
            "row_count": table["metadata"]["row_count"],
            "has_data": table["metadata"]["has_data"],
            "primary_keys": table.get("primary_keys", []),
        }

        self.neo4j.execute_write(query, params)
        logger.debug(f"创建表节点: {table['name']}")

    def _create_column_nodes(self, table: Dict[str, Any]):
        """
        创建列节点并建立与表的关系

        Args:
            table: 表信息
        """
        table_name = table["name"]

        for column in table["columns"]:
            # 创建列节点
            query = f"""
            MATCH (t:{self.LABEL_TABLE} {{name: $table_name}})
            MERGE (c:{self.LABEL_COLUMN} {{table_name: $table_name, name: $col_name}})
            SET c.type = $col_type,
                c.nullable = $nullable,
                c.primary_key = $primary_key,
                c.comment = $comment,
                c.default_value = $default_value,
                c.has_samples = $has_samples
            MERGE (t)-[:{self.REL_HAS_COLUMN}]->(c)
            RETURN c
            """

            params = {
                "table_name": table_name,
                "col_name": column["name"],
                "col_type": column["type"],
                "nullable": column["nullable"],
                "primary_key": column["primary_key"],
                "comment": column.get("comment", ""),
                "default_value": str(column.get("default", "")),
                "has_samples": column["metadata"]["has_samples"],
            }

            self.neo4j.execute_write(query, params)

        logger.debug(f"创建表 {table_name} 的 {len(table['columns'])} 个列节点")

    def _create_table_relationship(self, relationship: Dict[str, Any]):
        """
        创建表之间的关系

        Args:
            relationship: 关系信息
        """
        query = f"""
        MATCH (from_table:{self.LABEL_TABLE} {{name: $from_table}})
        MATCH (to_table:{self.LABEL_TABLE} {{name: $to_table}})
        MERGE (from_table)-[r:{self.REL_FOREIGN_KEY}]->(to_table)
        SET r.from_columns = $from_columns,
            r.to_columns = $to_columns,
            r.constraint_name = $constraint_name
        RETURN r
        """

        params = {
            "from_table": relationship["from_table"],
            "to_table": relationship["to_table"],
            "from_columns": relationship["from_columns"],
            "to_columns": relationship["to_columns"],
            "constraint_name": relationship.get("name", ""),
        }

        self.neo4j.execute_write(query, params)
        logger.debug(
            f"创建关系: {relationship['from_table']} -> {relationship['to_table']}"
        )

    def _create_value_nodes(self, table: Dict[str, Any]):
        """
        创建高频值节点（用于解决拼写问题）

        Args:
            table: 表信息
        """
        table_name = table["name"]

        for column in table["columns"]:
            if not column["metadata"]["has_samples"]:
                continue

            sample_values = column["metadata"]["sample_values"]

            # 只为非数值型且唯一值不超过 20 个的列创建值节点
            if len(sample_values) > 20:
                continue

            for value in sample_values:
                if value is None:
                    continue

                # 转换为字符串
                value_str = str(value)

                # 创建值节点
                query = f"""
                MATCH (c:{self.LABEL_COLUMN} {{table_name: $table_name, name: $col_name}})
                MERGE (v:{self.LABEL_VALUE} {{value: $value, column_path: $column_path}})
                SET v.table_name = $table_name,
                    v.column_name = $col_name
                MERGE (c)-[:{self.REL_HAS_VALUE}]->(v)
                RETURN v
                """

                params = {
                    "table_name": table_name,
                    "col_name": column["name"],
                    "value": value_str,
                    "column_path": f"{table_name}.{column['name']}",
                }

                try:
                    self.neo4j.execute_write(query, params)
                except Exception as e:
                    logger.debug(f"创建值节点失败: {e}")

        logger.debug(f"为表 {table_name} 创建值节点")

    def add_business_concept(
        self,
        concept_name: str,
        description: str,
        related_columns: List[Dict[str, str]],
        synonyms: Optional[List[str]] = None,
    ):
        """
        添加业务概念节点

        Args:
            concept_name: 概念名称（如"高价值客户"）
            description: 概念描述
            related_columns: 相关列列表 [{'table': 'users', 'column': 'vip_level'}, ...]
            synonyms: 同义词列表
        """
        # 创建概念节点
        query = f"""
        MERGE (concept:{self.LABEL_CONCEPT} {{name: $name}})
        SET concept.description = $description,
            concept.created_at = datetime()
        RETURN concept
        """

        params = {"name": concept_name, "description": description}

        self.neo4j.execute_write(query, params)

        # 关联到列
        for col_info in related_columns:
            link_query = f"""
            MATCH (concept:{self.LABEL_CONCEPT} {{name: $concept_name}})
            WITH concept
            MATCH (c:{self.LABEL_COLUMN} {{table_name: $table_name, name: $col_name}})
            MERGE (concept)-[:{self.REL_MEANS}]->(c)
            """

            link_params = {
                "concept_name": concept_name,
                "table_name": col_info["table"],
                "col_name": col_info["column"],
            }

            self.neo4j.execute_write(link_query, link_params)

        # 添加同义词
        if synonyms:
            for synonym in synonyms:
                syn_query = f"""
                MERGE (syn:{self.LABEL_CONCEPT} {{name: $synonym}})
                WITH syn
                MATCH (concept:{self.LABEL_CONCEPT} {{name: $concept_name}})
                MERGE (syn)-[:{self.REL_SYNONYM_OF}]->(concept)
                """

                syn_params = {"synonym": synonym, "concept_name": concept_name}

                self.neo4j.execute_write(syn_query, syn_params)

        logger.info(f"添加业务概念: {concept_name}")

    def get_graph_statistics(self) -> Dict[str, int]:
        """
        获取图谱统计信息

        Returns:
            统计信息字典
        """
        stats = {}

        # 节点统计
        node_count_query = f"""
        MATCH (n:{self.LABEL_TABLE})
        RETURN count(n) as table_count
        """
        result = self.neo4j.execute_query(node_count_query)
        stats["table_count"] = result[0]["table_count"] if result else 0

        column_count_query = f"""
        MATCH (n:{self.LABEL_COLUMN})
        RETURN count(n) as column_count
        """
        result = self.neo4j.execute_query(column_count_query)
        stats["column_count"] = result[0]["column_count"] if result else 0

        concept_count_query = f"""
        MATCH (n:{self.LABEL_CONCEPT})
        RETURN count(n) as concept_count
        """
        result = self.neo4j.execute_query(concept_count_query)
        stats["concept_count"] = result[0]["concept_count"] if result else 0

        # 关系统计
        rel_count_query = f"""
        MATCH ()-[r:{self.REL_FOREIGN_KEY}]->()
        RETURN count(r) as fk_count
        """
        result = self.neo4j.execute_query(rel_count_query)
        stats["foreign_key_count"] = result[0]["fk_count"] if result else 0

        return stats
