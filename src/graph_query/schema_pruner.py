"""
Schema 剪枝器 - 将子图转换为精简的 Schema 描述
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from src.utils import format_schema_for_prompt


class SchemaPruner:
    """
    Schema 剪枝器

    将检索到的子图转换为适合 LLM 的精简 Schema 描述，
    只包含与查询相关的表和列，大幅减少 Token 消耗。
    """

    def __init__(
        self,
        include_comments: bool = True,
        include_sample_values: bool = False,
        highlight_relevant_columns: bool = True,
    ):
        """
        初始化 Schema 剪枝器

        Args:
            include_comments: 是否包含注释
            include_sample_values: 是否包含示例值
            highlight_relevant_columns: 是否高亮相关列
        """
        self.include_comments = include_comments
        self.include_sample_values = include_sample_values
        self.highlight_relevant_columns = highlight_relevant_columns

    def prune_schema(self, subgraph: Dict[str, Any]) -> Dict[str, Any]:
        """
        剪枝 Schema

        Args:
            subgraph: 子图信息

        Returns:
            精简的 Schema 信息
        """
        logger.info("开始剪枝 Schema...")

        pruned_schema = {
            "tables": [],
            "relationships": subgraph.get("relationships", []),
            "metadata": subgraph.get("metadata", {}),
        }

        highlighted_columns = {
            f"{col['table']}.{col['column']}": col
            for col in subgraph.get("highlighted_columns", [])
        }

        # 处理每张表
        for table in subgraph.get("tables", []):
            pruned_table = self._prune_table(table, highlighted_columns)
            pruned_schema["tables"].append(pruned_table)

        logger.info(f"Schema 剪枝完成，保留 {len(pruned_schema['tables'])} 张表")
        return pruned_schema

    def _prune_table(
        self, table: Dict[str, Any], highlighted_columns: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        剪枝单张表

        Args:
            table: 表信息
            highlighted_columns: 高亮列字典

        Returns:
            精简的表信息
        """
        pruned_table = {
            "name": table["name"],
            "comment": table.get("comment", "") if self.include_comments else "",
            "primary_keys": table.get("primary_keys", []),
            "columns": [],
        }

        # 处理列
        for column in table.get("columns", []):
            col_key = f"{table['name']}.{column['name']}"
            is_highlighted = col_key in highlighted_columns

            # 如果启用高亮，优先保留高亮列
            if self.highlight_relevant_columns:
                if is_highlighted or column.get("primary_key", False):
                    pruned_column = self._prune_column(column, is_highlighted)
                    pruned_table["columns"].append(pruned_column)
            else:
                # 保留所有列
                pruned_column = self._prune_column(column, is_highlighted)
                pruned_table["columns"].append(pruned_column)

        # 确保至少包含主键列
        if not pruned_table["columns"]:
            for column in table.get("columns", []):
                if column.get("primary_key", False):
                    pruned_column = self._prune_column(column, False)
                    pruned_table["columns"].append(pruned_column)

        return pruned_table

    def _prune_column(
        self, column: Dict[str, Any], is_highlighted: bool
    ) -> Dict[str, Any]:
        """
        剪枝单个列

        Args:
            column: 列信息
            is_highlighted: 是否高亮

        Returns:
            精简的列信息
        """
        pruned_column = {
            "name": column["name"],
            "type": column["type"],
            "nullable": column.get("nullable", True),
            "primary_key": column.get("primary_key", False),
            "comment": column.get("comment", "") if self.include_comments else "",
            "highlighted": is_highlighted,
        }

        return pruned_column

    def generate_ddl(self, pruned_schema: Dict[str, Any]) -> str:
        """
        生成 DDL 语句（用于 Prompt）

        Args:
            pruned_schema: 精简的 Schema

        Returns:
            DDL 字符串
        """
        return format_schema_for_prompt(pruned_schema)

    def generate_schema_summary(self, pruned_schema: Dict[str, Any]) -> str:
        """
        生成 Schema 摘要（简短描述）

        Args:
            pruned_schema: 精简的 Schema

        Returns:
            摘要字符串
        """
        lines = []

        lines.append("## 数据库结构摘要")
        lines.append("")

        # 表概览
        lines.append("### 相关表:")
        for table in pruned_schema.get("tables", []):
            comment = table.get("comment", "")
            if comment:
                lines.append(f"- **{table['name']}**: {comment}")
            else:
                lines.append(f"- **{table['name']}**")

        lines.append("")

        # 关系概览
        if pruned_schema.get("relationships"):
            lines.append("### 表关系:")
            for rel in pruned_schema["relationships"]:
                lines.append(
                    f"- {rel['from_table']} → {rel['to_table']} "
                    f"({', '.join(rel['from_columns'])} → {', '.join(rel['to_columns'])})"
                )
            lines.append("")

        return "\n".join(lines)

    def generate_column_descriptions(self, pruned_schema: Dict[str, Any]) -> str:
        """
        生成列描述（用于帮助 LLM 理解字段含义）

        Args:
            pruned_schema: 精简的 Schema

        Returns:
            列描述字符串
        """
        lines = []

        lines.append("## 重要字段说明")
        lines.append("")

        for table in pruned_schema.get("tables", []):
            table_name = table["name"]

            # 只描述高亮的列
            highlighted_cols = [
                col for col in table.get("columns", []) if col.get("highlighted", False)
            ]

            if highlighted_cols:
                lines.append(f"### {table_name}")
                for col in highlighted_cols:
                    comment = col.get("comment", "")
                    if comment:
                        lines.append(f"- **{col['name']}** ({col['type']}): {comment}")
                    else:
                        lines.append(f"- **{col['name']}** ({col['type']})")
                lines.append("")

        return "\n".join(lines)

    def calculate_token_savings(
        self, original_table_count: int, pruned_table_count: int
    ) -> Dict[str, Any]:
        """
        计算 Token 节省估算

        Args:
            original_table_count: 原始表数量
            pruned_table_count: 剪枝后表数量

        Returns:
            节省信息
        """
        # 假设每张表平均 200 tokens（包含列定义）
        avg_tokens_per_table = 200

        original_tokens = original_table_count * avg_tokens_per_table
        pruned_tokens = pruned_table_count * avg_tokens_per_table

        saved_tokens = original_tokens - pruned_tokens
        saved_percentage = (
            (saved_tokens / original_tokens * 100) if original_tokens > 0 else 0
        )

        return {
            "original_tokens": original_tokens,
            "pruned_tokens": pruned_tokens,
            "saved_tokens": saved_tokens,
            "saved_percentage": round(saved_percentage, 2),
        }

    def generate_join_hints(self, pruned_schema: Dict[str, Any]) -> List[str]:
        """
        生成 JOIN 提示（帮助 LLM 理解如何连接表）

        Args:
            pruned_schema: 精简的 Schema

        Returns:
            JOIN 提示列表
        """
        hints = []

        for rel in pruned_schema.get("relationships", []):
            from_table = rel["from_table"]
            to_table = rel["to_table"]
            from_cols = ", ".join(rel["from_columns"])
            to_cols = ", ".join(rel["to_columns"])

            hint = (
                f"To join {from_table} with {to_table}: "
                f"{from_table}.{from_cols} = {to_table}.{to_cols}"
            )
            hints.append(hint)

        return hints

    def create_prompt_context(
        self, pruned_schema: Dict[str, Any], user_question: str
    ) -> str:
        """
        创建完整的 Prompt 上下文

        Args:
            pruned_schema: 精简的 Schema
            user_question: 用户问题

        Returns:
            Prompt 上下文字符串
        """
        sections = []

        # 1. Schema 摘要
        sections.append(self.generate_schema_summary(pruned_schema))

        # 2. DDL 定义
        sections.append("## 数据库表结构")
        sections.append("```sql")
        sections.append(self.generate_ddl(pruned_schema))
        sections.append("```")
        sections.append("")

        # 3. 列描述
        if self.include_comments:
            sections.append(self.generate_column_descriptions(pruned_schema))

        # 4. JOIN 提示
        join_hints = self.generate_join_hints(pruned_schema)
        if join_hints:
            sections.append("## JOIN 提示")
            for hint in join_hints:
                sections.append(f"- {hint}")
            sections.append("")

        # 5. 用户问题
        sections.append("## 用户问题")
        sections.append(f"{user_question}")
        sections.append("")

        return "\n".join(sections)
