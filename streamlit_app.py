import streamlit as st
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="K-Omnidoc QA Visualizer",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📄"
)

# --- Modern Custom CSS ---
st.markdown("""
<style>
    /* 전체 배경 및 폰트 */
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        background-attachment: fixed;
    }
    
    /* 메인 컨텐츠 카드 */
    .content-card {
        background: white;
        border-radius: 20px;
        padding: 3rem;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        margin: 2rem auto;
        max-width: 900px;
    }
    
    /* 제목 스타일 */
    .main-title {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .subtitle {
        text-align: center;
        color: #6c757d;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    
    /* 기능 카드 */
    .feature-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 5px solid #667eea;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
    }
    
    .feature-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 0.5rem;
    }
    
    .feature-desc {
        color: #6c757d;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
    }
    
    /* 통계 배지 */
    .stat-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 25px;
        font-weight: 600;
        margin: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Main Content ---
st.markdown('<div class="content-card">', unsafe_allow_html=True)

st.markdown('<h1 class="main-title">📄 K-Omnidoc QA Visualizer</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">문서 이미지 어노테이션 검증 및 시각화 도구</p>', unsafe_allow_html=True)

st.markdown("---")

# 기능 소개 (깔끔한 카드 형식)
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="feature-card">
        <div class="feature-title">🔍 검수 모드</div>
        <div class="feature-desc">
            개별 문서의 어노테이션을 시각적으로 확인하고<br>
            상세 검증 결과를 실시간으로 확인합니다.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="feature-card">
        <div class="feature-title">🔎 전역 텍스트 검색</div>
        <div class="feature-desc">
            데이터셋 내 모든 어노테이션에서<br>
            특정 키워드를 빠르게 검색합니다.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="feature-card">
        <div class="feature-title">✅ 일괄 검증</div>
        <div class="feature-desc">
            전체 데이터셋에 대한 검증 리포트를 생성하고<br>
            문제점을 한눈에 파악합니다.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="feature-card">
        <div class="feature-title">📊 데이터셋 통계</div>
        <div class="feature-desc">
            카테고리 분포, 언어 분포 등<br>
            데이터셋의 전반적인 통계를 확인합니다.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# CTA (Call to Action)
st.markdown("""
<div style="text-align: center; margin-top: 2rem;">
    <p style="font-size: 1.1rem; color: #6c757d; margin-bottom: 1rem;">
        시작하려면 왼쪽 사이드바에서 원하는 기능을 선택하세요
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align: center; margin-top: 3rem; padding: 1rem; color: white;">
    <p style="font-size: 0.9rem; opacity: 0.8;">
        K-Omnidoc Benchmark Dataset QA Tool | Built with Streamlit
    </p>
</div>
""", unsafe_allow_html=True)