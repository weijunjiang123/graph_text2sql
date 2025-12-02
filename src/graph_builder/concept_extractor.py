"""
业务概念提取器 - 从文档或定义中提取业务概念
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


class ConceptExtractor:
    """
    业务概念提取器

    负责从配置文件或文档中提取业务概念，并构建概念到数据库字段的映射
    """

    def __init__(
        self, concept_file: Optional[str] = None, synonym_file: Optional[str] = None
    ):
        """
        初始化概念提取器

        Args:
            concept_file: 业务概念定义文件路径（YAML格式）
            synonym_file: 同义词字典文件路径（YAML格式）
        """
        self.concept_file = concept_file
        self.synonym_file = synonym_file
        self.concepts: List[Dict[str, Any]] = []
        self.synonyms: Dict[str, List[str]] = {}

        if concept_file and Path(concept_file).exists():
            self._load_concepts()

        if synonym_file and Path(synonym_file).exists():
            self._load_synonyms()

    def _load_concepts(self):
        """从 YAML 文件加载业务概念"""
        try:
            with open(self.concept_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.concepts = data.get("concepts", [])

            logger.info(f"加载了 {len(self.concepts)} 个业务概念")

        except Exception as e:
            logger.error(f"加载业务概念失败: {e}")

    def _load_synonyms(self):
        """从 YAML 文件加载同义词字典"""
        try:
            with open(self.synonym_file, "r", encoding="utf-8") as f:
                self.synonyms = yaml.safe_load(f) or {}

            logger.info(f"加载了 {len(self.synonyms)} 组同义词")

        except Exception as e:
            logger.error(f"加载同义词字典失败: {e}")

    def get_all_concepts(self) -> List[Dict[str, Any]]:
        """
        获取所有业务概念

        Returns:
            概念列表
        """
        return self.concepts

    def get_concept_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取业务概念

        Args:
            name: 概念名称

        Returns:
            概念信息
        """
        for concept in self.concepts:
            if concept["name"].lower() == name.lower():
                return concept

            # 检查同义词
            if name.lower() in [s.lower() for s in concept.get("synonyms", [])]:
                return concept

        return None

    def get_synonyms(self, term: str) -> List[str]:
        """
        获取术语的所有同义词

        Args:
            term: 术语

        Returns:
            同义词列表
        """
        term_lower = term.lower()

        # 从字典中查找
        if term_lower in self.synonyms:
            return self.synonyms[term_lower]

        # 从概念中查找
        for concept in self.concepts:
            if concept["name"].lower() == term_lower:
                return concept.get("synonyms", [])

            if term_lower in [s.lower() for s in concept.get("synonyms", [])]:
                return [concept["name"]] + concept.get("synonyms", [])

        return []

    def extract_concepts_from_text(self, text: str) -> List[str]:
        """
        从文本中提取可能的业务概念

        Args:
            text: 输入文本

        Returns:
            提取的概念列表
        """
        extracted = []
        text_lower = text.lower()

        # 匹配已知概念
        for concept in self.concepts:
            concept_name = concept["name"].lower()

            if concept_name in text_lower:
                extracted.append(concept["name"])

            # 检查同义词
            for synonym in concept.get("synonyms", []):
                if synonym.lower() in text_lower:
                    extracted.append(concept["name"])
                    break

        return list(set(extracted))  # 去重

    def create_concept_definition(
        self,
        name: str,
        description: str,
        related_tables: List[str],
        related_columns: List[Dict[str, str]],
        synonyms: Optional[List[str]] = None,
        calculation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建业务概念定义

        Args:
            name: 概念名称
            description: 描述
            related_tables: 相关表列表
            related_columns: 相关列列表 [{'table': 'users', 'column': 'vip_level'}]
            synonyms: 同义词列表
            calculation: 计算公式（可选）

        Returns:
            概念定义字典
        """
        concept = {
            "name": name,
            "description": description,
            "related_tables": related_tables,
            "related_columns": related_columns,
            "synonyms": synonyms or [],
            "calculation": calculation,
        }

        return concept

    def save_concepts_to_file(self, output_file: str):
        """
        将概念保存到 YAML 文件

        Args:
            output_file: 输出文件路径
        """
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                yaml.dump({"concepts": self.concepts}, f, allow_unicode=True, indent=2)

            logger.info(f"概念已保存到: {output_file}")

        except Exception as e:
            logger.error(f"保存概念失败: {e}")

    @staticmethod
    def create_example_concept_file(output_file: str = "data/concepts.yaml"):
        """
        创建示例概念定义文件

        Args:
            output_file: 输出文件路径
        """
        example_concepts = {
            "concepts": [
                {
                    "name": "高价值客户",
                    "description": "购买金额超过10000元或VIP等级大于3的客户",
                    "related_tables": ["customers", "orders"],
                    "related_columns": [
                        {"table": "customers", "column": "vip_level"},
                        {"table": "orders", "column": "total_amount"},
                    ],
                    "synonyms": ["VIP客户", "重要客户", "高端客户"],
                    "calculation": "SUM(total_amount) > 10000 OR vip_level > 3",
                },
                {
                    "name": "活跃用户",
                    "description": "最近30天内有登录记录的用户",
                    "related_tables": ["users", "login_logs"],
                    "related_columns": [
                        {"table": "users", "column": "last_login_time"},
                        {"table": "login_logs", "column": "login_time"},
                    ],
                    "synonyms": ["活跃客户", "在线用户"],
                    "calculation": "last_login_time >= CURRENT_DATE - INTERVAL 30 DAY",
                },
                {
                    "name": "销售额",
                    "description": "订单的总金额",
                    "related_tables": ["orders", "order_items"],
                    "related_columns": [
                        {"table": "orders", "column": "total_amount"},
                        {"table": "order_items", "column": "price"},
                    ],
                    "synonyms": ["营业额", "收入", "交易额"],
                    "calculation": "SUM(total_amount)",
                },
                {
                    "name": "订单转化率",
                    "description": "成功支付的订单数占总订单数的比例",
                    "related_tables": ["orders"],
                    "related_columns": [
                        {"table": "orders", "column": "status"},
                        {"table": "orders", "column": "order_id"},
                    ],
                    "synonyms": ["转化率", "支付率"],
                    "calculation": 'COUNT(CASE WHEN status = "paid" THEN 1 END) / COUNT(*)',
                },
            ]
        }

        # 确保目录存在
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(example_concepts, f, allow_unicode=True, indent=2)

        logger.info(f"示例概念文件已创建: {output_file}")

    @staticmethod
    def create_example_synonym_file(output_file: str = "data/synonyms.yaml"):
        """
        创建示例同义词文件

        Args:
            output_file: 输出文件路径
        """
        example_synonyms = {
            "客户": ["用户", "买家", "customer", "user"],
            "订单": ["交易", "购买记录", "order"],
            "商品": ["产品", "货物", "product", "item"],
            "金额": ["价格", "费用", "amount", "price"],
            "数量": ["个数", "件数", "quantity", "count"],
            "时间": ["日期", "time", "date", "datetime"],
            "地区": ["区域", "城市", "region", "city", "area"],
            "状态": ["状况", "情况", "status", "state"],
        }

        # 确保目录存在
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(example_synonyms, f, allow_unicode=True, indent=2)

        logger.info(f"示例同义词文件已创建: {output_file}")

    def match_concept_to_query(self, query: str) -> List[Dict[str, Any]]:
        """
        将用户查询匹配到业务概念

        Args:
            query: 用户查询

        Returns:
            匹配的概念列表
        """
        matched_concepts = []
        query_lower = query.lower()

        for concept in self.concepts:
            # 检查概念名称
            if concept["name"].lower() in query_lower:
                matched_concepts.append(
                    {
                        "concept": concept,
                        "match_type": "exact",
                        "matched_term": concept["name"],
                    }
                )
                continue

            # 检查同义词
            for synonym in concept.get("synonyms", []):
                if synonym.lower() in query_lower:
                    matched_concepts.append(
                        {
                            "concept": concept,
                            "match_type": "synonym",
                            "matched_term": synonym,
                        }
                    )
                    break

        return matched_concepts
