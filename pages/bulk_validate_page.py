"""
Streamlit 일괄 검증 페이지 - 전체 데이터셋 검증 리포트 (고도화)
"""
import streamlit as st
import pandas as pd
from io import BytesIO

from app_helpers import get_json_files, perform_bulk_validation


def bulk_validate_page():
    """일괄 검증 페이지 메인 함수"""
    st.header("🔬 일괄 검증 리포트")
    
    # 상단 컨트롤 패널
    col1, col2 = st.columns([0.8, 0.2])
    with col2:
        if st.button("🔄 재검증 (캐시 초기화)", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # 검증 실행
    report_df = perform_bulk_validation()
    
    if report_df.empty:
        st.success("✅ 모든 파일이 검증을 통과했습니다!")
        return
    
    # 요약 통계
    _render_summary_metrics(report_df)
    
    # 카테고리별 통계 (새로 추가)
    _render_category_statistics(report_df)
    
    # 상세 내역
    st.subheader("📝 상세 내역")
    
    # 고급 필터링 (개선)
    filtered_df = _render_advanced_filters(report_df)
    
    # 데이터 테이블
    st.dataframe(filtered_df, width="stretch", height=600)
    
    # 다운로드 버튼 (CSV + Excel)
    _render_download_buttons(filtered_df)


def _render_summary_metrics(report_df: pd.DataFrame):
    """요약 메트릭 렌더링"""
    st.subheader("📊 요약")
    total_files = len(get_json_files())
    error_count = len(report_df[report_df["심각도"] == "ERROR"])
    warning_count = len(report_df[report_df["심각도"] == "WARNING"])
    total_issues = len(report_df)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("스캔한 파일", total_files)
    c2.metric("총 이슈", total_issues)
    c3.metric("오류 (ERROR)", error_count, delta_color="inverse")
    c4.metric("경고 (WARNING)", warning_count, delta_color="inverse")


def _render_category_statistics(report_df: pd.DataFrame):
    """카테고리별 통계 렌더링 (새로 추가)"""
    st.subheader("📈 카테고리별 통계")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 카테고리별 오류 분포")
        category_errors = report_df[report_df["심각도"] == "ERROR"]["카테고리"].value_counts()
        if not category_errors.empty:
            st.bar_chart(category_errors)
        else:
            st.info("오류가 없습니다.")
    
    with col2:
        st.markdown("#### 규칙별 오류 분포")
        rule_errors = report_df[report_df["심각도"] == "ERROR"]["규칙"].value_counts()
        if not rule_errors.empty:
            st.bar_chart(rule_errors)
        else:
            st.info("오류가 없습니다.")
    
    # 상위 문제 파일
    st.markdown("#### 📂 상위 문제 파일 (Top 10)")
    file_counts = report_df["파일"].value_counts().head(10)
    if not file_counts.empty:
        file_df = pd.DataFrame({
            "파일": file_counts.index,
            "이슈 개수": file_counts.values
        })
        st.dataframe(file_df, width="stretch", height=300)
    else:
        st.info("문제가 있는 파일이 없습니다.")


def _render_advanced_filters(report_df: pd.DataFrame) -> pd.DataFrame:
    """고급 필터링 렌더링 및 필터링된 데이터 반환"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        severity_filter = st.multiselect(
            "심각도 필터",
            options=["ERROR", "WARNING"],
            default=["ERROR", "WARNING"],
            key="bulk_severity_filter"
        )
    
    with col2:
        categories = sorted(report_df["카테고리"].unique().tolist())
        category_filter = st.multiselect(
            "카테고리 필터",
            options=categories,
            default=[],
            key="bulk_category_filter"
        )
    
    with col3:
        rules = sorted(report_df["규칙"].unique().tolist())
        rule_filter = st.multiselect(
            "규칙 필터",
            options=rules,
            default=[],
            key="bulk_rule_filter"
        )
    
    with col4:
        files = sorted(report_df["파일"].unique().tolist())
        file_filter = st.multiselect(
            "파일 필터",
            options=files,
            default=[],
            key="bulk_file_filter"
        )
    
    # 필터링 적용
    filtered_df = report_df[report_df["심각도"].isin(severity_filter)]
    if category_filter:
        filtered_df = filtered_df[filtered_df["카테고리"].isin(category_filter)]
    if rule_filter:
        filtered_df = filtered_df[filtered_df["규칙"].isin(rule_filter)]
    if file_filter:
        filtered_df = filtered_df[filtered_df["파일"].isin(file_filter)]
    
    st.info(f"📊 필터링 결과: {len(filtered_df)}개 이슈 (전체: {len(report_df)}개)")
    
    return filtered_df


def _render_download_buttons(filtered_df: pd.DataFrame):
    """다운로드 버튼 렌더링 (CSV + Excel)"""
    st.subheader("📥 다운로드")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV 다운로드
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📄 CSV로 다운로드",
            data=csv,
            file_name="validation_report.csv",
            mime="text/csv",
            key="bulk_download_csv_btn",
            use_container_width=True
        )
    
    with col2:
        # Excel 다운로드
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='검증 결과')
            
            # 요약 시트 추가
            summary_data = {
                "항목": ["총 이슈", "오류 (ERROR)", "경고 (WARNING)", "스캔한 파일"],
                "값": [
                    len(filtered_df),
                    len(filtered_df[filtered_df["심각도"] == "ERROR"]),
                    len(filtered_df[filtered_df["심각도"] == "WARNING"]),
                    len(get_json_files())
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, index=False, sheet_name='요약')
        
        excel_data = excel_buffer.getvalue()
        st.download_button(
            label="📊 Excel로 다운로드",
            data=excel_data,
            file_name="validation_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="bulk_download_excel_btn",
            use_container_width=True
        )


if __name__ == "__main__":
    bulk_validate_page()
