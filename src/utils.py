"""
工具函数模块
"""

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


def setup_logger(config):
    """设置日志系统"""
    logger.add(
        config.logging.file,
        rotation=config.logging.max_bytes,
        retention=config.logging.backup_count,
        level=config.logging.level,
        format=config.logging.format,
        encoding="utf-8",
    )
    return logger


def normalize_text(text: str) -> str:
    """
    标准化文本
    - 转小写
    - 去除多余空格
    - 去除特殊字符
    """
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_sql_from_markdown(text: str) -> str:
    """
    从 Markdown 格式文本中提取 SQL

    Args:
        text: 可能包含 Markdown 格式的文本

    Returns:
        提取的 SQL 语句
    """
    # 尝试提取 ```sql ... ``` 代码块
    sql_pattern = r"```sql\s*(.*?)\s*```"
    matches = re.findall(sql_pattern, text, re.DOTALL | re.IGNORECASE)

    if matches:
        return matches[0].strip()

    # 尝试提取 ``` ... ``` 代码块
    code_pattern = r"```\s*(.*?)\s*```"
    matches = re.findall(code_pattern, text, re.DOTALL)

    if matches:
        return matches[0].strip()

    # 如果没有代码块，返回原文本
    return text.strip()


def validate_sql(sql: str) -> bool:
    """
    基础 SQL 验证

    Args:
        sql: SQL 语句

    Returns:
        是否为有效的 SQL
    """
    if not sql or not sql.strip():
        return False

    # 检查是否包含基本的 SQL 关键字
    sql_upper = sql.upper()
    valid_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"]

    return any(keyword in sql_upper for keyword in valid_keywords)


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度（简单的 Jaccard 相似度）

    Args:
        text1: 文本1
        text2: 文本2

    Returns:
        相似度分数 [0, 1]
    """
    set1 = set(text1.lower().split())
    set2 = set(text2.lower().split())

    if not set1 or not set2:
        return 0.0

    intersection = set1.intersection(set2)
    union = set1.union(set2)

    return len(intersection) / len(union)


def hash_text(text: str) -> str:
    """
    生成文本的哈希值（用于缓存键）

    Args:
        text: 输入文本

    Returns:
        MD5 哈希值
    """
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def format_schema_for_prompt(schema_info: Dict[str, Any]) -> str:
    """
    将 Schema 信息格式化为 Prompt 友好的字符串

    Args:
        schema_info: Schema 信息字典

    Returns:
        格式化的 Schema 字符串
    """
    output = []

    for table in schema_info.get("tables", []):
        table_name = table["name"]
        comment = table.get("comment", "")

        # 表定义
        if comment:
            output.append(f"-- Table: {table_name} ({comment})")
        else:
            output.append(f"-- Table: {table_name}")

        output.append(f"CREATE TABLE {table_name} (")

        # 列定义
        columns = []
        for col in table.get("columns", []):
            col_name = col["name"]
            col_type = col["type"]
            col_comment = col.get("comment", "")

            col_def = f"  {col_name} {col_type}"

            # 添加约束
            if col.get("primary_key"):
                col_def += " PRIMARY KEY"
            if col.get("not_null"):
                col_def += " NOT NULL"

            # 添加注释
            if col_comment:
                col_def += f"  -- {col_comment}"

            columns.append(col_def)

        output.append(",\n".join(columns))
        output.append(");")
        output.append("")

        # 外键关系
        for fk in table.get("foreign_keys", []):
            output.append(
                f"-- Foreign Key: {table_name}.{fk['column']} -> "
                f"{fk['ref_table']}.{fk['ref_column']}"
            )

        output.append("")

    return "\n".join(output)


def parse_cypher_result(result: List[Dict]) -> List[Dict]:
    """
    解析 Cypher 查询结果

    Args:
        result: Neo4j 查询结果

    Returns:
        解析后的结果列表
    """
    parsed = []

    for record in result:
        item = {}
        for key, value in record.items():
            # 处理 Neo4j 节点对象
            if hasattr(value, "__dict__"):
                item[key] = dict(value)
            else:
                item[key] = value
        parsed.append(item)

    return parsed


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本

    Args:
        text: 输入文本
        max_length: 最大长度
        suffix: 后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def measure_time(func):
    """装饰器：测量函数执行时间"""

    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.debug(f"{func.__name__} 执行时间: {duration:.2f}s")
        return result

    return wrapper


class SimpleCache:
    """简单的内存缓存实现"""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        Args:
            max_size: 最大缓存条目数
            ttl: 缓存过期时间（秒）
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self.cache:
            return None

        entry = self.cache[key]

        # 检查是否过期
        if datetime.now().timestamp() - entry["timestamp"] > self.ttl:
            del self.cache[key]
            return None

        return entry["value"]

    def set(self, key: str, value: Any):
        """设置缓存值"""
        # 如果缓存已满，删除最旧的条目
        if len(self.cache) >= self.max_size:
            oldest_key = min(
                self.cache.keys(), key=lambda k: self.cache[k]["timestamp"]
            )
            del self.cache[oldest_key]

        self.cache[key] = {"value": value, "timestamp": datetime.now().timestamp()}

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    安全地解析 JSON

    Args:
        text: JSON 字符串
        default: 解析失败时的默认值

    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"JSON 解析失败: {truncate_text(text)}")
        return default


def merge_dicts(*dicts: Dict) -> Dict:
    """
    合并多个字典

    Args:
        *dicts: 要合并的字典

    Returns:
        合并后的字典
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result
