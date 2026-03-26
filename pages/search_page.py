"""
Streamlit 검색 페이지 - 전역 텍스트 검색
"""
import streamlit as st
import pandas as pd

from app_helpers import perform_search


from PIL import Image
import os

from src.config import DATA_ROOT, IMAGE_DIR
from app_helpers import perform_search, perform_visual_search, load_document


def search_page():
    """검색 페이지 메인 함수 - 텍스트 및 시각적 유사도 검색 지원"""
    st.set_page_config(layout="wide") if not "layout" in st.session_state else None
    st.header("🔎 문서 검색 및 중복 탐지")
    
    tab_text, tab_visual = st.tabs(["🔤 텍스트 검색", "🖼️ 시각적 유사도 검색"])
    
    with tab_text:
        _render_text_search_tab()
        
    with tab_visual:
        _render_visual_search_tab()


def _render_text_search_tab():
    """기존 텍스트 검색 탭"""
    search_query = st.text_input(
        "검색어를 입력하세요 (텍스트 추출 결과 기준):",
        key="search_query_text_input"
    )
    
    if st.button("검색", type="primary", key="search_text_btn"):
        if not search_query:
            st.warning("검색어를 입력해주세요.")
            return
        
        results_df = perform_search(search_query)
        _render_search_results(search_query, results_df)


def _render_visual_search_tab():
    """시각적 유사도 검색 탭 (3-Stage)"""
    st.subheader("이미지 기반 유사 문서 찾기")
    st.info("업로드한 이미지와 가장 유사한 레이아웃이나 내용을 가진 문서를 Milvus DB에서 검색합니다.")
    
    col_input, col_config = st.columns([1, 1])
    
    with col_input:
        uploaded_file = st.file_uploader("쿼리 이미지 업로드", type=["png", "jpg", "jpeg"])
    
    with col_config:
        search_stage = st.selectbox(
            "유사도 기준 선택 (3-Stage)",
            options=[1, 2, 3],
            format_func=lambda x: {
                1: "Stage 1: 전체 이미지 유사도 (Jina-CLIP)",
                2: "Stage 2: 템플릿/레이아웃 유사도 (DINOv2)",
                3: "Stage 3: 특정 영역(직인/서명) 유사도 (Florence-2)"
            }[x],
            help="Stage 1은 전반적인 내용, Stage 2는 레이아웃, Stage 3은 날인/서명을 중점적으로 봅니다."
        )
        
        target_label = None
        if search_stage == 3:
            target_label = st.selectbox("탐색 영역 선택", ["stamp", "signature", "table"])
            
        top_k = st.slider("검색 결과 개수", 1, 20, 5)

    if uploaded_file:
        query_img = Image.open(uploaded_file).convert("RGB")
        st.image(query_img, caption="쿼리 이미지", width=300)
        
        if st.button("유사 문서 검색 시작", type="primary"):
            with st.spinner("Milvus 벡터 공간에서 검색 중..."):
                results_df = perform_visual_search(query_img, stage=search_stage, label=target_label, top_k=top_k)
                
            if results_df.empty:
                st.error("유사한 문서를 찾지 못했습니다. DB에 데이터가 있는지 확인해주세요.")
            else:
                st.success(f"상위 {len(results_df)}개의 유사 문서를 찾았습니다.")
                _render_visual_hits(query_img, results_df)


def _render_visual_hits(query_img, hits_df):
    """검색된 유사 문서 결과 렌더링"""
    for idx, row in hits_df.iterrows():
        doc_id = row['doc_id']
        score = row['score']
        
        with st.container(border=True):
            cols = st.columns([1, 2, 2])
            
            with cols[0]:
                st.metric("유사도 점수", f"{score:.4f}")
                st.write(f"**파일명**: {doc_id}")
                if 'label' in row:
                    st.write(f"**매칭 영역**: {row['label']}")
            
            with cols[1]:
                st.image(query_img, caption="쿼리 (User)", use_container_width=True)
            
            with cols[2]:
                # 이미지 경로 찾기 (DOC_ID는 .json 포함일 수 있음)
                base_name = os.path.splitext(doc_id)[0]
                
                # 확장자 대응 (jpg 또는 png)
                img_path_jpg = os.path.join(IMAGE_DIR, f"{base_name}.jpg")
                img_path_png = os.path.join(IMAGE_DIR, f"{base_name}.png")
                
                final_img_path = None
                if os.path.exists(img_path_jpg):
                    final_img_path = img_path_jpg
                elif os.path.exists(img_path_png):
                    final_img_path = img_path_png
                
                if final_img_path:
                    st.image(final_img_path, caption=f"검색 결과: {doc_id}", use_container_width=True)
                else:
                    st.error(f"이미지 파일을 찾을 수 없습니다 (JPG/PNG).")
                    st.caption(f"경로: {img_path_jpg}")


def _render_search_results(query: str, results_df: pd.DataFrame):
    """검색 결과 렌더링"""
    st.subheader(f"🔍 '{query}' 검색 결과: {len(results_df)}건")
    
    if len(results_df) == 0:
        st.info("검색 결과가 없습니다.")
        return
    
    st.dataframe(results_df, width="stretch", height=600)
    
    # CSV 다운로드 옵션
    csv = results_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 검색 결과 CSV로 다운로드",
        data=csv,
        file_name=f"search_results_{query}.csv",
        mime="text/csv",
        key="search_download_btn"
    )


if __name__ == "__main__":
    search_page()
