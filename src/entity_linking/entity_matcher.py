"""
实体匹配器 - 将提取的关键词匹配到知识图谱节点
"""

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from src.database import Neo4jConnector
from src.entity_linking.keyword_extractor import KeywordExtractor
from src.graph_builder.concept_extractor import ConceptExtractor


class EntityMatcher:
    """
    实体匹配器

    负责将提取的关键词匹配到知识图谱中的节点（表、列、概念、值）
    """

    def __init__(
        self,
        neo4j_connector: Neo4jConnector,
        keyword_extractor: KeywordExtractor,
        concept_extractor: Optional[ConceptExtractor] = None,
        fuzzy_threshold: float = 0.85,
    ):
        """
        初始化实体匹配器

        Args:
            neo4j_connector: Neo4j 连接器
            keyword_extractor: 关键词提取器
            concept_extractor: 概念提取器（可选）
            fuzzy_threshold: 模糊匹配阈值
        """
        self.neo4j = neo4j_connector
        self.keyword_extractor = keyword_extractor
        self.concept_extractor = concept_extractor
        self.fuzzy_threshold = fuzzy_threshold

    def match_entities(self, query: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        从查询中匹配实体到图谱节点

        Args:
            query: 用户查询

        Returns:
            匹配结果字典：
            {
                'tables': [...],
                'columns': [...],
                'concepts': [...],
                'values': [...],
                'keywords': [...]
            }
        """
        # 1. 提取关键词
        keywords = self.keyword_extractor.extract(query, max_keywords=15)
        logger.debug(
            f"提取到 {len(keywords)} 个关键词: {[k['text'] for k in keywords]}"
        )

        matches = {
            "tables": [],
            "columns": [],
            "concepts": [],
            "values": [],
            "keywords": keywords,
        }

        # 2. 匹配业务概念
        if self.concept_extractor:
            concept_matches = self.concept_extractor.match_concept_to_query(query)
            matches["concepts"] = concept_matches
            logger.debug(f"匹配到 {len(concept_matches)} 个业务概念")

        # 3. 匹配表节点
        for kw in keywords:
            table_matches = self._match_tables(kw["text"])
            matches["tables"].extend(table_matches)

        # 4. 匹配列节点
        for kw in keywords:
            column_matches = self._match_columns(kw["text"])
            matches["columns"].extend(column_matches)

        # 5. 匹配值节点
        for kw in keywords:
            if kw["type"] in ["NUMBER", "TIME", "LOCATION", "ENTITY_LOC"]:
                value_matches = self._match_values(kw["text"])
                matches["values"].extend(value_matches)

        # 去重
        matches["tables"] = self._deduplicate_matches(matches["tables"])
        matches["columns"] = self._deduplicate_matches(matches["columns"])
        matches["values"] = self._deduplicate_matches(matches["values"])

        logger.info(
            f"实体匹配完成: {len(matches['tables'])} 张表, "
            f"{len(matches['columns'])} 个列, {len(matches['concepts'])} 个概念"
        )

        return matches

    def _match_tables(self, keyword: str) -> List[Dict[str, Any]]:
        """
        匹配表节点

        Args:
            keyword: 关键词

        Returns:
            匹配的表节点列表
        """
        # 精确匹配
        exact_query = """
        MATCH (t:Table)
        WHERE toLower(t.name) CONTAINS toLower($keyword)
           OR toLower(t.comment) CONTAINS toLower($keyword)
        RETURN t.name as name, t.comment as comment, 1.0 as score
        """

        exact_matches = self.neo4j.execute_query(exact_query, {"keyword": keyword})

        if exact_matches:
            return [
                {
                    "name": m["name"],
                    "comment": m["comment"],
                    "score": m["score"],
                    "match_type": "exact",
                }
                for m in exact_matches
            ]

        # 模糊匹配
        all_tables_query = "MATCH (t:Table) RETURN t.name as name, t.comment as comment"
        all_tables = self.neo4j.execute_query(all_tables_query)

        fuzzy_matches = []
        for table in all_tables:
            # 计算相似度
            name_similarity = self._calculate_similarity(keyword, table["name"])
            comment_similarity = self._calculate_similarity(
                keyword, table.get("comment", "")
            )

            max_similarity = max(name_similarity, comment_similarity)

            if max_similarity >= self.fuzzy_threshold:
                fuzzy_matches.append(
                    {
                        "name": table["name"],
                        "comment": table.get("comment", ""),
                        "score": max_similarity,
                        "match_type": "fuzzy",
                    }
                )

        return fuzzy_matches

    def _match_columns(self, keyword: str) -> List[Dict[str, Any]]:
        """
        匹配列节点

        Args:
            keyword: 关键词

        Returns:
            匹配的列节点列表
        """
        # 精确匹配
        exact_query = """
        MATCH (c:Column)
        WHERE toLower(c.name) CONTAINS toLower($keyword)
           OR toLower(c.comment) CONTAINS toLower($keyword)
        RETURN c.table_name as table_name, c.name as name, 
               c.comment as comment, c.type as type, 1.0 as score
        LIMIT 20
        """

        exact_matches = self.neo4j.execute_query(exact_query, {"keyword": keyword})

        if exact_matches:
            return [
                {
                    "table_name": m["table_name"],
                    "name": m["name"],
                    "comment": m["comment"],
                    "type": m["type"],
                    "score": m["score"],
                    "match_type": "exact",
                }
                for m in exact_matches
            ]

        # 模糊匹配（只对关键词较长的情况）
        if len(keyword) >= 3:
            all_columns_query = """
            MATCH (c:Column)
            RETURN c.table_name as table_name, c.name as name, 
                   c.comment as comment, c.type as type
            LIMIT 100
            """

            all_columns = self.neo4j.execute_query(all_columns_query)

            fuzzy_matches = []
            for col in all_columns:
                name_similarity = self._calculate_similarity(keyword, col["name"])
                comment_similarity = self._calculate_similarity(
                    keyword, col.get("comment", "")
                )

                max_similarity = max(name_similarity, comment_similarity)

                if max_similarity >= self.fuzzy_threshold:
                    fuzzy_matches.append(
                        {
                            "table_name": col["table_name"],
                            "name": col["name"],
                            "comment": col.get("comment", ""),
                            "type": col["type"],
                            "score": max_similarity,
                            "match_type": "fuzzy",
                        }
                    )

            return fuzzy_matches

        return []

    def _match_values(self, keyword: str) -> List[Dict[str, Any]]:
        """
        匹配值节点

        Args:
            keyword: 关键词

        Returns:
            匹配的值节点列表
        """
        query = """
        MATCH (v:Value)
        WHERE toLower(v.value) = toLower($keyword)
        RETURN v.table_name as table_name, v.column_name as column_name,
               v.value as value, 1.0 as score
        LIMIT 10
        """

        matches = self.neo4j.execute_query(query, {"keyword": keyword})

        return [
            {
                "table_name": m["table_name"],
                "column_name": m["column_name"],
                "value": m["value"],
                "score": m["score"],
                "match_type": "exact",
            }
            for m in matches
        ]

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            相似度分数 [0, 1]
        """
        if not text1 or not text2:
            return 0.0

        # 转小写
        text1 = text1.lower()
        text2 = text2.lower()

        # 使用 SequenceMatcher 计算相似度
        return SequenceMatcher(None, text1, text2).ratio()

    def _deduplicate_matches(
        self, matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        去除重复的匹配结果

        Args:
            matches: 匹配结果列表

        Returns:
            去重后的列表
        """
        seen = set()
        unique_matches = []

        for match in matches:
            # 生成唯一标识
            if "table_name" in match and "name" in match:
                # 列节点
                key = f"{match['table_name']}.{match['name']}"
            elif "name" in match:
                # 表节点
                key = match["name"]
            elif "value" in match:
                # 值节点
                key = f"{match.get('table_name', '')}.{match.get('column_name', '')}.{match['value']}"
            else:
                continue

            if key not in seen:
                seen.add(key)
                unique_matches.append(match)

        # 按分数排序
        return sorted(unique_matches, key=lambda x: x.get("score", 0), reverse=True)

    def get_related_tables_from_matches(
        self, matches: Dict[str, List[Dict[str, Any]]]
    ) -> List[str]:
        """
        从匹配结果中提取相关表名

        Args:
            matches: 匹配结果

        Returns:
            表名列表
        """
        tables = set()

        # 从表匹配中获取
        for table_match in matches.get("tables", []):
            tables.add(table_match["name"])

        # 从列匹配中获取
        for col_match in matches.get("columns", []):
            tables.add(col_match["table_name"])

        # 从概念匹配中获取
        for concept_match in matches.get("concepts", []):
            concept = concept_match.get("concept", {})
            for related_table in concept.get("related_tables", []):
                tables.add(related_table)

        # 从值匹配中获取
        for value_match in matches.get("values", []):
            if value_match.get("table_name"):
                tables.add(value_match["table_name"])

        return list(tables)

    def get_related_columns_from_matches(
        self, matches: Dict[str, List[Dict[str, Any]]]
    ) -> List[Tuple[str, str]]:
        """
        从匹配结果中提取相关列（表名，列名）

        Args:
            matches: 匹配结果

        Returns:
            (表名, 列名) 元组列表
        """
        columns = set()

        # 从列匹配中获取
        for col_match in matches.get("columns", []):
            columns.add((col_match["table_name"], col_match["name"]))

        # 从概念匹配中获取
        for concept_match in matches.get("concepts", []):
            concept = concept_match.get("concept", {})
            for related_col in concept.get("related_columns", []):
                columns.add((related_col["table"], related_col["column"]))

        return list(columns)
