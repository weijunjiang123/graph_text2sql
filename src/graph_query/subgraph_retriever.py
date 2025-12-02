"""
子图检索器 - 从知识图谱中检索相关子图
"""

from typing import Any, Dict, List, Set

from loguru import logger

from src.database import Neo4jConnector


class SubgraphRetriever:
    """
    子图检索器

    根据实体匹配结果，从知识图谱中检索相关的表、列和关系，
    形成一个精简的子图，用于后续的 Schema 剪枝。
    """

    def __init__(
        self,
        neo4j_connector: Neo4jConnector,
        max_hop_distance: int = 2,
        max_tables: int = 10,
    ):
        """
        初始化子图检索器

        Args:
            neo4j_connector: Neo4j 连接器
            max_hop_distance: 图遍历的最大跳数
            max_tables: 返回的最大表数量
        """
        self.neo4j = neo4j_connector
        self.max_hop_distance = max_hop_distance
        self.max_tables = max_tables

    def retrieve_subgraph(
        self, matched_entities: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        检索相关子图

        Args:
            matched_entities: 实体匹配结果

        Returns:
            子图信息，包含表、列、关系等
        """
        logger.info("开始检索相关子图...")

        # 1. 获取直接匹配的表
        entry_tables = self._get_entry_tables(matched_entities)
        logger.debug(f"入口表: {entry_tables}")

        if not entry_tables:
            logger.warning("未找到入口表，尝试从列推断...")
            entry_tables = self._infer_tables_from_columns(matched_entities)

        if not entry_tables:
            logger.warning("无法确定相关表")
            return self._empty_subgraph()

        # 2. 通过图遍历找到相关表
        related_tables = self._find_related_tables(
            entry_tables, max_distance=self.max_hop_distance
        )

        # 限制表数量
        all_tables = list(set(entry_tables + related_tables))[: self.max_tables]
        logger.info(f"检索到 {len(all_tables)} 张相关表")

        # 3. 获取表的详细信息
        subgraph = self._build_subgraph(all_tables, matched_entities)

        return subgraph

    def _get_entry_tables(
        self, matched_entities: Dict[str, List[Dict[str, Any]]]
    ) -> List[str]:
        """
        获取入口表（直接匹配的表）

        Args:
            matched_entities: 实体匹配结果

        Returns:
            表名列表
        """
        tables = []

        # 从表匹配中获取
        for table_match in matched_entities.get("tables", []):
            tables.append(table_match["name"])

        # 从概念匹配中获取
        for concept_match in matched_entities.get("concepts", []):
            concept = concept_match.get("concept", {})
            tables.extend(concept.get("related_tables", []))

        return list(set(tables))  # 去重

    def _infer_tables_from_columns(
        self, matched_entities: Dict[str, List[Dict[str, Any]]]
    ) -> List[str]:
        """
        从匹配的列推断表

        Args:
            matched_entities: 实体匹配结果

        Returns:
            表名列表
        """
        tables = []

        # 从列匹配中获取
        for col_match in matched_entities.get("columns", []):
            tables.append(col_match["table_name"])

        # 从值匹配中获取
        for value_match in matched_entities.get("values", []):
            if value_match.get("table_name"):
                tables.append(value_match["table_name"])

        return list(set(tables))  # 去重

    def _find_related_tables(
        self, entry_tables: List[str], max_distance: int = 2
    ) -> List[str]:
        """
        通过外键关系找到相关表

        Args:
            entry_tables: 入口表列表
            max_distance: 最大跳数

        Returns:
            相关表列表
        """
        if not entry_tables:
            return []

        # 使用 Cypher 查询在图中查找相关表
        query = f"""
        MATCH path = (start:Table)-[:FOREIGN_KEY*1..{max_distance}]-(related:Table)
        WHERE start.name IN $entry_tables
        RETURN DISTINCT related.name as table_name, length(path) as distance
        ORDER BY distance ASC
        """

        params = {"entry_tables": entry_tables}

        try:
            results = self.neo4j.execute_query(query, params)
            related_tables = [r["table_name"] for r in results]

            logger.debug(f"通过外键找到 {len(related_tables)} 张相关表")
            return related_tables

        except Exception as e:
            logger.error(f"查找相关表失败: {e}")
            return []

    def _build_subgraph(
        self, tables: List[str], matched_entities: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        构建子图详细信息

        Args:
            tables: 表名列表
            matched_entities: 实体匹配结果

        Returns:
            子图信息
        """
        subgraph = {
            "tables": [],
            "relationships": [],
            "highlighted_columns": [],  # 高亮显示的列（与查询最相关）
            "metadata": {
                "total_tables": len(tables),
                "entry_tables": self._get_entry_tables(matched_entities),
            },
        }

        # 获取每张表的详细信息
        for table_name in tables:
            table_info = self._get_table_info(table_name)
            if table_info:
                subgraph["tables"].append(table_info)

        # 获取表之间的关系
        relationships = self._get_relationships(tables)
        subgraph["relationships"] = relationships

        # 标记高亮列
        highlighted = self._identify_highlighted_columns(matched_entities, tables)
        subgraph["highlighted_columns"] = highlighted

        return subgraph

    def _get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        获取表的详细信息

        Args:
            table_name: 表名

        Returns:
            表信息
        """
        query = """
        MATCH (t:Table {name: $table_name})
        OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
        RETURN t.name as name, t.comment as comment, t.primary_keys as primary_keys,
               collect({
                   name: c.name,
                   type: c.type,
                   nullable: c.nullable,
                   primary_key: c.primary_key,
                   comment: c.comment
               }) as columns
        """

        try:
            results = self.neo4j.execute_query(query, {"table_name": table_name})

            if not results:
                return None

            result = results[0]

            return {
                "name": result["name"],
                "comment": result.get("comment", ""),
                "primary_keys": result.get("primary_keys", []),
                "columns": [c for c in result["columns"] if c["name"] is not None],
            }

        except Exception as e:
            logger.error(f"获取表信息失败 {table_name}: {e}")
            return None

    def _get_relationships(self, tables: List[str]) -> List[Dict[str, Any]]:
        """
        获取表之间的外键关系

        Args:
            tables: 表名列表

        Returns:
            关系列表
        """
        query = """
        MATCH (from:Table)-[r:FOREIGN_KEY]->(to:Table)
        WHERE from.name IN $tables AND to.name IN $tables
        RETURN from.name as from_table, to.name as to_table,
               r.from_columns as from_columns, r.to_columns as to_columns
        """

        try:
            results = self.neo4j.execute_query(query, {"tables": tables})

            return [
                {
                    "from_table": r["from_table"],
                    "to_table": r["to_table"],
                    "from_columns": r["from_columns"],
                    "to_columns": r["to_columns"],
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"获取表关系失败: {e}")
            return []

    def _identify_highlighted_columns(
        self, matched_entities: Dict[str, List[Dict[str, Any]]], tables: List[str]
    ) -> List[Dict[str, str]]:
        """
        识别应该高亮显示的列（与查询最相关的列）

        Args:
            matched_entities: 实体匹配结果
            tables: 表列表

        Returns:
            高亮列列表 [{'table': 'users', 'column': 'age'}, ...]
        """
        highlighted = []

        # 从列匹配中获取
        for col_match in matched_entities.get("columns", []):
            if col_match["table_name"] in tables:
                highlighted.append(
                    {
                        "table": col_match["table_name"],
                        "column": col_match["name"],
                        "reason": "direct_match",
                        "score": col_match.get("score", 0.5),
                    }
                )

        # 从概念匹配中获取
        for concept_match in matched_entities.get("concepts", []):
            concept = concept_match.get("concept", {})
            for related_col in concept.get("related_columns", []):
                if related_col["table"] in tables:
                    highlighted.append(
                        {
                            "table": related_col["table"],
                            "column": related_col["column"],
                            "reason": "concept_match",
                            "score": 0.9,
                        }
                    )

        # 去重
        seen = set()
        unique_highlighted = []
        for item in highlighted:
            key = f"{item['table']}.{item['column']}"
            if key not in seen:
                seen.add(key)
                unique_highlighted.append(item)

        return sorted(unique_highlighted, key=lambda x: x["score"], reverse=True)

    def _empty_subgraph(self) -> Dict[str, Any]:
        """返回空子图"""
        return {
            "tables": [],
            "relationships": [],
            "highlighted_columns": [],
            "metadata": {"total_tables": 0, "entry_tables": []},
        }

    def retrieve_path_between_tables(
        self, table1: str, table2: str, max_length: int = 3
    ) -> List[List[str]]:
        """
        查找两张表之间的连接路径

        Args:
            table1: 表1
            table2: 表2
            max_length: 最大路径长度

        Returns:
            路径列表，每个路径是表名列表
        """
        query = f"""
        MATCH path = shortestPath((t1:Table {{name: $table1}})-[:FOREIGN_KEY*1..{max_length}]-(t2:Table {{name: $table2}}))
        RETURN [node in nodes(path) | node.name] as path
        LIMIT 5
        """

        try:
            results = self.neo4j.execute_query(
                query, {"table1": table1, "table2": table2}
            )

            paths = [r["path"] for r in results]
            logger.debug(f"找到 {len(paths)} 条路径连接 {table1} 和 {table2}")
            return paths

        except Exception as e:
            logger.error(f"查找表路径失败: {e}")
            return []
