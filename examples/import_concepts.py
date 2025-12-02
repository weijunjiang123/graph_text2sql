#!/usr/bin/env python
"""导入业务概念到Neo4j图谱"""

from src.database import Neo4jConnector
from src.config import get_config
from src.graph_builder.concept_extractor import ConceptExtractor
from src.graph_builder.graph_constructor import GraphConstructor
from loguru import logger

def main():
    """主函数"""
    # 加载配置
    config = get_config()
    
    # 连接Neo4j
    neo4j = Neo4jConnector(
        config.neo4j.uri,
        config.neo4j.username,
        config.neo4j.password,
        config.neo4j.database
    )
    
    # 初始化图谱构建器
    graph_constructor = GraphConstructor(neo4j)
    
    # 加载概念提取器
    concept_extractor = ConceptExtractor(
        concept_file=config.business_concepts.concept_definitions,
        synonym_file=config.business_concepts.synonym_dict
    )
    
    # 获取所有概念
    concepts = concept_extractor.get_all_concepts()
    
    logger.info(f"开始导入 {len(concepts)} 个业务概念...")
    
    # 导入每个概念
    for concept in concepts:
        try:
            graph_constructor.add_business_concept(
                concept_name=concept["name"],
                description=concept["description"],
                related_columns=concept["related_columns"],
                synonyms=concept.get("synonyms", [])
            )
            logger.info(f"✓ 已导入: {concept['name']}")
        except Exception as e:
            logger.error(f"✗ 导入失败 {concept['name']}: {e}")
    
    # 获取统计信息
    stats = graph_constructor.get_graph_statistics()
    
    logger.info("=" * 50)
    logger.info("图谱统计信息:")
    logger.info(f"  Table节点: {stats.get('table_count', 0)}")
    logger.info(f"  Column节点: {stats.get('column_count', 0)}")
    logger.info(f"  Concept节点: {stats.get('concept_count', 0)}")
    logger.info(f"  FOREIGN_KEY关系: {stats.get('foreign_key_count', 0)}")
    logger.info("=" * 50)
    
    neo4j.close()
    logger.info("概念导入完成！")

if __name__ == "__main__":
    main()