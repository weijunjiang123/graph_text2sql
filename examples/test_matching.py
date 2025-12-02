#!/usr/bin/env python
"""测试实体匹配功能"""

from src.database import Neo4jConnector
from src.config import get_config
from src.entity_linking.keyword_extractor import KeywordExtractor
from src.entity_linking.entity_matcher import EntityMatcher
from src.graph_builder.concept_extractor import ConceptExtractor
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
    
    # 初始化组件
    keyword_extractor = KeywordExtractor(method='regex')
    concept_extractor = ConceptExtractor(
        concept_file=config.business_concepts.concept_definitions,
        synonym_file=config.business_concepts.synonym_dict
    )
    entity_matcher = EntityMatcher(
        neo4j_connector=neo4j,
        keyword_extractor=keyword_extractor,
        concept_extractor=concept_extractor,
        fuzzy_threshold=config.entity_linking.matching.fuzzy_threshold
    )
    
    # 测试查询
    test_queries = [
        "各大类产品结构分析",
        "扫码记录统计",
        "查询数据权限信息"
    ]
    
    logger.info("=" * 60)
    logger.info("实体匹配测试")
    logger.info("=" * 60)
    
    for query in test_queries:
        logger.info(f"\n查询: {query}")
        logger.info("-" * 60)
        
        # 执行匹配
        matches = entity_matcher.match_entities(query)
        
        # 显示结果
        logger.info(f"关键词 ({len(matches['keywords'])}): {[k['text'] for k in matches['keywords'][:5]]}")
        logger.info(f"表 ({len(matches['tables'])}): {[t['name'] for t in matches['tables'][:3]]}")
        logger.info(f"列 ({len(matches['columns'])}): {[(c['table_name'], c['name']) for c in matches['columns'][:3]]}")
        logger.info(f"概念 ({len(matches['concepts'])}): {[c['concept']['name'] for c in matches['concepts'][:3]]}")
        
        # 获取相关表
        related_tables = entity_matcher.get_related_tables_from_matches(matches)
        logger.info(f"相关表: {related_tables}")
    
    neo4j.close()
    logger.info("\n" + "=" * 60)
    logger.info("测试完成！")

if __name__ == "__main__":
    main()