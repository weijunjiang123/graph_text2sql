# 项目执行指南

本指南将详细说明如何从零开始运行 Graph-Enhanced Text2SQL 项目。

## 📋 前置要求检查清单

在开始之前，请确保以下环境已准备好：

- [ ] Python 3.9 或更高版本
- [ ] Neo4j 5.x 数据库
- [ ] PostgreSQL 或 MySQL 数据库（业务数据库）
- [ ] LLM API 访问权限（OpenAI/Anthropic/OpenAI Compatible）

## 🚀 完整安装步骤

### 步骤 1: 安装 Python 依赖

```bash
# 进入项目目录
cd graph_schema_rag

# 创建虚拟环境（推荐）
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 Spacy 中文模型
python -m spacy download zh_core_web_sm

# 如需英文支持
python -m spacy download en_core_web_sm
```

### 步骤 2: 启动 Neo4j 数据库

#### 使用 Docker（推荐）

```bash
# 拉取并启动 Neo4j
docker run -d \
  --name neo4j-text2sql \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  -v neo4j_data:/data \
  neo4j:5.15

# 等待启动完成（约10-15秒）
docker logs -f neo4j-text2sql
```

#### 验证 Neo4j

访问 http://localhost:7474 并使用以下凭据登录：
- 用户名: `neo4j`
- 密码: `your_password`

### 步骤 3: 配置系统

```bash
# 复制配置模板
cp config.example.yaml config.yaml

# 编辑配置文件
# Windows: notepad config.yaml
# Linux/Mac: nano config.yaml
```

**必须配置的项目：**

```yaml
# Neo4j 配置
neo4j:
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "your_password"  # 改为你的密码

# 业务数据库配置
source_database:
  type: "postgresql"  # 或 mysql
  host: "localhost"
  port: 5432
  database: "your_database_name"  # 改为你的数据库名
  username: "your_username"       # 改为你的用户名
  password: "your_password"       # 改为你的密码

# LLM 配置
llm:
  provider: "openai_compatible"  # 使用 OpenAI Compatible API
  
  openai_compatible:
    api_key: "sk-dummy-key"
    base_url: "http://localhost:8000/v1"  # 改为你的 API 地址
    model: "your-model-name"               # 改为你的模型名
    temperature: 0.0
    max_tokens: 2000
```

### 步骤 4: 构建知识图谱

创建一个简单的初始化脚本 `init_graph.py`：

```python
from src.text2sql import GraphEnhancedText2SQL
from src.config import Config

# 加载配置
config = Config.from_yaml("config.yaml")

# 初始化系统
print("正在初始化系统...")
text2sql = GraphEnhancedText2SQL(config=config)

# 构建知识图谱
print("\n开始构建知识图谱...")
print("这可能需要几分钟时间，取决于数据库大小...")

stats = text2sql.build_knowledge_graph(clear_existing=True)

print("\n✅ 知识图谱构建完成！")
print(f"📊 统计信息:")
print(f"  - 表节点数: {stats.get('table_count', 0)}")
print(f"  - 列节点数: {stats.get('column_count', 0)}")
print(f"  - 外键关系数: {stats.get('foreign_key_count', 0)}")
print(f"  - 概念节点数: {stats.get('concept_count', 0)}")

text2sql.close()
```

运行初始化：

```bash
python init_graph.py
```

### 步骤 5: 测试查询

创建测试脚本 `test_query.py`：

```python
from src.text2sql import GraphEnhancedText2SQL
from src.config import Config

# 加载配置
config = Config.from_yaml("config.yaml")

# 初始化系统
text2sql = GraphEnhancedText2SQL(config=config)

# 测试查询
questions = [
    "查询所有用户",
    "统计每个城市的用户数量",
    "查询上个月的订单总数"
]

print("🔍 开始测试查询...\n")

for i, question in enumerate(questions, 1):
    print(f"问题 {i}: {question}")
    
    try:
        result = text2sql.process_question(question)
        
        if result['success']:
            print(f"✅ SQL: {result['sql']}")
            print(f"📊 使用了 {result['metadata']['subgraph']['table_count']} 张表")
        else:
            print(f"❌ 错误: {result['error']}")
    
    except Exception as e:
        print(f"❌ 异常: {e}")
    
    print("-" * 60)

text2sql.close()
```

运行测试：

```bash
python test_query.py
```

## 📝 使用示例程序

运行完整的示例程序：

```bash
python examples/basic_usage.py
```

这将提供一个交互式菜单，让你选择不同的示例：

```
可用示例:
1. 基础查询
2. 复杂查询
3. 执行查询
4. 构建图谱
5. 添加业务概念
6. 系统统计

选择要运行的示例 (1-6, 或 'all' 运行全部):
```

## 🔧 常见问题排查

### 问题 1: 无法连接 Neo4j

**错误信息**: `Failed to establish connection`

**解决方案**:
```bash
# 检查 Neo4j 是否运行
docker ps | grep neo4j

# 如果没有运行，启动它
docker start neo4j-text2sql

# 检查日志
docker logs neo4j-text2sql
```

### 问题 2: 无法连接业务数据库

**错误信息**: `Can't connect to database`

**解决方案**:
1. 确认数据库正在运行
2. 检查 `config.yaml` 中的连接信息
3. 测试数据库连接：

```python
from src.database import DatabaseConnector
from src.config import Config

config = Config.from_yaml("config.yaml")
db = DatabaseConnector(config.source_database)
tables = db.get_all_tables()
print(f"发现 {len(tables)} 张表")
```

### 问题 3: LLM API 调用失败

**错误信息**: `API call failed`

**解决方案**:
1. 检查 API 地址是否正确
2. 确认 API 服务正在运行
3. 测试 API 连接：

```bash
# 测试 OpenAI Compatible API
curl http://localhost:8000/v1/models
```

### 问题 4: 找不到 Spacy 模型

**错误信息**: `Can't find model 'zh_core_web_sm'`

**解决方案**:
```bash
# 重新下载模型
python -m spacy download zh_core_web_sm

# 验证安装
python -c "import spacy; nlp = spacy.load('zh_core_web_sm'); print('OK')"
```

## 🎯 快速启动脚本

创建 `quick_start.py` 用于一键启动：

```python
#!/usr/bin/env python3
"""
快速启动脚本
"""
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """检查 Python 版本"""
    if sys.version_info < (3, 9):
        print("❌ 需要 Python 3.9 或更高版本")
        sys.exit(1)
    print("✅ Python 版本检查通过")

def install_dependencies():
    """安装依赖"""
    print("\n📦 安装依赖...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.run([sys.executable, "-m", "spacy", "download", "zh_core_web_sm"])
    print("✅ 依赖安装完成")

def check_config():
    """检查配置文件"""
    if not Path("config.yaml").exists():
        print("\n⚠️  配置文件不存在")
        print("正在复制配置模板...")
        import shutil
        shutil.copy("config.example.yaml", "config.yaml")
        print("✅ 已创建 config.yaml，请编辑此文件配置数据库和 LLM")
        print("📝 主要配置项:")
        print("  1. Neo4j 连接信息")
        print("  2. 业务数据库连接信息")
        print("  3. LLM API 配置")
        return False
    print("✅ 配置文件存在")
    return True

def main():
    """主函数"""
    print("🚀 Graph-Enhanced Text2SQL 快速启动\n")
    
    # 检查 Python 版本
    check_python_version()
    
    # 询问是否安装依赖
    install = input("\n是否安装/更新依赖? (y/n): ").lower()
    if install == 'y':
        install_dependencies()
    
    # 检查配置
    if not check_config():
        print("\n请配置 config.yaml 后重新运行此脚本")
        return
    
    # 询问是否构建图谱
    build = input("\n是否构建知识图谱? (y/n): ").lower()
    if build == 'y':
        from src.text2sql import GraphEnhancedText2SQL
        from src.config import Config
        
        config = Config.from_yaml("config.yaml")
        text2sql = GraphEnhancedText2SQL(config=config)
        
        print("\n正在构建知识图谱...")
        stats = text2sql.build_knowledge_graph(clear_existing=True)
        
        print("\n✅ 构建完成！")
        print(f"📊 统计: {stats}")
        
        text2sql.close()
    
    print("\n✅ 系统已就绪！")
    print("\n📚 下一步:")
    print("  1. 运行示例: python examples/basic_usage.py")
    print("  2. 运行测试: python tests/test_basic.py")
    print("  3. 查看文档: docs/QUICKSTART.md")

if __name__ == "__main__":
    main()
```

运行快速启动：

```bash
python quick_start.py
```

## 📊 验证安装

运行以下命令验证所有组件：

```bash
# 测试基本工具函数
python tests/test_basic.py

# 检查系统状态
python -c "from src.text2sql import GraphEnhancedText2SQL; print('✅ 系统可用')"
```

## 🎉 完成！

现在你可以开始使用系统了。建议从简单的查询开始测试，逐步尝试复杂的业务查询。

如有问题，请查看：
- 📖 [快速开始指南](QUICKSTART.md)
- 🏗️ [架构文档](ARCHITECTURE.md)
- 💻 [示例代码](../examples/basic_usage.py)