# Web 界面使用指南

本指南介绍如何使用基于 Streamlit 的 Web 界面。

## 🚀 启动 Web 界面

### 方法 1: 直接启动

```bash
streamlit run app.py
```

### 方法 2: 指定端口

```bash
streamlit run app.py --server.port 8501
```

### 方法 3: 后台运行

```bash
# Linux/Mac
nohup streamlit run app.py &

# Windows (使用 PowerShell)
Start-Process streamlit -ArgumentList "run","app.py" -WindowStyle Hidden
```

启动后，浏览器会自动打开，或手动访问：http://localhost:8501

## 📱 界面功能

### 1. 查询界面

#### 主要功能

- **预设示例查询**: 快速选择常用查询模板
- **自定义查询**: 输入任意自然语言问题
- **生成 SQL**: 将自然语言转换为 SQL
- **执行查询**: 直接运行生成的 SQL 并显示结果
- **下载结果**: 将查询结果导出为 CSV 文件

#### 使用步骤

1. **选择或输入查询**
   ```
   示例: "查询上个月北京地区的高价值客户数量"
   ```

2. **点击"生成 SQL"**
   - 系统会分析问题
   - 从知识图谱中检索相关表
   - 调用 LLM 生成 SQL

3. **查看生成的 SQL**
   ```sql
   SELECT COUNT(DISTINCT c.customer_id)
   FROM customers c
   JOIN orders o ON c.customer_id = o.customer_id
   WHERE c.city = '北京'
     AND o.created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
     AND (c.vip_level > 3 OR o.total_amount > 10000)
   ```

4. **执行查询（可选）**
   - 点击"执行查询"按钮
   - 查看结果表格
   - 下载 CSV 文件

#### 元数据信息

启用"显示元数据"后，可以看到：

- **使用的表数量**: 系统选择了多少张表
- **尝试次数**: LLM 生成尝试的次数
- **关系数量**: 表之间的连接数
- **匹配的实体**: 从问题中识别的实体

### 2. 图谱管理

#### 统计信息

查看知识图谱的统计数据：

- **表节点数**: 数据库中的表数量
- **列节点数**: 所有列的总数
- **概念节点数**: 业务概念数量
- **外键关系数**: 表之间的关系数

#### 重建图谱

当数据库结构变更时，需要重建知识图谱：

1. 切换到"重建"标签
2. 点击"开始重建"按钮
3. 等待完成（可能需要几分钟）

⚠️ **注意**: 重建会清除现有图谱，包括手动添加的业务概念。

### 3. 侧边栏配置

#### 系统状态

- **系统就绪状态**: 显示系统是否正常初始化
- **图谱统计**: 实时显示图谱规模

#### 查询选项

- **最大结果数**: 限制返回的记录数（10-1000）
- **显示元数据**: 是否显示查询的详细信息
- **使用缓存**: 是否启用查询缓存

## 💡 使用技巧

### 1. 查询优化

**好的查询示例:**
```
✅ "查询上个月北京地区的订单数量"
✅ "统计每个城市的用户数量，按降序排列"
✅ "查询高价值客户的平均购买金额"
```

**需要改进的查询:**
```
❌ "给我看看数据"  (太模糊)
❌ "帮我分析一下"  (缺少具体目标)
```

### 2. 利用预设查询

预设查询经过优化，可以作为模板：

1. 选择相似的预设查询
2. 修改其中的条件
3. 生成 SQL

### 3. 查看元数据

元数据可以帮助你理解：

- 系统是如何理解你的问题的
- 选择了哪些表和列
- 是否需要优化查询表述

### 4. 结果导出

查询结果可以导出为 CSV：

1. 执行查询
2. 点击"下载 CSV"
3. 文件自动命名为 `result_时间戳.csv`

## 🔧 故障排查

### 问题 1: Web 界面无法启动

**错误**: `ModuleNotFoundError: No module named 'streamlit'`

**解决**:
```bash
pip install streamlit plotly
```

### 问题 2: 系统初始化失败

**症状**: 页面显示"系统初始化失败"

**解决**:
1. 检查 `config.yaml` 是否存在
2. 确认 Neo4j 正在运行
3. 确认业务数据库可访问
4. 运行: `python quick_start.py`

### 问题 3: SQL 生成失败

**可能原因**:
- LLM API 不可用
- 知识图谱未构建
- 问题表述不清

**解决**:
1. 检查 LLM API 配置
2. 重建知识图谱
3. 尝试更清晰的问题表述

### 问题 4: 查询执行超时

**解决**:
1. 减少返回结果数量
2. 优化数据库查询
3. 添加适当的索引

## ⚙️ 配置选项

### 自定义端口

```bash
streamlit run app.py --server.port 8080
```

### 禁用自动打开浏览器

```bash
streamlit run app.py --server.headless true
```

### 配置服务器地址

```bash
streamlit run app.py --server.address 0.0.0.0
```

### 配置文件

创建 `.streamlit/config.toml`:

```toml
[server]
port = 8501
headless = false
enableCORS = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#667eea"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"
```

## 📊 性能建议

### 1. 缓存使用

- 开启缓存可加快重复查询
- 缓存会自动过期
- 可在图谱管理中手动清除

### 2. 结果限制

- 大数据量查询时，限制返回结果数
- 使用分页或筛选条件

### 3. 定期维护

- 定期重建知识图谱（当数据库结构变更时）
- 清理缓存
- 检查系统统计

## 🌐 远程访问

### 使用 ngrok

```bash
# 安装 ngrok
# 启动 streamlit
streamlit run app.py

# 在另一个终端
ngrok http 8501
```

### 使用 SSH 隧道

```bash
ssh -L 8501:localhost:8501 user@server
```

然后访问: http://localhost:8501

## 🔒 安全建议

1. **不要暴露到公网**: Streamlit 默认不包含认证
2. **使用反向代理**: 通过 Nginx/Apache 添加认证
3. **限制访问**: 使用防火墙规则
4. **定期更新**: 保持依赖包最新

## 📚 更多资源

- [Streamlit 文档](https://docs.streamlit.io)
- [项目文档](./QUICKSTART.md)
- [架构说明](./ARCHITECTURE.md)

---

如有问题，请查看[执行指南](./EXECUTION_GUIDE.md)或提交 Issue。