import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from typing import List

from src import config
from src.data_engine import Document, get_json_files, load_document
from src.analysis_engine import (
    calculate_category_stats,
    extract_doc_type_from_filename,
    DOC_TYPE_NAMES,
    detect_text_length_outliers,
    detect_bbox_size_outliers,
    get_statistics_summary,
    calculate_bbox_area
)



# 한글 폰트 설정
def set_korean_font():
    """한글 폰트 설정"""
    try:
        # 시스템에서 사용 가능한 한글 폰트 찾기
        font_list = fm.findSystemFonts(fontpaths=None, fontext='ttf')
        korean_fonts = [f for f in font_list if 'Nanum' in f or 'Malgun' in f or 'AppleGothic' in f]
        
        if korean_fonts:
            font_path = korean_fonts[0]
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams['font.family'] = font_prop.get_name()
        else:
            # 기본 폰트 사용
            plt.rcParams['font.family'] = 'DejaVu Sans'
    except:
        plt.rcParams['font.family'] = 'DejaVu Sans'
    
    # 마이너스 기호 깨짐 방지
    plt.rcParams['axes.unicode_minus'] = False


def statistics_page():
    """통계 페이지 메인 함수"""
    st.header("📊 라벨 작업 품질 분석")
    
    # 한글 폰트 설정
    set_korean_font()
    
    # 파일 로드
    json_files = get_json_files()
    
    if not json_files:
        st.warning("분석할 파일이 없습니다.")
        return
    
    # 문서 타입 추출
    doc_types = set()
    for filename in json_files:
        doc_type = extract_doc_type_from_filename(filename)
        if doc_type != 'DEFAULT':
            doc_types.add(doc_type)
    
    # 사이드바: 필터
    st.sidebar.header("🔍 필터")
    
    doc_type_options = ['전체'] + sorted(list(doc_types))
    selected_doc_type = st.sidebar.selectbox(
        "문서 타입",
        options=doc_type_options,
        format_func=lambda x: f"{x} ({DOC_TYPE_NAMES.get(x, x)})" if x != '전체' else x
    )
    
    # 분석 실행 버튼
    if st.sidebar.button("🚀 분석 실행", type="primary"):
        st.session_state.analysis_done = True
    
    if not st.session_state.get('analysis_done', False):
        st.info("👈 사이드바에서 '분석 실행' 버튼을 클릭하세요.")
        return
    
    # 문서 로드
    with st.spinner("문서를 로드하는 중..."):
        docs: List[Document] = []
        progress_bar = st.progress(0)
        
        for i, filename in enumerate(json_files):
            doc = load_document(filename)
            docs.append(doc)
            progress_bar.progress((i + 1) / len(json_files))
        
        progress_bar.empty()
    
    # 문서 타입 필터 적용
    doc_type_filter = None if selected_doc_type == '전체' else selected_doc_type
    
    # 탭 구분
    tab1, tab2, tab3 = st.tabs(["📈 기본 통계", "⚠️ 이상치 분석", "📊 상세 분석"])
    
    with tab1:
        _render_basic_statistics(docs, doc_type_filter)
    
    with tab2:
        _render_outlier_analysis(docs, doc_type_filter)
    
    with tab3:
        _render_detailed_analysis(docs, doc_type_filter)


def _render_basic_statistics(docs: List[Document], doc_type_filter: str):
    """기본 통계 렌더링"""
    st.subheader("📈 기본 통계")
    
    # 통계 요약
    stats = get_statistics_summary(docs, doc_type_filter)
    
    # 메트릭 표시
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 파일 수", f"{stats['total_files']:,}")
    with col2:
        st.metric("총 어노테이션 수", f"{stats['total_annotations']:,}")
    with col3:
        st.metric("평균 텍스트 길이", f"{stats['text_length']['mean']:.1f}자")
    with col4:
        st.metric("평균 영역 비율", f"{stats['bbox_area']['mean']:.1f}%")
    
    # 카테고리 분포
    st.markdown("---")
    st.subheader("📊 카테고리 분포")
    
    if stats['category_distribution']:
        category_df = pd.DataFrame([
            {'카테고리': k, '개수': v}
            for k, v in sorted(stats['category_distribution'].items(), key=lambda x: -x[1])
        ])
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.dataframe(category_df, use_container_width=True, height=400)
        
        with col2:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.barh(category_df['카테고리'], category_df['개수'])
            ax.set_xlabel('개수')
            ax.set_title('카테고리별 어노테이션 개수')
            plt.tight_layout()
            st.pyplot(fig)
    else:
        st.info("카테고리 분포 데이터가 없습니다.")


def _render_outlier_analysis(docs: List[Document], doc_type_filter: str):
    """이상치 분석 렌더링"""
    st.subheader("⚠️ 이상치 분석")
    
    # 텍스트 길이 이상치
    with st.spinner("텍스트 길이 이상치 탐지 중..."):
        text_outliers = detect_text_length_outliers(docs, doc_type_filter)
    
    # 폴리곤 크기 이상치
    with st.spinner("폴리곤 크기 이상치 탐지 중..."):
        bbox_outliers = detect_bbox_size_outliers(docs, doc_type_filter)
    
    # 요약
    col1, col2 = st.columns(2)
    with col1:
        st.metric("텍스트 길이 이상치", f"{len(text_outliers):,}개")
    with col2:
        st.metric("폴리곤 크기 이상치", f"{len(bbox_outliers):,}개")
    
    # 텍스트 길이 이상치
    st.markdown("---")
    st.markdown("### 📏 텍스트 길이 이상치")
    
    if text_outliers:
        text_df = pd.DataFrame(text_outliers)
        
        # Arrow 변환 오류 방지: 타입 변환 강화
        for col in text_df.columns:
            if col in ['anno_id', 'file', 'doc_type', 'category', 'reason', 'text_preview']:
                text_df[col] = text_df[col].astype(str).replace('nan', '')
            elif col in ['min', 'max', 'length', 'order']:
                text_df[col] = pd.to_numeric(text_df[col], errors='coerce').fillna(0)
            
        # order는 int로 변환
        if 'order' in text_df.columns:
            text_df['order'] = text_df['order'].astype(int)
        if 'length' in text_df.columns:
            text_df['length'] = text_df['length'].astype(int)
        
        # 필터
        col1, col2 = st.columns(2)
        with col1:
            reason_filter = st.multiselect(
                "이유 필터",
                options=sorted(list(text_df['reason'].unique())),
                default=sorted(list(text_df['reason'].unique()))
            )
        with col2:
            category_filter = st.multiselect(
                "카테고리 필터",
                options=sorted(list(text_df['category'].unique())),
                default=sorted(list(text_df['category'].unique()))
            )
        
        filtered_text_df = text_df[
            text_df['reason'].isin(reason_filter) &
            text_df['category'].isin(category_filter)
        ]
        
        st.dataframe(filtered_text_df, use_container_width=True, height=400)
        
        # 다운로드
        csv = filtered_text_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 CSV로 다운로드",
            csv,
            "text_length_outliers.csv",
            "text/csv",
            key='download_text_outliers'
        )
    else:
        st.success("✅ 텍스트 길이 이상치가 없습니다!")
    
    # 폴리곤 크기 이상치
    st.markdown("---")
    st.markdown("### 📐 폴리곤 크기 이상치")
    
    if bbox_outliers:
        bbox_df = pd.DataFrame(bbox_outliers)
        
        # Arrow 변환 오류 방지: 타입 변환 강화
        for col in bbox_df.columns:
            if col in ['anno_id', 'file', 'doc_type', 'category', 'reason']:
                bbox_df[col] = bbox_df[col].astype(str).replace('nan', '')
            elif col in ['width', 'height', 'area', 'area_ratio', 'aspect_ratio', 'min_ratio', 'max_ratio', 'order']:
                bbox_df[col] = pd.to_numeric(bbox_df[col], errors='coerce').fillna(0)
        
        # order는 int로 변환
        if 'order' in bbox_df.columns:
            bbox_df['order'] = bbox_df['order'].astype(int)
        
        # 필터
        col1, col2 = st.columns(2)
        with col1:
            reason_filter = st.multiselect(
                "이유 필터",
                options=sorted(list(bbox_df['reason'].unique())),
                default=sorted(list(bbox_df['reason'].unique())),
                key='bbox_reason_filter'
            )
        with col2:
            category_filter = st.multiselect(
                "카테고리 필터",
                options=sorted(list(bbox_df['category'].unique())),
                default=sorted(list(bbox_df['category'].unique())),
                key='bbox_category_filter'
            )
        
        filtered_bbox_df = bbox_df[
            bbox_df['reason'].isin(reason_filter) &
            bbox_df['category'].isin(category_filter)
        ]
        
        st.dataframe(filtered_bbox_df, use_container_width=True, height=400)
        
        # 다운로드
        csv = filtered_bbox_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 CSV로 다운로드",
            csv,
            "bbox_size_outliers.csv",
            "text/csv",
            key='download_bbox_outliers'
        )
    else:
        st.success("✅ 폴리곤 크기 이상치가 없습니다!")


def _render_detailed_analysis(docs: List[Document], doc_type_filter: str):
    """상세 분석 렌더링"""
    st.subheader("📊 상세 분석")
    
    # 텍스트 길이 분포
    st.markdown("### 📏 텍스트 길이 분포")
    
    text_lengths = []
    for doc in docs:
        if doc_type_filter:
            doc_type = extract_doc_type_from_filename(doc.filename)
            if doc_type != doc_type_filter:
                continue
        
        for ann in doc.layout_dets:
            if ann.text:
                text_lengths.append(len(ann.text))
    
    if text_lengths:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(text_lengths, bins=50, edgecolor='black', alpha=0.7)
        ax.set_xlabel('텍스트 길이 (자)')
        ax.set_ylabel('빈도')
        ax.set_title('텍스트 길이 분포')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("텍스트 데이터가 없습니다.")
    
    # 폴리곤 크기 분포
    st.markdown("---")
    st.markdown("### 📐 폴리곤 크기 분포")
    
    bbox_areas = []
    for doc in docs:
        if doc_type_filter:
            doc_type = extract_doc_type_from_filename(doc.filename)
            if doc_type != doc_type_filter:
                continue
        
        page_area = doc.page_info.width * doc.page_info.height
        for ann in doc.layout_dets:
            if ann.poly:
                size_info = calculate_bbox_area(ann.poly)
                bbox_areas.append(size_info['area'] / page_area * 100)
    
    if bbox_areas:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(bbox_areas, bins=50, edgecolor='black', alpha=0.7)
        ax.set_xlabel('영역 비율 (%)')
        ax.set_ylabel('빈도')
        ax.set_title('폴리곤 크기 분포 (페이지 대비 비율)')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("폴리곤 데이터가 없습니다.")


if __name__ == "__main__":
    statistics_page()
