"""
SQL 生成器 - 使用 LLM 生成 SQL 查询
"""

from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.config import Config
from src.llm_integration.prompt_builder import PromptBuilder
from src.utils import extract_sql_from_markdown, validate_sql


class SQLGenerator:
    """
    SQL 生成器

    使用 LLM 根据 Schema 和用户问题生成 SQL 查询
    """

    def __init__(self, config: Config, prompt_builder: Optional[PromptBuilder] = None):
        """
        初始化 SQL 生成器

        Args:
            config: 配置对象
            prompt_builder: Prompt 构建器
        """
        self.config = config
        self.prompt_builder = prompt_builder or PromptBuilder(
            system_message=config.prompt.system_message, include_tips=True
        )
        self.llm = self._initialize_llm()

    def _initialize_llm(self):
        """初始化 LLM"""
        provider = self.config.llm.provider

        try:
            if provider == "openai":
                from langchain_openai import ChatOpenAI

                llm = ChatOpenAI(
                    model=self.config.llm.openai.model,
                    temperature=self.config.llm.openai.temperature,
                    max_tokens=self.config.llm.openai.max_tokens,
                    api_key=self.config.llm.openai.api_key,
                    base_url=self.config.llm.openai.base_url,
                )

            elif provider == "anthropic":
                from langchain_anthropic import ChatAnthropic

                llm = ChatAnthropic(
                    model=self.config.llm.anthropic.model,
                    temperature=self.config.llm.anthropic.temperature,
                    max_tokens=self.config.llm.anthropic.max_tokens,
                    api_key=self.config.llm.anthropic.api_key,
                )
            elif provider == "openai_compatible":
                from langchain_openai import ChatOpenAI

                # 使用 OpenAI Compatible API（如 vLLM, LocalAI, Ollama 等）
                llm = ChatOpenAI(
                    model=self.config.llm.openai_compatible.model,
                    temperature=self.config.llm.openai_compatible.temperature,
                    max_tokens=self.config.llm.openai_compatible.max_tokens,
                    api_key=self.config.llm.openai_compatible.api_key,
                    base_url=self.config.llm.openai_compatible.base_url,
                )
                logger.info(f"使用 OpenAI Compatible API: {self.config.llm.openai_compatible.base_url}")


            else:
                raise ValueError(f"不支持的 LLM 提供商: {provider}")

            logger.info(f"成功初始化 LLM: {provider}")
            return llm

        except Exception as e:
            logger.error(f"初始化 LLM 失败: {e}")
            raise

    def generate_sql(
        self,
        schema_context: str,
        user_question: str,
        additional_context: Optional[str] = None,
        retry_on_error: bool = True,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        生成 SQL 查询

        Args:
            schema_context: Schema 上下文
            user_question: 用户问题
            additional_context: 额外上下文
            retry_on_error: 是否在错误时重试
            max_retries: 最大重试次数

        Returns:
            生成结果：
            {
                'sql': '生成的SQL',
                'success': True/False,
                'error': '错误信息（如有）',
                'attempts': 尝试次数
            }
        """
        logger.info(f"开始生成 SQL: {user_question}")

        attempts = 0
        last_error = None

        while attempts <= max_retries:
            attempts += 1

            try:
                # 构建 Prompt
                messages = self.prompt_builder.build_prompt(
                    schema_context, user_question, additional_context
                )

                # 估算 Token
                token_count = self.prompt_builder.estimate_token_count(messages)
                logger.debug(f"Prompt Token 估算: {token_count}")

                # 如果超过限制，优化 Prompt
                max_tokens = (
                    self.config.llm.openai.max_tokens
                    if self.config.llm.provider == "openai"
                    else self.config.llm.anthropic.max_tokens
                )
                if token_count > max_tokens * 0.7:  # 留出空间给响应
                    messages = self.prompt_builder.optimize_prompt_length(
                        messages, int(max_tokens * 0.7)
                    )

                # 调用 LLM
                sql = self._call_llm(messages)

                # 提取 SQL
                sql = extract_sql_from_markdown(sql)

                # 验证 SQL
                if not validate_sql(sql):
                    raise ValueError("生成的 SQL 无效")

                logger.info(f"SQL 生成成功 (尝试 {attempts} 次)")

                return {
                    "sql": sql,
                    "success": True,
                    "error": None,
                    "attempts": attempts,
                }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"SQL 生成失败 (尝试 {attempts}/{max_retries + 1}): {e}")

                if not retry_on_error or attempts > max_retries:
                    break

        # 所有尝试都失败
        logger.error(f"SQL 生成最终失败: {last_error}")

        return {
            "sql": None,
            "success": False,
            "error": last_error,
            "attempts": attempts,
        }

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """
        调用 LLM

        Args:
            messages: 消息列表

        Returns:
            LLM 响应
        """
        # 转换为 LangChain 消息格式
        langchain_messages = []

        for msg in messages:
            if msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            # assistant 消息在 few-shot 中使用，但 LangChain 会自动处理

        # 调用 LLM
        response = self.llm.invoke(langchain_messages)

        return response.content

    def generate_sql_with_explanation(
        self, schema_context: str, user_question: str
    ) -> Dict[str, Any]:
        """
        生成 SQL 并提供解释

        Args:
            schema_context: Schema 上下文
            user_question: 用户问题

        Returns:
            包含 SQL 和解释的结果
        """
        # 修改 Prompt 要求包含解释
        modified_context = f"""{schema_context}

## Task
Generate a SQL query to answer: **{user_question}**

Please provide:
1. The SQL query
2. A brief explanation of what the query does

Format:
```sql
-- Your SQL query here
```

Explanation: [Your explanation here]
"""

        messages = [
            {"role": "system", "content": self.prompt_builder.system_message},
            {"role": "user", "content": modified_context},
        ]

        try:
            response = self._call_llm(messages)

            # 提取 SQL 和解释
            sql = extract_sql_from_markdown(response)

            # 简单提取解释（在 SQL 后面的文本）
            explanation_start = response.lower().find("explanation")
            explanation = ""
            if explanation_start != -1:
                explanation = response[explanation_start:].strip()

            return {
                "sql": sql,
                "explanation": explanation,
                "success": True,
                "error": None,
            }

        except Exception as e:
            logger.error(f"生成带解释的 SQL 失败: {e}")
            return {"sql": None, "explanation": None, "success": False, "error": str(e)}

    def validate_and_fix_sql(
        self, sql: str, schema_context: str, error_message: str
    ) -> Dict[str, Any]:
        """
        验证并修复 SQL（当执行出错时）

        Args:
            sql: 原始 SQL
            schema_context: Schema 上下文
            error_message: 错误信息

        Returns:
            修复后的 SQL
        """
        fix_prompt = f"""The following SQL query has an error:

```sql
{sql}
```

Error: {error_message}

Database Schema:
{schema_context}

Please fix the SQL query to resolve the error. Return only the corrected SQL query.
"""

        messages = [
            {"role": "system", "content": "You are a SQL expert who fixes SQL errors."},
            {"role": "user", "content": fix_prompt},
        ]

        try:
            response = self._call_llm(messages)
            fixed_sql = extract_sql_from_markdown(response)

            logger.info("SQL 修复成功")

            return {"sql": fixed_sql, "success": True, "error": None}

        except Exception as e:
            logger.error(f"SQL 修复失败: {e}")
            return {"sql": None, "success": False, "error": str(e)}

    def batch_generate(self, queries: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        批量生成 SQL

        Args:
            queries: 查询列表，每个包含 schema_context 和 user_question

        Returns:
            生成结果列表
        """
        results = []

        for i, query in enumerate(queries):
            logger.info(f"批量生成 {i + 1}/{len(queries)}")

            result = self.generate_sql(query["schema_context"], query["user_question"])

            results.append(result)

        # 统计
        success_count = sum(1 for r in results if r["success"])
        logger.info(f"批量生成完成: {success_count}/{len(queries)} 成功")

        return results
