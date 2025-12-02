"""
基础单元测试
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.utils import (
    normalize_text,
    extract_sql_from_markdown,
    validate_sql,
    calculate_similarity,
    hash_text,
)


class TestUtils:
    """测试工具函数"""

    def test_normalize_text(self):
        """测试文本标准化"""
        text = "  Hello   World  "
        result = normalize_text(text)
        assert result == "hello world"

    def test_extract_sql_from_markdown(self):
        """测试从Markdown提取SQL"""
        # 测试带sql标记的代码块
        text = """
        ```sql
        SELECT * FROM users;
        ```
        """
        sql = extract_sql_from_markdown(text)
        assert sql == "SELECT * FROM users;"

        # 测试纯文本
        text = "SELECT * FROM orders;"
        sql = extract_sql_from_markdown(text)
        assert sql == "SELECT * FROM orders;"

    def test_validate_sql(self):
        """测试SQL验证"""
        # 有效的SQL
        assert validate_sql("SELECT * FROM users") == True
        assert validate_sql("INSERT INTO users VALUES (1)") == True

        # 无效的SQL
        assert validate_sql("") == False
        assert validate_sql("   ") == False
        assert validate_sql("Hello World") == False

    def test_calculate_similarity(self):
        """测试相似度计算"""
        sim1 = calculate_similarity("hello", "hello")
        assert sim1 == 1.0

        sim2 = calculate_similarity("hello", "world")
        assert sim2 < 0.5

        sim3 = calculate_similarity("", "hello")
        assert sim3 == 0.0

    def test_hash_text(self):
        """测试文本哈希"""
        hash1 = hash_text("hello")
        hash2 = hash_text("hello")
        hash3 = hash_text("world")

        assert hash1 == hash2  # 相同文本产生相同哈希
        assert hash1 != hash3  # 不同文本产生不同哈希
        assert len(hash1) == 32  # MD5哈希长度


class TestCache:
    """测试缓存功能"""

    def test_cache_basic(self):
        """测试基本缓存操作"""
        from src.utils import SimpleCache

        cache = SimpleCache(max_size=10, ttl=3600)

        # 测试设置和获取
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # 测试不存在的键
        assert cache.get("nonexistent") is None

        # 测试缓存大小
        assert cache.size() == 1

        # 测试清空
        cache.clear()
        assert cache.size() == 0


# 运行测试的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
