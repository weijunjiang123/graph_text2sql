"""
基础使用示例
演示如何使用 Graph-Enhanced Text2SQL 系统
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.text2sql import GraphEnhancedText2SQL


def example_1_basic_query():
    """示例 1: 基础查询"""
    print("=" * 60)
    print("示例 1: 基础查询")
    print("=" * 60)

    # 初始化系统（使用配置文件）
    text2sql = GraphEnhancedText2SQL()

    # 简单查询
    question = "查询所有用户的姓名和邮箱"

    print(f"\n问题: {question}")
    print("\n生成的 SQL:")

    try:
        sql = text2sql.generate_sql(question)
        print(sql)
    except Exception as e:
        print(f"错误: {e}")

    text2sql.close()


def example_2_complex_query():
    """示例 2: 复杂查询（带业务逻辑）"""
    print("\n" + "=" * 60)
    print("示例 2: 复杂查询")
    print("=" * 60)

    text2sql = GraphEnhancedText2SQL()

    # 涉及多表 JOIN 和业务概念
    question = "查询上个月北京地区的高价值客户数量"

    print(f"\n问题: {question}")
    print("\n生成的 SQL:")

    try:
        # 返回详细上下文
        result = text2sql.generate_sql(question, return_context=True)

        if result["success"]:
            print(result["sql"])
            print(f"\n使用的表数量: {result['metadata']['subgraph']['table_count']}")
            print(f"尝试次数: {result['metadata']['attempts']}")
        else:
            print(f"失败: {result['error']}")

    except Exception as e:
        print(f"错误: {e}")

    text2sql.close()


def example_3_execute_query():
    """示例 3: 执行查询并获取结果"""
    print("\n" + "=" * 60)
    print("示例 3: 执行查询")
    print("=" * 60)

    text2sql = GraphEnhancedText2SQL()

    question = "统计每个城市的用户数量，按数量降序排列"

    print(f"\n问题: {question}")

    try:
        # 生成并执行 SQL
        results, columns = text2sql.execute(question, fetch_size=10)

        print(f"\n查询结果（前10条）:")
        print(f"列名: {columns}")

        for i, row in enumerate(results, 1):
            print(f"{i}. {row}")

    except Exception as e:
        print(f"错误: {e}")

    text2sql.close()


def example_4_build_graph():
    """示例 4: 构建知识图谱"""
    print("\n" + "=" * 60)
    print("示例 4: 构建知识图谱")
    print("=" * 60)

    # 初始化但不自动构建图谱
    text2sql = GraphEnhancedText2SQL(auto_build_graph=False)

    print("\n开始构建知识图谱...")

    try:
        # 手动构建（清除现有图谱）
        stats = text2sql.build_knowledge_graph(clear_existing=True)

        print("\n图谱统计:")
        print(f"表节点数: {stats.get('table_count', 0)}")
        print(f"列节点数: {stats.get('column_count', 0)}")
        print(f"外键关系数: {stats.get('foreign_key_count', 0)}")
        print(f"概念节点数: {stats.get('concept_count', 0)}")

    except Exception as e:
        print(f"错误: {e}")

    text2sql.close()


def example_5_add_business_concept():
    """示例 5: 添加业务概念"""
    print("\n" + "=" * 60)
    print("示例 5: 添加业务概念")
    print("=" * 60)

    text2sql = GraphEnhancedText2SQL()

    # 添加自定义业务概念
    text2sql.add_business_concept(
        name="超级VIP客户",
        description="VIP等级为5且累计消费超过50000元的客户",
        related_columns=[
            {"table": "customers", "column": "vip_level"},
            {"table": "customers", "column": "total_spent"},
        ],
        synonyms=["顶级客户", "钻石客户"],
    )

    print("\n已添加业务概念: 超级VIP客户")

    # 使用新概念查询
    question = "查询超级VIP客户的数量"
    print(f"\n问题: {question}")

    try:
        sql = text2sql.generate_sql(question)
        print(f"\n生成的 SQL:\n{sql}")
    except Exception as e:
        print(f"错误: {e}")

    text2sql.close()


def example_6_statistics():
    """示例 6: 获取系统统计"""
    print("\n" + "=" * 60)
    print("示例 6: 系统统计")
    print("=" * 60)

    text2sql = GraphEnhancedText2SQL()

    stats = text2sql.get_statistics()

    print("\n系统统计信息:")
    print(f"图谱节点:")
    print(f"  - 表: {stats['graph'].get('table_count', 0)}")
    print(f"  - 列: {stats['graph'].get('column_count', 0)}")
    print(f"  - 概念: {stats['graph'].get('concept_count', 0)}")
    print(f"图谱关系:")
    print(f"  - 外键: {stats['graph'].get('foreign_key_count', 0)}")
    print(f"缓存:")
    print(f"  - 条目数: {stats['cache']['size']}")

    text2sql.close()


def main():
    """运行所有示例"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Graph-Enhanced Text2SQL 示例" + " " * 18 + "║")
    print("╚" + "=" * 58 + "╝")

    examples = [
        ("基础查询", example_1_basic_query),
        ("复杂查询", example_2_complex_query),
        ("执行查询", example_3_execute_query),
        ("构建图谱", example_4_build_graph),
        ("添加业务概念", example_5_add_business_concept),
        ("系统统计", example_6_statistics),
    ]

    print("\n可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")

    print("\n" + "-" * 60)
    choice = input("\n选择要运行的示例 (1-6, 或 'all' 运行全部): ").strip().lower()

    if choice == "all":
        for name, func in examples:
            try:
                func()
            except Exception as e:
                print(f"\n示例 '{name}' 执行出错: {e}")
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        name, func = examples[int(choice) - 1]
        try:
            func()
        except Exception as e:
            print(f"\n示例 '{name}' 执行出错: {e}")
    else:
        print("无效的选择")

    print("\n" + "=" * 60)
    print("示例执行完成")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
