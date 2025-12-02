"""
Graph-Enhanced Text2SQL Web 界面
使用 Streamlit 构建的交互式前端
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from src.text2sql import GraphEnhancedText2SQL
from src.config import Config


# 页面配置
st.set_page_config(
    page_title="Graph-Enhanced Text2SQL",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_system():
    """初始化系统（缓存以避免重复加载）"""
    try:
        config = Config.from_yaml("config.yaml")
        text2sql = GraphEnhancedText2SQL(config=config)
        return text2sql, None
    except Exception as e:
        return None, str(e)


def display_header():
    """显示页面标题"""
    st.markdown('<h1 class="main-header">🔍 Graph-Enhanced Text2SQL</h1>', unsafe_allow_html=True)
    st.markdown("### 基于知识图谱增强的自然语言到SQL转换系统")
    st.markdown("---")


def sidebar_config():
    """侧边栏配置"""
    with st.sidebar:
        st.title("⚙️ 系统配置")
        
        # 系统状态
        st.subheader("📊 系统状态")
        text2sql, error = initialize_system()
        
        if text2sql:
            st.success("✅ 系统已就绪")
            
            try:
                stats = text2sql.get_statistics()
                st.metric("表节点", stats['graph'].get('table_count', 0))
                st.metric("列节点", stats['graph'].get('column_count', 0))
                st.metric("外键关系", stats['graph'].get('foreign_key_count', 0))
            except:
                pass
        else:
            st.error(f"❌ 初始化失败")
        
        st.markdown("---")
        
        # 查询选项
        st.subheader("🎯 查询选项")
        max_results = st.slider("最大结果数", 10, 1000, 100, 10)
        show_metadata = st.checkbox("显示元数据", value=True)
        use_cache = st.checkbox("使用缓存", value=True)
        
        return max_results, show_metadata, use_cache


def main_query_interface(text2sql, max_results, show_metadata, use_cache):
    """主查询界面"""
    
    st.subheader("💬 自然语言查询")
    
    # 预设示例
    example_queries = [
        "自定义查询...",
        "查询所有用户",
        "统计每个城市的用户数量",
        "查询上个月的订单总数",
    ]
    
    selected = st.selectbox("选择示例:", example_queries)
    
    if selected == "自定义查询...":
        user_question = st.text_area("输入问题:", height=100)
    else:
        user_question = st.text_area("编辑查询:", value=selected, height=100)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        query_button = st.button("🚀 生成 SQL", type="primary", use_container_width=True)
    
    with col2:
        execute_button = st.button("▶️ 执行查询", use_container_width=True)
    
    if query_button and user_question:
        process_query(text2sql, user_question, show_metadata, use_cache, False, max_results)
    
    if execute_button and user_question:
        process_query(text2sql, user_question, show_metadata, use_cache, True, max_results)


def process_query(text2sql, question, show_metadata, use_cache, execute, max_results):
    """处理查询"""
    with st.spinner('处理中...'):
        try:
            result = text2sql.process_question(question, use_cache=use_cache)
            
            if result['success']:
                st.success("✅ SQL 生成成功！")
                st.subheader("📝 生成的 SQL")
                st.code(result['sql'], language='sql')
                
                if show_metadata and 'metadata' in result:
                    with st.expander("📊 元数据"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("使用的表", result['metadata'].get('subgraph', {}).get('table_count', 0))
                        with col2:
                            st.metric("尝试次数", result['metadata'].get('attempts', 1))
                
                if execute:
                    st.subheader("📋 查询结果")
                    try:
                        results, columns = text2sql.execute(question, fetch_size=max_results)
                        if results:
                            df = pd.DataFrame(results)
                            st.info(f"返回 {len(results)} 条结果")
                            st.dataframe(df, use_container_width=True)
                            
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                "📥 下载 CSV",
                                csv,
                                f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                "text/csv"
                            )
                        else:
                            st.warning("查询未返回结果")
                    except Exception as e:
                        st.error(f"执行失败: {e}")
            else:
                st.error(f"生成失败: {result.get('error', '未知错误')}")
        except Exception as e:
            st.error(f"处理失败: {e}")


def graph_management_page(text2sql):
    """图谱管理"""
    st.subheader("🏗️ 知识图谱管理")
    
    tab1, tab2 = st.tabs(["📊 统计", "🔄 重建"])
    
    with tab1:
        try:
            stats = text2sql.get_statistics()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("表节点", stats['graph'].get('table_count', 0))
            with col2:
                st.metric("列节点", stats['graph'].get('column_count', 0))
            with col3:
                st.metric("概念", stats['graph'].get('concept_count', 0))
            with col4:
                st.metric("关系", stats['graph'].get('foreign_key_count', 0))
        except Exception as e:
            st.error(f"获取统计失败: {e}")
    
    with tab2:
        st.warning("⚠️ 重建将清除现有图谱")
        if st.button("🔄 开始重建", type="primary"):
            with st.spinner("重建中..."):
                try:
                    stats = text2sql.build_knowledge_graph(clear_existing=True)
                    st.success("✅ 重建完成！")
                    st.json(stats)
                except Exception as e:
                    st.error(f"重建失败: {e}")


def main():
    """主函数"""
    display_header()
    
    max_results, show_metadata, use_cache = sidebar_config()
    
    text2sql, error = initialize_system()
    
    if not text2sql:
        st.error(f"系统初始化失败: {error}")
        st.info("请运行: python quick_start.py")
        return
    
    tab1, tab2 = st.tabs(["🔍 查询", "🏗️ 管理"])
    
    with tab1:
        main_query_interface(text2sql, max_results, show_metadata, use_cache)
    
    with tab2:
        graph_management_page(text2sql)
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 1rem;">
        <p><strong>Graph-Enhanced Text2SQL</strong> v1.0</p>
        <p>📚 <a href="docs/QUICKSTART.md">文档</a></p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
