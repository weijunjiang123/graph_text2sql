"""
关键词提取器 - 从用户问题中提取关键词和实体
"""

import re
from typing import Dict, List, Set

from loguru import logger

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("Spacy 未安装，将使用基础关键词提取")


class KeywordExtractor:
    """
    关键词提取器

    支持多种提取策略：
    1. Spacy NLP（推荐）
    2. 正则表达式匹配
    3. 混合模式
    """

    def __init__(self, method: str = "hybrid", spacy_model: str = "zh_core_web_sm"):
        """
        初始化关键词提取器

        Args:
            method: 提取方法 - spacy, regex, hybrid
            spacy_model: Spacy 模型名称
        """
        self.method = method
        self.nlp = None

        # 如果使用 Spacy
        if method in ["spacy", "hybrid"] and SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load(spacy_model)
                logger.info(f"成功加载 Spacy 模型: {spacy_model}")
            except Exception as e:
                logger.warning(f"加载 Spacy 模型失败: {e}，将使用正则表达式")
                self.method = "regex"

        # 常用停用词（中文）
        self.stopwords = self._load_stopwords()

        # SQL 关键词（需要过滤）
        self.sql_keywords = {
            "select",
            "from",
            "where",
            "and",
            "or",
            "order",
            "by",
            "group",
            "having",
            "limit",
            "join",
            "left",
            "right",
            "inner",
            "outer",
            "on",
            "as",
            "in",
            "not",
            "like",
            "between",
            "is",
            "null",
        }

    def _load_stopwords(self) -> Set[str]:
        """加载停用词表"""
        # 常用中文停用词
        chinese_stopwords = {
            "的",
            "了",
            "在",
            "是",
            "我",
            "有",
            "和",
            "就",
            "不",
            "人",
            "都",
            "一",
            "一个",
            "上",
            "也",
            "很",
            "到",
            "说",
            "要",
            "去",
            "你",
            "会",
            "着",
            "没有",
            "看",
            "好",
            "自己",
            "这",
            "那",
        }

        # 常用英文停用词
        english_stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
        }

        return chinese_stopwords | english_stopwords

    def extract(self, text: str, max_keywords: int = 10) -> List[Dict[str, any]]:
        """
        提取关键词

        Args:
            text: 输入文本
            max_keywords: 最大关键词数量

        Returns:
            关键词列表，每个关键词包含：
            - text: 关键词文本
            - type: 类型（ENTITY, KEYWORD, NUMBER, etc.）
            - score: 重要性分数
        """
        if self.method == "spacy" and self.nlp:
            return self._extract_with_spacy(text, max_keywords)
        elif self.method == "regex":
            return self._extract_with_regex(text, max_keywords)
        else:  # hybrid
            keywords_spacy = (
                self._extract_with_spacy(text, max_keywords) if self.nlp else []
            )
            keywords_regex = self._extract_with_regex(text, max_keywords)

            # 合并去重
            all_keywords = {}
            for kw in keywords_spacy + keywords_regex:
                if kw["text"] not in all_keywords:
                    all_keywords[kw["text"]] = kw
                else:
                    # 保留更高的分数
                    if kw["score"] > all_keywords[kw["text"]]["score"]:
                        all_keywords[kw["text"]] = kw

            return sorted(
                all_keywords.values(), key=lambda x: x["score"], reverse=True
            )[:max_keywords]

    def _extract_with_spacy(self, text: str, max_keywords: int) -> List[Dict[str, any]]:
        """使用 Spacy 提取关键词"""
        doc = self.nlp(text)
        keywords = []

        # 提取命名实体
        for ent in doc.ents:
            if self._should_include(ent.text):
                keywords.append(
                    {
                        "text": ent.text,
                        "type": f"ENTITY_{ent.label_}",
                        "score": 1.0,  # 实体权重最高
                    }
                )

        # 提取名词短语
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.strip()
            if self._should_include(chunk_text) and len(chunk_text) > 1:
                keywords.append(
                    {"text": chunk_text, "type": "NOUN_PHRASE", "score": 0.8}
                )

        # 提取重要词性（名词、动词、形容词）
        for token in doc:
            if token.pos_ in ["NOUN", "PROPN", "VERB", "ADJ"]:
                if self._should_include(token.text):
                    score = 0.7 if token.pos_ in ["NOUN", "PROPN"] else 0.5
                    keywords.append(
                        {"text": token.text, "type": token.pos_, "score": score}
                    )

        # 去重并排序
        unique_keywords = {}
        for kw in keywords:
            if kw["text"] not in unique_keywords:
                unique_keywords[kw["text"]] = kw
            else:
                # 保留更高的分数
                if kw["score"] > unique_keywords[kw["text"]]["score"]:
                    unique_keywords[kw["text"]] = kw

        return sorted(unique_keywords.values(), key=lambda x: x["score"], reverse=True)[
            :max_keywords
        ]

    def _extract_with_regex(self, text: str, max_keywords: int) -> List[Dict[str, any]]:
        """使用正则表达式提取关键词"""
        keywords = []

        # 1. 提取数字和单位组合（如：100元、30天、5个）
        number_patterns = [
            r"\d+[元|块|万|千|百|个|件|人|天|月|年|次]",
            r"\d+\.\d+[元|块|万]?",
            r"\d+%",
        ]

        for pattern in number_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                keywords.append({"text": match.group(), "type": "NUMBER", "score": 0.9})

        # 2. 提取时间表达式
        time_patterns = [
            r"(今天|明天|昨天|上周|本周|下周|上月|本月|下月|去年|今年|明年)",
            r"\d{4}年\d{1,2}月",
            r"\d{1,2}月\d{1,2}日",
            r"最近\d+[天|月|年]",
        ]

        for pattern in time_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                keywords.append({"text": match.group(), "type": "TIME", "score": 0.85})

        # 3. 提取地名（简单规则）
        location_pattern = r"[北京|上海|广州|深圳|杭州|成都|武汉|西安|南京|重庆]"
        matches = re.finditer(location_pattern, text)
        for match in matches:
            keywords.append({"text": match.group(), "type": "LOCATION", "score": 0.85})

        # 4. 改进的中文分词 - 使用滑动窗口提取多种长度的词
        # 优先提取较长的词组（2-6个字），给予更高权重
        for length in [6, 5, 4, 3, 2]:
            pattern = f"[\u4e00-\u9fa5]{{{length}}}"
            chinese_words = re.findall(pattern, text)
            for word in chinese_words:
                if self._should_include(word):
                    # 较长的词给予更高分数
                    score = 0.5 + (length * 0.05)  # 2字:0.6, 3字:0.65, 4字:0.7, 5字:0.75, 6字:0.8
                    keywords.append({"text": word, "type": "KEYWORD", "score": score})

        # 5. 提取英文单词
        english_words = re.findall(r"\b[a-zA-Z]{2,}\b", text)
        for word in english_words:
            if self._should_include(word):
                keywords.append({"text": word, "type": "KEYWORD", "score": 0.6})

        # 去重并排序（保留最高分）
        unique_keywords = {}
        for kw in keywords:
            if kw["text"] not in unique_keywords:
                unique_keywords[kw["text"]] = kw
            else:
                # 保留更高的分数
                if kw["score"] > unique_keywords[kw["text"]]["score"]:
                    unique_keywords[kw["text"]] = kw

        return sorted(unique_keywords.values(), key=lambda x: x["score"], reverse=True)[
            :max_keywords
        ]

    def _should_include(self, text: str) -> bool:
        """
        判断是否应该包含该关键词

        Args:
            text: 关键词文本

        Returns:
            是否包含
        """
        text_lower = text.lower().strip()

        # 过滤条件
        if not text_lower:
            return False

        if len(text_lower) < 2:  # 太短
            return False

        if text_lower in self.stopwords:  # 停用词
            return False

        if text_lower in self.sql_keywords:  # SQL 关键词
            return False

        # 过滤纯标点符号
        if re.match(r"^[^\w\u4e00-\u9fa5]+$", text):
            return False

        return True

    def extract_entities(self, text: str) -> List[str]:
        """
        提取实体（简化版，只返回实体文本）

        Args:
            text: 输入文本

        Returns:
            实体列表
        """
        keywords = self.extract(text)

        # 优先返回高分关键词
        entities = [kw["text"] for kw in keywords if kw["score"] >= 0.7]

        return entities

    def extract_table_column_hints(self, text: str) -> Dict[str, List[str]]:
        """
        从问题中提取可能的表名和列名提示

        Args:
            text: 用户问题

        Returns:
            {'tables': [...], 'columns': [...]}
        """
        hints = {"tables": [], "columns": []}

        # 常见表名关键词映射
        table_keywords = {
            "用户": ["users", "customers", "user"],
            "订单": ["orders", "order"],
            "商品": ["products", "items", "goods"],
            "支付": ["payments", "payment"],
            "日志": ["logs", "log"],
            "评论": ["comments", "reviews"],
        }

        # 常见列名关键词映射
        column_keywords = {
            "名称": ["name", "title"],
            "金额": ["amount", "price", "total"],
            "数量": ["quantity", "count", "number"],
            "时间": ["time", "date", "created_at"],
            "状态": ["status", "state"],
            "类型": ["type", "category"],
        }

        # 提取表名提示
        for keyword, table_names in table_keywords.items():
            if keyword in text:
                hints["tables"].extend(table_names)

        # 提取列名提示
        for keyword, column_names in column_keywords.items():
            if keyword in text:
                hints["columns"].extend(column_names)

        return hints
