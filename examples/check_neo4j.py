#!/usr/bin/env python
"""检查Neo4j图谱数据"""

from src.database import Neo4jConnector
from src.config import get_config

config = get_config()
neo4j = Neo4jConnector(
    config.neo4j.uri, 
    config.neo4j.username, 
    config.neo4j.password, 
    config.neo4j.database
)

# 检查各类节点和关系数量
queries = {
    "Table节点": "MATCH (t:Table) RETURN count(t) as count",
    "Column节点": "MATCH (c:Column) RETURN count(c) as count",
    "Concept节点": "MATCH (n:Concept) RETURN count(n) as count",
    "Value节点": "MATCH (v:Value) RETURN count(v) as count",
    "FOREIGN_KEY关系": "MATCH ()-[r:FOREIGN_KEY]->() RETURN count(r) as count",
    "HAS_COLUMN关系": "MATCH ()-[r:HAS_COLUMN]->() RETURN count(r) as count",
}

print("=" * 50)
print("Neo4j 图谱数据统计")
print("=" * 50)

for name, query in queries.items():
    try:
        result = neo4j.execute_query(query)
        count = result[0]["count"] if result else 0
        print(f"{name}: {count}")
    except Exception as e:
        print(f"{name}: 查询失败 - {e}")

# 如果有Table节点，显示示例
tables_query = "MATCH (t:Table) RETURN t.name as name LIMIT 5"
tables = neo4j.execute_query(tables_query)
if tables:
    print("\n示例表名:")
    for t in tables:
        print(f"  - {t['name']}")

neo4j.close()