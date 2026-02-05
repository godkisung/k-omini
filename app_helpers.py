"""
Streamlit 앱 헬퍼 함수 모듈
공통으로 사용되는 데이터 로딩 및 처리 함수
"""
import streamlit as st
import os
import glob
import json
import pandas as pd
import re
from typing import List, Optional

from qa_visualizer import config
from qa_visualizer.core import Document
from qa_visualizer.validation import run_full_doc_validation, Severity


@st.cache_data(show_spinner=False)
def get_json_files() -> List[str]:
    """
    데이터 디렉토리에서 모든 JSON 파일 이름 가져오기
    
    Returns:
        정렬된 JSON 파일 이름 리스트
    """
    files = sorted(
        [
            os.path.basename(f)
            for f in glob.glob(os.path.join(config.DATA_DIR, "*.json"))
        ]
    )
    if not files:
        st.error(f"❌ 데이터 디렉토리에 JSON 파일이 없습니다: {config.DATA_DIR}")
    return files


@st.cache_data(show_spinner=False)
def load_document(file_name: str) -> Document:
    """
    JSON 파일에서 문서 로드
    
    Args:
        file_name: 로드할 JSON 파일 이름
        
    Returns:
        Document 객체
    """
    json_path = os.path.join(config.DATA_DIR, file_name)
    return Document.from_json(json_path)


@st.cache_data(show_spinner=False)
def perform_bulk_validation() -> pd.DataFrame:
    """
    모든 파일에 대한 검증 실행 및 DataFrame 리포트 반환
    
    Returns:
        검증 결과 DataFrame (파일, 카테고리, 어노테이션 ID, 순서, 심각도, 규칙, 메시지)
    """
    json_files = get_json_files()
    report_data = []
    progress_bar = st.progress(0, text="일괄 검증 시작 중...")

    for i, file_name in enumerate(json_files):
        progress_bar.progress(
            (i + 1) / len(json_files), text=f"검증 중: {file_name}"
        )
        json_path = os.path.join(config.DATA_DIR, file_name)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = run_full_doc_validation(data)

        for res in results:
            if res.severity in [Severity.ERROR, Severity.WARNING]:
                report_data.append(
                    {
                        "파일": file_name,
                        "카테고리": res.category or "N/A",
                        "어노테이션 ID": res.anno_id or "N/A",
                        "순서": res.order if res.order is not None else "N/A",
                        "심각도": res.severity.name,
                        "규칙": res.rule_id,
                        "메시지": res.message,
                    }
                )
    progress_bar.empty()
    return pd.DataFrame(report_data)


@st.cache_data(show_spinner=False)
def perform_search(query: str) -> pd.DataFrame:
    """
    모든 어노테이션의 텍스트에서 쿼리 문자열 검색
    
    Args:
        query: 검색할 문자열
        
    Returns:
        검색 결과 DataFrame (파일, 순서, 카테고리, 텍스트)
    """
    if not query:
        return pd.DataFrame()
    
    json_files = get_json_files()
    search_results = []
    progress_bar = st.progress(0, text="검색 시작 중...")
    
    for i, file_name in enumerate(json_files):
        progress_bar.progress(
            (i + 1) / len(json_files), text=f"검색 중: {file_name}"
        )
        doc = load_document(file_name)
        for ann in doc.layout_dets:
            if ann.text and query.lower() in ann.text.lower():
                search_results.append(
                    {
                        "파일": file_name,
                        "순서": ann.order if ann.order is not None else "N/A",
                        "카테고리": ann.category_type,
                        "텍스트": ann.text[:200] + "..." if len(ann.text) > 200 else ann.text,  # 텍스트 길이 제한
                    }
                )
    progress_bar.empty()
    return pd.DataFrame(search_results)


@st.cache_data(show_spinner=False)
def get_file_metadata(file_name: str) -> dict:
    """
    파일 메타데이터 가져오기 (고도화)
    
    Args:
        file_name: JSON 파일 이름
        
    Returns:
        메타데이터 딕셔너리
    """
    doc = load_document(file_name)
    
    return {
        "file_name": file_name,
        "total_annotations": len(doc.layout_dets),
        "categories": list(set([ann.category_type for ann in doc.layout_dets])),
        "has_image": doc.image_path is not None,
        "image_path": doc.image_path,
    }


def clear_cache():
    """캐시 초기화 (고도화)"""
    st.cache_data.clear()
    st.success("캐시가 초기화되었습니다.")
