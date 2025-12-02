"""
Schema 解析器 - 将数据库 Schema 解析为图谱友好的结构
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from src.database import DatabaseConnector


class SchemaParser:
    """
    Schema 解析器

    负责从关系型数据库中提取结构信息，并转换为适合构建知识图谱的格式
    """

    def __init__(self, db_connector: DatabaseConnector):
        """
        初始化 Schema 解析器

        Args:
            db_connector: 数据库连接器
        """
        self.db = db_connector

    def parse_database_schema(self) -> Dict[str, Any]:
        """
        解析完整的数据库 Schema

        Returns:
            解析后的 Schema 信息
        """
        logger.info("开始解析数据库 Schema...")

        schema = self.db.get_database_schema()

        # 增强 Schema 信息
        enhanced_schema = {
            "database": schema["database"],
            "type": schema["type"],
            "tables": [],
            "relationships": [],  # 表之间的关系
        }

        # 处理每张表
        for table in schema["tables"]:
            enhanced_table = self._enhance_table_info(table)
            enhanced_schema["tables"].append(enhanced_table)

        # 提取表之间的关系
        relationships = self._extract_relationships(schema["tables"])
        enhanced_schema["relationships"] = relationships

        logger.info(
            f"Schema 解析完成: {len(enhanced_schema['tables'])} 张表, "
            f"{len(enhanced_schema['relationships'])} 个关系"
        )

        return enhanced_schema

    def _enhance_table_info(self, table: Dict[str, Any]) -> Dict[str, Any]:
        """
        增强表信息

        Args:
            table: 原始表信息

        Returns:
            增强后的表信息
        """
        enhanced = {
            "name": table["name"],
            "comment": table.get("comment", ""),
            "columns": [],
            "primary_keys": table.get("primary_keys", []),
            "foreign_keys": table.get("foreign_keys", []),
            "indexes": table.get("indexes", []),
            "metadata": {"row_count": 0, "has_data": False},
        }

        # 增强列信息
        for col in table["columns"]:
            enhanced_col = self._enhance_column_info(table["name"], col)
            enhanced["columns"].append(enhanced_col)

        # 获取表的行数（可选，用于了解数据量）
        try:
            row_count = self.db.get_table_row_count(table["name"])
            enhanced["metadata"]["row_count"] = row_count
            enhanced["metadata"]["has_data"] = row_count > 0
        except Exception as e:
            logger.debug(f"无法获取表 {table['name']} 的行数: {e}")

        return enhanced

    def _enhance_column_info(
        self, table_name: str, column: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        增强列信息

        Args:
            table_name: 表名
            column: 原始列信息

        Returns:
            增强后的列信息
        """
        enhanced = {
            "name": column["name"],
            "type": column["type"],
            "nullable": column.get("nullable", True),
            "primary_key": column.get("primary_key", False),
            "default": column.get("default"),
            "comment": column.get("comment", ""),
            "metadata": {"sample_values": [], "has_samples": False, "value_count": 0},
        }

        # 提取示例值（用于构建 Value 节点）
        # 只对某些类型的列提取示例值
        if self._should_extract_samples(column):
            try:
                samples = self.db.get_sample_values(
                    table_name, column["name"], limit=10
                )
                enhanced["metadata"]["sample_values"] = samples
                enhanced["metadata"]["has_samples"] = len(samples) > 0
                enhanced["metadata"]["value_count"] = len(samples)
            except Exception as e:
                logger.debug(f"无法获取列 {table_name}.{column['name']} 的示例值: {e}")

        return enhanced

    def _should_extract_samples(self, column: Dict[str, Any]) -> bool:
        """
        判断是否应该提取列的示例值

        Args:
            column: 列信息

        Returns:
            是否提取示例值
        """
        col_type = str(column["type"]).upper()

        # 对于枚举类型、短字符串、外键等提取示例值
        extract_types = [
            "VARCHAR",
            "CHAR",
            "TEXT",
            "ENUM",
            "INT",
            "INTEGER",
            "SMALLINT",
        ]

        # 检查类型
        for extract_type in extract_types:
            if extract_type in col_type:
                # 对于字符串类型，只提取较短的
                if "VARCHAR" in col_type or "CHAR" in col_type:
                    # 提取 VARCHAR(50) 以下的
                    import re

                    match = re.search(r"\((\d+)\)", col_type)
                    if match:
                        length = int(match.group(1))
                        if length > 100:
                            return False
                return True

        return False

    def _extract_relationships(
        self, tables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        从表结构中提取表之间的关系

        Args:
            tables: 表列表

        Returns:
            关系列表
        """
        relationships = []

        for table in tables:
            table_name = table["name"]

            # 从外键提取关系
            for fk in table.get("foreign_keys", []):
                relationship = {
                    "type": "FOREIGN_KEY",
                    "from_table": table_name,
                    "from_columns": fk["constrained_columns"],
                    "to_table": fk["referred_table"],
                    "to_columns": fk["referred_columns"],
                    "name": fk.get("name", f"fk_{table_name}_{fk['referred_table']}"),
                }
                relationships.append(relationship)

        logger.info(f"提取到 {len(relationships)} 个表关系")
        return relationships

    def get_table_dependencies(self, table_name: str) -> Dict[str, List[str]]:
        """
        获取表的依赖关系

        Args:
            table_name: 表名

        Returns:
            依赖关系字典 {'depends_on': [...], 'depended_by': [...]}
        """
        schema = self.parse_database_schema()

        dependencies = {
            "depends_on": [],  # 该表依赖的表（外键指向的表）
            "depended_by": [],  # 依赖该表的表（外键来自的表）
        }

        for rel in schema["relationships"]:
            if rel["from_table"] == table_name:
                dependencies["depends_on"].append(rel["to_table"])
            elif rel["to_table"] == table_name:
                dependencies["depended_by"].append(rel["from_table"])

        return dependencies

    def find_related_tables(self, table_name: str, max_depth: int = 2) -> List[str]:
        """
        查找与指定表相关的所有表（通过外键关系）

        Args:
            table_name: 表名
            max_depth: 最大搜索深度

        Returns:
            相关表列表
        """
        schema = self.parse_database_schema()

        # 构建邻接表
        adjacency = {}
        for rel in schema["relationships"]:
            from_table = rel["from_table"]
            to_table = rel["to_table"]

            if from_table not in adjacency:
                adjacency[from_table] = set()
            if to_table not in adjacency:
                adjacency[to_table] = set()

            adjacency[from_table].add(to_table)
            adjacency[to_table].add(from_table)  # 双向关系

        # BFS 搜索相关表
        visited = set()
        queue = [(table_name, 0)]  # (table, depth)
        related = []

        while queue:
            current_table, depth = queue.pop(0)

            if current_table in visited or depth > max_depth:
                continue

            visited.add(current_table)

            if current_table != table_name:
                related.append(current_table)

            # 添加邻接表
            if current_table in adjacency:
                for neighbor in adjacency[current_table]:
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))

        return related

    def extract_table_aliases(self, table: Dict[str, Any]) -> List[str]:
        """
        提取表的别名（从注释或命名中推断）

        Args:
            table: 表信息

        Returns:
            别名列表
        """
        aliases = []

        # 从表名提取
        table_name = table["name"]

        # 移除常见前缀/后缀
        prefixes = ["tbl_", "t_", "tb_"]
        suffixes = ["_table", "_tbl", "_t"]

        clean_name = table_name.lower()
        for prefix in prefixes:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix) :]
                break

        for suffix in suffixes:
            if clean_name.endswith(suffix):
                clean_name = clean_name[: -len(suffix)]
                break

        if clean_name != table_name.lower():
            aliases.append(clean_name)

        # 从注释提取（假设注释中包含中文名称）
        comment = table.get("comment", "")
        if comment:
            # 简单提取：假设注释就是别名
            aliases.append(comment.strip())

        return list(set(aliases))  # 去重
