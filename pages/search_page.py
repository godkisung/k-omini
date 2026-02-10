"""
Streamlit 검색 페이지 - 전역 텍스트 검색
"""
import streamlit as st
import pandas as pd

from app_helpers import perform_search


def search_page():
    """검색 페이지 메인 함수"""
    st.header("🔎 전역 텍스트 검색")
    
    search_query = st.text_input(
        "검색어를 입력하세요:",
        key="search_query_input"
    )
    
    if st.button("검색", type="primary", key="search_submit_btn"):
        if not search_query:
            st.warning("검색어를 입력해주세요.")
            return
        
        results_df = perform_search(search_query)
        _render_search_results(search_query, results_df)


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
