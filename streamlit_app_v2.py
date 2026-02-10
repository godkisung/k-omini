import streamlit as st
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="K-Omnidoc QA Visualizer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Imports from new structure ---
from src import config
from src.data_engine import get_json_files, load_document

# --- Session State Initialization ---
if 'current_file_idx' not in st.session_state:
    st.session_state.current_file_idx = 0
if 'files' not in st.session_state:
    st.session_state.files = []
if 'global_filters' not in st.session_state:
    st.session_state.global_filters = {"category": "All"}

def main():
    st.title("🔍 K-Omnidoc QA Visualizer (Refactored)")
    
    st.markdown("""
    ### 👋 Welcome!
    이 도구는 **K-Omnidoc Benchmark 데이터셋**의 품질 검증을 위해 설계되었습니다.
    
    #### 🚀 주요 기능
    *   **Inspect Page**: 개별 문서의 어노테이션 시각화 및 검증
    *   **Statistics Page**: 데이터셋 전체 통계 및 오류 유형 분석
    *   **Batch OCR**: 대량 문서 OCR 일괄 처리 및 검증
    
    좌측 사이드바에서 원하는 **Page**를 선택하여 작업을 시작하세요.
    """)
    
    # 데이터 로드 확인
    files = get_json_files()
    st.info(f"📂 데이터베이스 로드 완료: 총 {len(files)}개의 문서가 감지되었습니다.")
    
    with st.expander("🛠️ 시스템 설정 정보"):
        st.json({
            "Data Directory": config.DATA_DIR,
            "Image Directory": config.IMAGE_DIR,
            "OCR Enabled": config.get_config().OCR_ENABLED,
            "Cache Status": "Active" if os.path.exists(config.OCR_CACHE_FILE) else "Empty"
        })

if __name__ == "__main__":
    main()
