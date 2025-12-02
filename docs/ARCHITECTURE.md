# 系统架构文档

本文档详细描述 Graph-Enhanced Text2SQL 系统的技术架构。

## 系统概述

Graph-Enhanced Text2SQL 是一个基于知识图谱增强的自然语言到SQL转换系统。通过将数据库结构映射为图谱，系统能够精准定位相关表和列，大幅降低 LLM Token 消耗并提高 SQL 生成准确率。

### 核心优势

1. **Schema 剪枝**: 只向 LLM 发送相关表结构，减少 40%-60% Token 消耗
2. **业务语义理解**: 支持业务概念映射，理解"高价值客户"等术语
3. **可扩展性**: 支持 100+ 张表的大规模数据库
4. **高准确率**: 通过图遍历精确定位 JOIN 路径

## 整体架构

系统采用分层架构设计，包含接口层、业务逻辑层和数据访问层。

### 核心流程

```
用户问题 → 实体链接 → 图谱检索 → Schema剪枝 → LLM生成 → SQL输出
```

## 核心模块

### 1. 实体链接模块 (Entity Linking)

负责从自然语言中提取实体并链接到图谱节点。

- **KeywordExtractor**: 提取关键词（支持Spacy/正则/混合模式）
- **EntityMatcher**: 将关键词匹配到表、列、概念节点

### 2. 图谱查询模块 (Graph Query)

负责从知识图谱中检索相关子图。

- **SubgraphRetriever**: 通过图遍历检索相关表
- **SchemaPruner**: 剪枝并格式化Schema为LLM友好格式

### 3. LLM集成模块 (LLM Integration)

负责构建Prompt并调用LLM生成SQL。

- **PromptBuilder**: 构建结构化Prompt
- **SQLGenerator**: 调用LLM并处理响应

### 4. 图谱构建模块 (Graph Builder)

负责构建知识图谱。

- **SchemaParser**: 解析数据库Schema
- **GraphConstructor**: 构建Neo4j图谱
- **ConceptExtractor**: 提取业务概念

## 关键技术

### 图遍历算法

使用广度优先搜索(BFS)在图中查找相关表，通过外键关系连接。

### Token优化

通过Schema剪枝，将100+张表压缩到5-10张相关表，大幅减少Token消耗。

### 缓存机制

自动缓存查询结果，提高响应速度。

## 技术栈

- **图数据库**: Neo4j 5.x
- **LLM框架**: LangChain
- **NLP**: Spacy
- **数据库**: SQLAlchemy (支持PostgreSQL/MySQL)

---

更多详情请参考源代码注释和快速开始指南。