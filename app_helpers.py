"""
Streamlit 앱 헬퍼 함수 모듈
공통으로 사용되는 데이터 로딩 및 처리 함수
"""
import streamlit as st
import os
import glob
import json
import pandas as pd
from typing import List

# [Refactor] New Module Imports
from src.config import get_config, DATA_DIR
from src.core.models import Document, get_json_files as core_get_json_files
from src.analysis.validator import Validator, Severity

# Initialize Validator with Config
config = get_config()
# validator = Validator(config) # Moved inside function to ensure fresh instance

@st.cache_data(show_spinner=False)
def get_json_files() -> List[str]:
    """
    데이터 디렉토리에서 모든 JSON 파일 이름 가져오기
    Returns: 정렬된 JSON 파일 이름 리스트 (Basename)
    """
    # core_get_json_files returns full paths, we usually want basenames for UI
    full_paths = core_get_json_files(DATA_DIR)
    files = [os.path.basename(f) for f in full_paths]
    
    if not files:
        st.error(f"❌ 데이터 디렉토리에 JSON 파일이 없습니다: {DATA_DIR}")
    return files

@st.cache_data(show_spinner=False)
def load_document(file_name: str) -> Document:
    """
    JSON 파일에서 문서 로드
    Args: file_name: 로드할 JSON 파일 이름/경로
    """
    # If simple filename, join with DATA_DIR
    if os.path.dirname(file_name) == "":
        json_path = os.path.join(DATA_DIR, file_name)
    else:
        json_path = file_name
        
    return Document.from_json(json_path)

@st.cache_data(show_spinner=False)
def perform_bulk_validation() -> pd.DataFrame:
    """
    모든 파일에 대한 검증 실행 및 DataFrame 리포트 반환
    """
    full_paths = core_get_json_files(DATA_DIR)
    report_data = []
    
    # Progress UI
    progress_bar = st.progress(0, text="일괄 검증 시작 중...")
    
    # Instantiate Validator here to ensure latest class definition is used
    validator = Validator(config)

    for i, json_path in enumerate(full_paths):
        file_name = os.path.basename(json_path)
        progress_bar.progress((i + 1) / len(full_paths), text=f"검증 중: {file_name}")
        
        try:
            doc = Document.from_json(json_path)
            
            # 1. Validation Logic
            for ann in doc.layout_dets:
                results = validator.validate_annotation(ann)
                for res in results:
                     if res.severity in [Severity.ERROR, Severity.WARNING]:
                        report_data.append({
                            "파일": file_name,
                            "카테고리": ann.category_type or "N/A",
                            "어노테이션 ID": ann.anno_id or "N/A",
                            "순서": ann.order if ann.order is not None else "N/A",
                            "심각도": res.severity.name,
                            "규칙": res.rule_id,
                            "메시지": res.message,
                        })
                        
        except Exception as e:
            # File Load Error
            report_data.append({
                "파일": file_name,
                "심각도": "ERROR",
                "규칙": "file_load_error",
                "메시지": str(e)
            })

    progress_bar.empty()
    return pd.DataFrame(report_data)

@st.cache_data(show_spinner=False)
def perform_search(query: str) -> pd.DataFrame:
    """모든 어노테이션의 텍스트에서 쿼리 문자열 검색"""
    if not query: return pd.DataFrame()
    
    full_paths = core_get_json_files(DATA_DIR)
    search_results = []
    progress_bar = st.progress(0, text="검색 시작 중...")
    
    for i, json_path in enumerate(full_paths):
        file_name = os.path.basename(json_path)
        progress_bar.progress((i + 1) / len(full_paths), text=f"검색 중: {file_name}")
        
        try:
            doc = Document.from_json(json_path)
            for ann in doc.layout_dets:
                if ann.text and query.lower() in ann.text.lower():
                    search_results.append({
                        "파일": file_name,
                        "순서": ann.order if ann.order is not None else "N/A",
                        "카테고리": ann.category_type,
                        "텍스트": ann.text[:200] + "..." if len(ann.text) > 200 else ann.text,
                    })
        except:
             continue
             
    progress_bar.empty()
    return pd.DataFrame(search_results)

@st.cache_data(show_spinner=False)
def get_file_metadata(file_name: str) -> dict:
    """파일 메타데이터 가져오기"""
    doc = load_document(file_name)
    return {
        "file_name": file_name,
        "total_annotations": len(doc.layout_dets),
        "categories": list(set([ann.category_type for ann in doc.layout_dets])),
        "has_image": bool(doc.image_path),
        "image_path": doc.image_path,
    }

def clear_cache():
    st.cache_data.clear()
    st.success("캐시가 초기화되었습니다.")
