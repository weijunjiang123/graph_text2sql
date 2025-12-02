"""
Prompt 构建器 - 构建发送给 LLM 的 Prompt
"""

from typing import Any, Dict, List, Optional

from loguru import logger


class PromptBuilder:
    """
    Prompt 构建器

    负责根据剪枝后的 Schema 和用户问题构建优化的 Prompt
    """

    def __init__(
        self,
        system_message: Optional[str] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        include_tips: bool = True,
    ):
        """
        初始化 Prompt 构建器

        Args:
            system_message: 系统消息
            few_shot_examples: Few-shot 示例
            include_tips: 是否包含 SQL 编写提示
        """
        self.system_message = system_message or self._default_system_message()
        self.few_shot_examples = few_shot_examples or []
        self.include_tips = include_tips

    def _default_system_message(self) -> str:
        """默认系统消息"""
        return """You are a SQL expert. Your task is to generate accurate SQL queries based on the provided database schema and user question.

Always follow these rules:
1. Use standard SQL syntax
2. Include table aliases for clarity (e.g., SELECT u.name FROM users u)
3. Add appropriate WHERE clauses based on the question
4. Consider NULL value handling
5. Use JOIN when querying multiple tables
6. Add ORDER BY and LIMIT when necessary
7. Return only the SQL query without explanation"""

    def build_prompt(
        self,
        schema_context: str,
        user_question: str,
        additional_context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        构建完整的 Prompt

        Args:
            schema_context: Schema 上下文（来自 SchemaPruner）
            user_question: 用户问题
            additional_context: 额外的上下文信息

        Returns:
            消息列表，格式适用于 LangChain
        """
        messages = []

        # 1. 系统消息
        messages.append({"role": "system", "content": self.system_message})

        # 2. Few-shot 示例
        for example in self.few_shot_examples:
            messages.append(
                {
                    "role": "user",
                    "content": self._format_example_question(
                        example.get("question", ""), example.get("schema", "")
                    ),
                }
            )
            messages.append({"role": "assistant", "content": example.get("sql", "")})

        # 3. 当前问题
        user_content = self._format_user_question(
            schema_context, user_question, additional_context
        )

        messages.append({"role": "user", "content": user_content})

        return messages

    def _format_example_question(self, question: str, schema: str) -> str:
        """格式化示例问题"""
        return f"""Database Schema:
{schema}

Question: {question}

Please generate the SQL query."""

    def _format_user_question(
        self,
        schema_context: str,
        user_question: str,
        additional_context: Optional[str] = None,
    ) -> str:
        """格式化用户问题"""
        sections = []

        # Schema 上下文
        sections.append(schema_context)

        # 额外上下文
        if additional_context:
            sections.append("## Additional Context")
            sections.append(additional_context)
            sections.append("")

        # SQL 编写提示
        if self.include_tips:
            sections.append(self._get_sql_tips())

        # 用户问题
        sections.append("## Task")
        sections.append(f"Generate a SQL query to answer: **{user_question}**")
        sections.append("")
        sections.append(
            "Return only the SQL query, without any explanation or markdown formatting."
        )

        return "\n".join(sections)

    def _get_sql_tips(self) -> str:
        """获取 SQL 编写提示"""
        return """## SQL Writing Tips
- Use meaningful table aliases (e.g., u for users, o for orders)
- Always specify which table a column belongs to when joining tables
- Consider using DISTINCT if duplicates might occur
- Use appropriate aggregate functions (COUNT, SUM, AVG, etc.)
- Add date/time filtering when the question mentions time periods
- Use LIKE for partial string matching
- Remember to handle NULL values with IS NULL or COALESCE

"""

    def add_few_shot_example(
        self, question: str, sql: str, schema: Optional[str] = None
    ):
        """
        添加 Few-shot 示例

        Args:
            question: 问题
            sql: SQL 查询
            schema: Schema（可选）
        """
        example = {"question": question, "sql": sql}

        if schema:
            example["schema"] = schema

        self.few_shot_examples.append(example)
        logger.info(f"添加 Few-shot 示例: {question}")

    def load_examples_from_list(self, examples: List[Dict[str, str]]):
        """
        从列表加载示例

        Args:
            examples: 示例列表
        """
        self.few_shot_examples = examples
        logger.info(f"加载了 {len(examples)} 个 Few-shot 示例")

    @staticmethod
    def create_default_examples() -> List[Dict[str, str]]:
        """创建默认的 Few-shot 示例"""
        return [
            {
                "question": "查询所有用户的姓名和邮箱",
                "schema": "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100), email VARCHAR(100));",
                "sql": "SELECT name, email FROM users;",
            },
            {
                "question": "统计每个城市的用户数量",
                "schema": "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100), city VARCHAR(50));",
                "sql": "SELECT city, COUNT(*) as user_count FROM users GROUP BY city ORDER BY user_count DESC;",
            },
            {
                "question": "查询最近30天内的订单总金额",
                "schema": "CREATE TABLE orders (id INT PRIMARY KEY, user_id INT, total_amount DECIMAL(10,2), created_at DATETIME);",
                "sql": "SELECT SUM(total_amount) as total FROM orders WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY);",
            },
        ]

    def build_simple_prompt(self, user_question: str, schema_ddl: str) -> str:
        """
        构建简单的单条 Prompt（适用于某些 LLM API）

        Args:
            user_question: 用户问题
            schema_ddl: Schema DDL

        Returns:
            完整的 Prompt 字符串
        """
        sections = []

        sections.append("# Task: Generate SQL Query")
        sections.append("")
        sections.append("## Database Schema")
        sections.append("```sql")
        sections.append(schema_ddl)
        sections.append("```")
        sections.append("")
        sections.append("## User Question")
        sections.append(user_question)
        sections.append("")
        sections.append("## Instructions")
        sections.append("Generate a SQL query to answer the question above.")
        sections.append("Return only the SQL query without explanation.")
        sections.append("")
        sections.append("SQL Query:")

        return "\n".join(sections)

    def estimate_token_count(self, messages: List[Dict[str, str]]) -> int:
        """
        估算 Token 数量（粗略估算）

        Args:
            messages: 消息列表

        Returns:
            估算的 Token 数量
        """
        total_chars = sum(len(msg["content"]) for msg in messages)
        # 粗略估算：英文 4 字符约 1 token，中文 1.5 字符约 1 token
        # 取平均值
        estimated_tokens = int(total_chars / 3)
        return estimated_tokens

    def optimize_prompt_length(
        self, messages: List[Dict[str, str]], max_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """
        优化 Prompt 长度（如果超过限制）

        Args:
            messages: 原始消息列表
            max_tokens: 最大 Token 限制

        Returns:
            优化后的消息列表
        """
        current_tokens = self.estimate_token_count(messages)

        if current_tokens <= max_tokens:
            return messages

        logger.warning(f"Prompt 过长 ({current_tokens} tokens)，开始优化...")

        # 策略：减少 Few-shot 示例
        optimized_messages = [messages[0]]  # 保留系统消息

        # 只保留最相关的1-2个示例
        example_pairs = []
        for i in range(1, len(messages) - 1, 2):
            if i + 1 < len(messages) and messages[i]["role"] == "user":
                example_pairs.append((messages[i], messages[i + 1]))

        # 保留最多2个示例
        for pair in example_pairs[:2]:
            optimized_messages.extend(pair)

        # 保留用户问题
        optimized_messages.append(messages[-1])

        new_token_count = self.estimate_token_count(optimized_messages)
        logger.info(f"优化后 Token 数: {new_token_count}")

        return optimized_messages
