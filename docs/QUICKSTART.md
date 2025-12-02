# 快速开始指南

本指南将帮助您快速上手 Graph-Enhanced Text2SQL 系统。

## 前置要求

- Python 3.9+
- Neo4j 5.x（图数据库）
- PostgreSQL/MySQL（业务数据库）
- OpenAI 或 Anthropic API Key

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd graph_schema_rag
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 下载 Spacy 模型

```bash
# 中文模型
python -m spacy download zh_core_web_sm

# 英文模型（可选）
python -m spacy download en_core_web_sm
```

### 4. 启动 Neo4j

使用 Docker 快速启动：

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.15
```

访问 http://localhost:7474 验证 Neo4j 是否正常运行。

### 5. 配置系统

复制配置文件模板：

```bash
cp config.example.yaml config.yaml
```

编辑 [`config.yaml`](../config.yaml:1)，配置以下内容：

```yaml
# Neo4j 配置
neo4j:
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "password"

# 业务数据库配置
source_database:
  type: "postgresql"  # 或 mysql
  host: "localhost"
  port: 5432
  database: "your_database"
  username: "your_username"
  password: "your_password"

# LLM 配置
llm:
  provider: "openai"  # 或 anthropic
  openai:
    api_key: "sk-your-api-key"
    model: "gpt-4-turbo-preview"
```

## 首次使用

### 步骤 1: 构建知识图谱

```python
from src.text2sql import GraphEnhancedText2SQL

# 初始化系统
text2sql = GraphEnhancedText2SQL()

# 构建知识图谱（首次运行必须执行）
stats = text2sql.build_knowledge_graph(clear_existing=True)

print(f"图谱构建完成: {stats}")
```

这将从您的业务数据库中提取表结构，并在 Neo4j 中构建知识图谱。

### 步骤 2: 执行查询

```python
# 简单查询
question = "查询所有用户的姓名和邮箱"
sql = text2sql.generate_sql(question)
print(sql)

# 复杂查询
question = "查询上个月北京地区销售额超过1万元的订单数量"
sql = text2sql.generate_sql(question)
print(sql)

# 执行并获取结果
results, columns = text2sql.execute(question)
print(results)
```

## 运行示例

我们提供了完整的示例代码：

```bash
python examples/basic_usage.py
```

选择要运行的示例：

1. **基础查询** - 简单的单表查询
2. **复杂查询** - 多表 JOIN 和业务概念
3. **执行查询** - 生成并执行 SQL
4. **构建图谱** - 手动构建知识图谱
5. **添加业务概念** - 自定义业务概念
6. **系统统计** - 查看图谱统计信息

## 核心功能

### 1. 基础查询

```python
from src.text2sql import GraphEnhancedText2SQL

text2sql = GraphEnhancedText2SQL()

# 生成 SQL
sql = text2sql.generate_sql("查询所有用户")
print(sql)
# 输出: SELECT * FROM users;
```

### 2. 业务概念映射

系统支持将业务术语映射到数据库字段。编辑 [`data/concepts.yaml`](../data/concepts.yaml:1)：

```yaml
concepts:
  - name: 高价值客户
    description: VIP等级大于3的客户
    related_tables: [customers]
    related_columns:
      - table: customers
        column: vip_level
    synonyms: [VIP客户, 重要客户]
```

使用业务概念查询：

```python
sql = text2sql.generate_sql("统计高价值客户数量")
# 系统会自动理解"高价值客户"的含义
```

### 3. 同义词处理

编辑 [`data/synonyms.yaml`](../data/synonyms.yaml:1) 添加同义词：

```yaml
客户: [用户, 买家, customer, user]
订单: [交易, 购买记录, order]
```

现在可以使用不同表达方式：

```python
# 这三个问题会生成相同的 SQL
text2sql.generate_sql("查询所有客户")
text2sql.generate_sql("查询所有用户")
text2sql.generate_sql("查询所有买家")
```

### 4. 动态添加业务概念

```python
text2sql.add_business_concept(
    name="活跃用户",
    description="最近30天有登录记录的用户",
    related_columns=[
        {'table': 'users', 'column': 'last_login_time'}
    ],
    synonyms=["在线用户", "常用用户"]
)

# 现在可以使用这个概念
sql = text2sql.generate_sql("统计活跃用户数量")
```

## 工作原理

系统的处理流程：

```
用户问题
    ↓
1. 关键词提取 (KeywordExtractor)
    ↓
2. 实体链接 (EntityMatcher)
    ↓
3. 图谱检索 (SubgraphRetriever)
    ↓
4. Schema 剪枝 (SchemaPruner)
    ↓
5. Prompt 构建 (PromptBuilder)
    ↓
6. LLM 生成 (SQLGenerator)
    ↓
生成的 SQL
```

## 性能优化

### Token 节省

相比直接将所有表结构发送给 LLM，本系统通过 Schema 剪枝可以：

- ✅ 减少 40%-60% 的 Token 消耗
- ✅ 提高 SQL 生成准确率
- ✅ 支持大规模数据库（100+ 张表）

### 缓存机制

系统自动缓存查询结果：

```python
# 首次查询
sql = text2sql.generate_sql("查询用户数量")  # 调用 LLM

# 相同问题再次查询
sql = text2sql.generate_sql("查询用户数量")  # 从缓存返回
```

## 故障排查

### 问题 1: 连接 Neo4j 失败

**错误**: `Failed to establish connection to Neo4j`

**解决方案**:
1. 确认 Neo4j 正在运行：`docker ps | grep neo4j`
2. 检查端口是否正确：默认 7687
3. 验证用户名密码

### 问题 2: 找不到相关表

**错误**: `未找到相关表，无法生成 SQL`

**解决方案**:
1. 确认已运行 `build_knowledge_graph()`
2. 检查问题中的表名/列名是否存在
3. 添加同义词映射

### 问题 3: SQL 生成失败

**错误**: `SQL 生成失败`

**解决方案**:
1. 检查 LLM API Key 是否正确
2. 验证网络连接
3. 查看日志文件：`logs/text2sql.log`

## 下一步

- 📖 阅读 [完整文档](./ARCHITECTURE.md)
- 🔧 查看 [高级配置](./CONFIGURATION.md)
- 💡 浏览 [最佳实践](./BEST_PRACTICES.md)
- 🐛 提交 [Issue](https://github.com/your-repo/issues)

## 支持

如有问题，请：

1. 查看文档
2. 搜索已有 Issue
3. 提交新 Issue 并提供：
   - 错误信息
   - 配置文件
   - 日志文件

---

**提示**: 建议在测试环境中先运行系统，熟悉后再接入生产数据库。