#!/usr/bin/env python3
"""
快速启动脚本
Graph-Enhanced Text2SQL 系统一键部署工具
"""
import sys
import subprocess
from pathlib import Path


def print_header():
    """打印标题"""
    print("\n" + "=" * 60)
    print("  Graph-Enhanced Text2SQL 快速启动")
    print("=" * 60 + "\n")


def check_python_version():
    """检查 Python 版本"""
    print("🔍 检查 Python 版本...")
    if sys.version_info < (3, 9):
        print("❌ 需要 Python 3.9 或更高版本")
        print(f"   当前版本: {sys.version}")
        sys.exit(1)
    print(f"✅ Python 版本检查通过 ({sys.version.split()[0]})")


def install_dependencies():
    """安装依赖"""
    print("\n📦 安装 Python 依赖...")
    print("   这可能需要几分钟...")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
            capture_output=True
        )
        print("✅ 依赖安装完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False
    
    # 安装 Spacy 模型
    print("\n📦 安装 Spacy 中文模型...")
    try:
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", "zh_core_web_sm"],
            check=True,
            capture_output=True
        )
        print("✅ Spacy 模型安装完成")
    except subprocess.CalledProcessError:
        print("⚠️  Spacy 模型安装失败（可能已安装）")
    
    return True


def check_config():
    """检查配置文件"""
    print("\n🔍 检查配置文件...")
    
    if not Path("config.yaml").exists():
        print("⚠️  配置文件不存在")
        print("   正在从模板创建 config.yaml...")
        
        import shutil
        shutil.copy("config.example.yaml", "config.yaml")
        
        print("✅ 已创建 config.yaml")
        print("\n📝 请编辑 config.yaml 配置以下信息:")
        print("   1. Neo4j 数据库连接")
        print("      - uri: bolt://localhost:7687")
        print("      - username: neo4j")
        print("      - password: 你的密码")
        print("\n   2. 业务数据库连接")
        print("      - type: postgresql 或 mysql")
        print("      - host, port, database, username, password")
        print("\n   3. LLM API 配置")
        print("      - provider: openai_compatible")
        print("      - base_url: 你的 API 地址")
        print("      - model: 你的模型名称")
        
        return False
    
    print("✅ 配置文件存在")
    return True


def test_neo4j_connection():
    """测试 Neo4j 连接"""
    print("\n🔍 测试 Neo4j 连接...")
    
    try:
        from src.config import Config
        from src.database import Neo4jConnector
        
        config = Config.from_yaml("config.yaml")
        neo4j = Neo4jConnector(
            uri=config.neo4j.uri,
            username=config.neo4j.username,
            password=config.neo4j.password,
            database=config.neo4j.database
        )
        
        # 测试查询
        result = neo4j.execute_query("RETURN 1 as test")
        neo4j.close()
        
        print("✅ Neo4j 连接成功")
        return True
    
    except Exception as e:
        print(f"❌ Neo4j 连接失败: {e}")
        print("\n💡 提示:")
        print("   - 确认 Neo4j 正在运行")
        print("   - 检查 config.yaml 中的连接信息")
        print("   - 使用 Docker 启动: docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5.15")
        return False


def test_database_connection():
    """测试业务数据库连接"""
    print("\n🔍 测试业务数据库连接...")
    
    try:
        from src.config import Config
        from src.database import DatabaseConnector
        
        config = Config.from_yaml("config.yaml")
        db = DatabaseConnector(config.source_database)
        tables = db.get_all_tables()
        db.close()
        
        print(f"✅ 数据库连接成功 (发现 {len(tables)} 张表)")
        return True
    
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("\n💡 提示:")
        print("   - 确认数据库正在运行")
        print("   - 检查 config.yaml 中的连接信息")
        return False


def build_knowledge_graph():
    """构建知识图谱"""
    print("\n🏗️  构建知识图谱...")
    print("   这可能需要几分钟，取决于数据库大小...")
    
    try:
        from src.text2sql import GraphEnhancedText2SQL
        from src.config import Config
        
        config = Config.from_yaml("config.yaml")
        text2sql = GraphEnhancedText2SQL(config=config)
        
        stats = text2sql.build_knowledge_graph(clear_existing=True)
        
        print("\n✅ 知识图谱构建完成！")
        print(f"\n📊 统计信息:")
        print(f"   - 表节点: {stats.get('table_count', 0)}")
        print(f"   - 列节点: {stats.get('column_count', 0)}")
        print(f"   - 外键关系: {stats.get('foreign_key_count', 0)}")
        print(f"   - 概念节点: {stats.get('concept_count', 0)}")
        
        text2sql.close()
        return True
    
    except Exception as e:
        print(f"❌ 知识图谱构建失败: {e}")
        return False


def run_test_query():
    """运行测试查询"""
    print("\n🧪 运行测试查询...")
    
    try:
        from src.text2sql import GraphEnhancedText2SQL
        from src.config import Config
        
        config = Config.from_yaml("config.yaml")
        text2sql = GraphEnhancedText2SQL(config=config)
        
        # 简单测试查询
        test_question = "查询所有表"
        print(f"\n   问题: {test_question}")
        
        result = text2sql.process_question(test_question)
        
        if result['success']:
            print(f"   ✅ SQL 生成成功")
            print(f"   SQL: {result['sql'][:100]}...")
        else:
            print(f"   ⚠️  SQL 生成失败: {result.get('error', 'Unknown')}")
        
        text2sql.close()
        return True
    
    except Exception as e:
        print(f"❌ 测试查询失败: {e}")
        return False


def main():
    """主函数"""
    print_header()
    
    # 1. 检查 Python 版本
    check_python_version()
    
    # 2. 询问是否安装依赖
    if input("\n📦 是否安装/更新依赖? (y/n): ").lower() == 'y':
        if not install_dependencies():
            print("\n❌ 依赖安装失败，请检查错误信息")
            return
    
    # 3. 检查配置文件
    if not check_config():
        print("\n⚠️  请先配置 config.yaml，然后重新运行此脚本")
        print("   运行命令: python quick_start.py")
        return
    
    print("\n" + "=" * 60)
    print("  开始系统验证")
    print("=" * 60)
    
    # 4. 测试 Neo4j 连接
    if not test_neo4j_connection():
        print("\n⚠️  Neo4j 连接失败，请修复后继续")
        if input("   是否继续? (y/n): ").lower() != 'y':
            return
    
    # 5. 测试数据库连接
    if not test_database_connection():
        print("\n⚠️  数据库连接失败，请修复后继续")
        if input("   是否继续? (y/n): ").lower() != 'y':
            return
    
    # 6. 构建知识图谱
    if input("\n🏗️  是否构建知识图谱? (y/n): ").lower() == 'y':
        if not build_knowledge_graph():
            print("\n❌ 知识图谱构建失败")
            return
    
    # 7. 运行测试查询
    if input("\n🧪 是否运行测试查询? (y/n): ").lower() == 'y':
        run_test_query()
    
    # 完成
    print("\n" + "=" * 60)
    print("  ✅ 系统已就绪！")
    print("=" * 60)
    
    print("\n📚 下一步:")
    print("   1. 运行示例程序:")
    print("      python examples/basic_usage.py")
    print("\n   2. 运行测试:")
    print("      python tests/test_basic.py")
    print("\n   3. 查看文档:")
    print("      - 快速开始: docs/QUICKSTART.md")
    print("      - 执行指南: docs/EXECUTION_GUIDE.md")
    print("      - 架构文档: docs/ARCHITECTURE.md")
    
    print("\n   4. 直接使用:")
    print("      python")
    print("      >>> from src.text2sql import GraphEnhancedText2SQL")
    print("      >>> text2sql = GraphEnhancedText2SQL()")
    print("      >>> sql = text2sql.generate_sql('你的问题')")
    
    print("\n🎉 祝使用愉快！\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()