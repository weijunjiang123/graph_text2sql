"""
数据库连接和操作模块
"""

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import (
    MetaData,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from src.config import SourceDatabaseConfig


class DatabaseConnector:
    """数据库连接器"""

    def __init__(self, config: SourceDatabaseConfig):
        """
        初始化数据库连接

        Args:
            config: 数据库配置
        """
        self.config = config
        self.engine: Optional[Engine] = None
        self.metadata: Optional[MetaData] = None
        self._connect()

    def _connect(self):
        """建立数据库连接"""
        try:
            connection_string = self.config.get_connection_string()

            self.engine = create_engine(
                connection_string,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_pre_ping=True,  # 连接前检测
                echo=False,
            )

            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info(f"成功连接到数据库: {self.config.database}")

        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def get_all_tables(self) -> List[str]:
        """
        获取所有表名

        Returns:
            表名列表
        """
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        logger.info(f"发现 {len(tables)} 张表")
        return tables

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        获取表的详细结构信息

        Args:
            table_name: 表名

        Returns:
            表结构信息字典
        """
        inspector = inspect(self.engine)

        # 基本信息
        schema_info = {
            "name": table_name,
            "comment": "",
            "columns": [],
            "primary_keys": [],
            "foreign_keys": [],
            "indexes": [],
        }

        # 获取表注释（不同数据库实现不同）
        try:
            table_comment = inspector.get_table_comment(table_name)
            schema_info["comment"] = table_comment.get("text", "")
        except:
            pass

        # 获取列信息
        columns = inspector.get_columns(table_name)
        for col in columns:
            col_info = {
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col["nullable"],
                "default": col.get("default"),
                "comment": col.get("comment", ""),
                "primary_key": False,
            }
            schema_info["columns"].append(col_info)

        # 获取主键
        pk_constraint = inspector.get_pk_constraint(table_name)
        if pk_constraint:
            schema_info["primary_keys"] = pk_constraint["constrained_columns"]
            # 标记主键列
            for col in schema_info["columns"]:
                if col["name"] in schema_info["primary_keys"]:
                    col["primary_key"] = True

        # 获取外键
        foreign_keys = inspector.get_foreign_keys(table_name)
        for fk in foreign_keys:
            fk_info = {
                "name": fk.get("name"),
                "constrained_columns": fk["constrained_columns"],
                "referred_table": fk["referred_table"],
                "referred_columns": fk["referred_columns"],
            }
            schema_info["foreign_keys"].append(fk_info)

        # 获取索引
        indexes = inspector.get_indexes(table_name)
        for idx in indexes:
            idx_info = {
                "name": idx["name"],
                "columns": idx["column_names"],
                "unique": idx["unique"],
            }
            schema_info["indexes"].append(idx_info)

        return schema_info

    def get_database_schema(self) -> Dict[str, Any]:
        """
        获取整个数据库的 Schema 信息

        Returns:
            数据库 Schema 信息
        """
        logger.info("开始提取数据库 Schema...")

        tables = self.get_all_tables()
        schema_info = {
            "database": self.config.database,
            "type": self.config.type,
            "tables": [],
        }

        for table_name in tables:
            try:
                table_schema = self.get_table_schema(table_name)
                schema_info["tables"].append(table_schema)
                logger.debug(f"已提取表结构: {table_name}")
            except Exception as e:
                logger.warning(f"提取表 {table_name} 结构失败: {e}")

        logger.info(f"Schema 提取完成，共 {len(schema_info['tables'])} 张表")
        return schema_info

    def get_sample_values(
        self, table_name: str, column_name: str, limit: int = 10
    ) -> List[Any]:
        """
        获取列的示例值

        Args:
            table_name: 表名
            column_name: 列名
            limit: 返回数量限制

        Returns:
            示例值列表
        """
        try:
            query = text(
                f"SELECT DISTINCT {column_name} FROM {table_name} "
                f"WHERE {column_name} IS NOT NULL LIMIT :limit"
            )

            with self.engine.connect() as conn:
                result = conn.execute(query, {"limit": limit})
                values = [row[0] for row in result]

            return values

        except Exception as e:
            logger.warning(f"获取示例值失败 {table_name}.{column_name}: {e}")
            return []

    def execute_query(
        self, sql: str, params: Optional[Dict] = None, fetch_size: Optional[int] = None
    ) -> Tuple[List[Dict], List[str]]:
        """
        执行 SQL 查询

        Args:
            sql: SQL 语句
            params: 查询参数
            fetch_size: 返回结果数量限制

        Returns:
            (结果列表, 列名列表)
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), params or {})

                # 获取列名
                columns = list(result.keys())

                # 获取结果
                if fetch_size:
                    rows = result.fetchmany(fetch_size)
                else:
                    rows = result.fetchall()

                # 转换为字典列表
                data = [dict(zip(columns, row)) for row in rows]

                return data, columns

        except SQLAlchemyError as e:
            logger.error(f"SQL 执行失败: {e}")
            raise

    def test_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        测试 SQL 是否可执行（不实际执行，只验证语法）

        Args:
            sql: SQL 语句

        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 使用 EXPLAIN 验证语法
            explain_sql = f"EXPLAIN {sql}"

            with self.engine.connect() as conn:
                conn.execute(text(explain_sql))

            return True, None

        except Exception as e:
            return False, str(e)

    def get_table_row_count(self, table_name: str) -> int:
        """
        获取表的行数

        Args:
            table_name: 表名

        Returns:
            行数
        """
        try:
            query = text(f"SELECT COUNT(*) FROM {table_name}")

            with self.engine.connect() as conn:
                result = conn.execute(query)
                count = result.scalar()

            return count

        except Exception as e:
            logger.warning(f"获取表行数失败 {table_name}: {e}")
            return 0

    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            logger.info("数据库连接已关闭")


class Neo4jConnector:
    """Neo4j 图数据库连接器"""

    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """
        初始化 Neo4j 连接

        Args:
            uri: Neo4j URI
            username: 用户名
            password: 密码
            database: 数据库名
        """
        try:
            from neo4j import GraphDatabase

            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            self.database = database

            # 测试连接
            with self.driver.session(database=database) as session:
                session.run("RETURN 1")

            logger.info(f"成功连接到 Neo4j: {uri}")

        except Exception as e:
            logger.error(f"Neo4j 连接失败: {e}")
            raise

    def execute_query(
        self, query: str, parameters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        执行 Cypher 查询

        Args:
            query: Cypher 查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]

        except Exception as e:
            logger.error(f"Cypher 查询失败: {e}")
            raise

    def execute_write(self, query: str, parameters: Optional[Dict] = None) -> Dict:
        """
        执行写入操作

        Args:
            query: Cypher 写入语句
            parameters: 查询参数

        Returns:
            操作结果
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                summary = result.consume()

                return {
                    "nodes_created": summary.counters.nodes_created,
                    "relationships_created": summary.counters.relationships_created,
                    "properties_set": summary.counters.properties_set,
                }

        except Exception as e:
            logger.error(f"Cypher 写入失败: {e}")
            raise

    def clear_database(self):
        """清空数据库（谨慎使用）"""
        logger.warning("正在清空 Neo4j 数据库...")
        query = "MATCH (n) DETACH DELETE n"
        self.execute_write(query)
        logger.info("Neo4j 数据库已清空")

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j 连接已关闭")
