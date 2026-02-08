"""
Streamlit 검수 페이지 - 인덱스 오류 및 LaTeX 렌더링 수정 버전
"""
import streamlit as st
import os
import pandas as pd
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

try:
    import streamlit_shortcuts as ss
    SHORTCUTS_AVAILABLE = True
except ImportError:
    SHORTCUTS_AVAILABLE = False

from src import config
from src.data_engine import Document
from src.render_engine import draw_annotations_on_image
import importlib
try:
    importlib.reload(config)
except:
    pass

from src.analysis_engine import (
    validate_annotation, # Renamed run_validation to validate_annotation? Check naming
    validate_text_with_ocr,
    validate_table_structure_with_ocr,
    Severity,
    ValidationResult
)
from src.data_engine import get_json_files, load_document

# --- 1. 초기화 및 세션 관리 ---
def _initialize_session_state():
    if "file_index" not in st.session_state:
        st.session_state.file_index = 0
    if "selected_index" not in st.session_state:
        st.session_state.selected_index = 0
    if "last_search_query" not in st.session_state:
        st.session_state.last_search_query = ""
    if "current_file" not in st.session_state:
        st.session_state.current_file = None
    if "show_only_errors" not in st.session_state:
        st.session_state.show_only_errors = False

@st.cache_data
def get_cached_files():
    return get_json_files()

# --- 2. 메인 페이지 로직 ---
def inspect_page():
    _initialize_session_state()
    _render_global_shortcuts()

    tab_inspect, tab_file, tab_filter, tab_info = st.sidebar.tabs(["🔍 검수", "📂 파일", "⚙️ 필터", "ℹ️ 정보"])
    
    with tab_file:
        selected_file, filtered_files = _render_file_navigation_tab()
    
    if not selected_file:
        st.info("파일을 선택하세요.")
        return

    if st.session_state.current_file != selected_file:
        st.session_state.current_file = selected_file
        st.session_state.selected_index = 0
        st.rerun()

    doc = load_document(selected_file)

    with tab_filter:
        category_filter, show_only_errors = _render_filter_tab(doc)
    
    with tab_info:
        _render_info_tab(doc, selected_file)

    filtered_anns, filtered_indices = _filter_annotations(doc, category_filter, show_only_errors)
    
    if not filtered_anns:
        st.warning("⚠️ 필터 조건에 맞는 어노테이션이 없습니다.")
        st.stop()

    current_filtered_idx = _adjust_selected_index(st.session_state.selected_index, filtered_indices, doc)

    _render_main_visual_ui(doc, filtered_anns, filtered_indices, current_filtered_idx)
    
    with tab_inspect:
        _render_inspection_panel(doc, filtered_anns, filtered_indices, current_filtered_idx)

# --- 3. 파일 탐색 (인덱스 오류 방어 코드 추가) ---
def _render_file_navigation_tab():
    st.markdown("### 📁 파일 탐색")
    json_files = get_cached_files()
    
    search_query = st.text_input("🔍 파일 검색", value=st.session_state.last_search_query, key="f_search")
    st.session_state.last_search_query = search_query

    filtered_files = [f for f in json_files if search_query.lower() in f.lower()] if search_query else json_files
    
    if not filtered_files:
        st.warning("검색 결과가 없습니다.")
        return None, []

    # [수정] 파일 인덱스가 현재 필터링된 결과 범위를 벗어나지 않도록 보정
    if st.session_state.file_index >= len(filtered_files):
        st.session_state.file_index = max(0, len(filtered_files) - 1) #

    total = len(filtered_files)
    curr = st.session_state.file_index + 1
    
    # [핵심 수정] 진행률 값이 1.0을 넘지 않도록 min/max로 제한
    progress_val = min(max(curr / total, 0.0), 1.0) #
    st.progress(progress_val, text=f"파일 위치: {curr} / {total}")
    
    # 페이지 번호 직접 이동 UI
    st.markdown("#### 🔢 페이지 이동")
    col_a, col_b = st.columns([3, 1])
    with col_a:
        page_num = st.number_input(
            "페이지 번호",
            min_value=1,
            max_value=total,
            value=curr,
            step=1,
            key="page_jump",
            label_visibility="collapsed"
        )
    with col_b:
        if st.button("이동", use_container_width=True, key="btn_page_jump"):
            st.session_state.file_index = page_num - 1
            st.rerun()
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    if col1.button("⏪ 이전 파일", use_container_width=True, key="btn_f_prev"):
        if st.session_state.file_index > 0:
            st.session_state.file_index -= 1
            st.rerun()
    if col2.button("다음 파일 ⏩", use_container_width=True, key="btn_f_next"):
        if st.session_state.file_index < len(filtered_files) - 1:
            st.session_state.file_index += 1
            st.rerun()
    
    selected_file = filtered_files[st.session_state.file_index]
    st.caption(f"📂 {selected_file}")
    return selected_file, filtered_files

# --- 4. 상세 검수 및 콘텐츠 렌더링 (LaTeX 보정 추가) ---
def _render_inspection_panel(doc, filtered_anns, filtered_indices, current_filtered_idx):
    selected_det = doc.layout_dets[st.session_state.selected_index]
    st.markdown(f"## {selected_det.category_type}")
    
    col1, col2 = st.columns(2)
    col1.metric("📋 순서", selected_det.order if selected_det.order is not None else "N/A")
    col2.metric("🆔 ID", str(selected_det.anno_id)[:8] if selected_det.anno_id else "N/A")
    
    st.markdown("---")
    _render_content_tab(selected_det)
    
    # OCR 검증 결과 표시
    if config.OCR_ENABLED:
        _render_ocr_validation_section(selected_det, doc)
    
    st.markdown("### ⚙️ 속성")
    if selected_det.attributes: st.json(selected_det.attributes)
    
    with st.expander("✅ 검증 결과", expanded=False):
        _render_validation_tab(selected_det, doc)

def _render_content_tab(selected_det):
    """카테고리별 맞춤형 시각화 로직"""
    cat = selected_det.category_type
    attrs = selected_det.attributes
    
    # 1. 코드 (code_txt)
    if cat == 'code_txt' and selected_det.text:
        lang = attrs.get('text_language', 'text')
        st.markdown(f"**💻 코드** (언어: `{lang}`)")
        st.code(selected_det.text, language=lang if lang not in ['null', None] else None)
        return  # 코드는 별도 표시하므로 기본 텍스트 뷰 생략 가능

    # 2. 기본 텍스트 (다른 카테고리)
    if selected_det.text and selected_det.text.strip():
        st.markdown("**📝 텍스트**")
        st.text_area("Content", value=selected_det.text, height=150, key=f"tx_{selected_det.anno_id}", disabled=True, label_visibility="collapsed")
    
    # 3. LaTeX 수식
    if hasattr(selected_det, 'latex') and selected_det.latex:
        formula_type = attrs.get('formula_type', 'General')
        with st.expander(f"📐 LaTeX 수식 ({formula_type})", expanded=True):
            raw_latex = selected_det.latex.strip()
            clean_latex = raw_latex.replace("$$", "").strip()
            try:
                st.latex(clean_latex)
            except Exception as e:
                st.error(f"LaTeX 렌더링 실패: {str(e)}")
            st.code(raw_latex, language="latex")
            
    # 4. HTML (표, 차트)
    if hasattr(selected_det, 'html') and selected_det.html:
        type_info = ""
        if cat == 'chart':
            type_info = f"({attrs.get('chart_type', 'Chart')})"
        elif cat == 'table':
            type_info = f"({attrs.get('table_layout', 'Table')})"
            
        with st.expander(f"📊 HTML 미리보기 {type_info}", expanded=True):
            st.markdown(selected_det.html, unsafe_allow_html=True)

# --- 5. 보조 함수들 (기본 구조 유지) ---
def _render_global_shortcuts():
    if not SHORTCUTS_AVAILABLE: return
    with st.sidebar.expander("⌨️ 단축키 안내", expanded=False):
        if ss.shortcut_button("파일 이전", shortcut="Alt+ArrowLeft", key="sc_f_p"):
            if st.session_state.file_index > 0:
                st.session_state.file_index -= 1
                st.rerun()
        if ss.shortcut_button("파일 다음", shortcut="Alt+ArrowRight", key="sc_f_n"):
            st.session_state.file_index += 1
            st.rerun()

def _render_main_visual_ui(doc, filtered_anns, filtered_indices, current_filtered_idx):
    selected_det = doc.layout_dets[st.session_state.selected_index]
    st.subheader(f"📍 {current_filtered_idx + 1} / {len(filtered_anns)}")
    
    # 어노테이션 이동 버튼 (네비게이션)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if (ss.shortcut_button("⏮️ 처음", shortcut="Home", key="btn_a_f") if SHORTCUTS_AVAILABLE else st.button("⏮️ 처음")):
            st.session_state.selected_index = filtered_indices[0]
            st.rerun()
    with col2:
        c1, c2 = st.columns(2)
        if (ss.shortcut_button("⬅️ 이전", shortcut="ArrowLeft", key="btn_a_p") if SHORTCUTS_AVAILABLE else c1.button("⬅️ 이전")):
            if current_filtered_idx > 0:
                st.session_state.selected_index = filtered_indices[current_filtered_idx - 1]
                st.rerun()
        if (ss.shortcut_button("다음 ➡️", shortcut="ArrowRight", key="btn_a_n") if SHORTCUTS_AVAILABLE else c2.button("다음 ➡️")):
            if current_filtered_idx < len(filtered_indices) - 1:
                st.session_state.selected_index = filtered_indices[current_filtered_idx + 1]
                st.rerun()
    with col3:
        if (ss.shortcut_button("끝 ⏭️", shortcut="End", key="btn_a_l") if SHORTCUTS_AVAILABLE else st.button("끝 ⏭️")):
            st.session_state.selected_index = filtered_indices[-1]
            st.rerun()

    full_image_path = os.path.join(config.IMAGE_DIR, doc.image_path)
    if os.path.exists(full_image_path):
        image = Image.open(full_image_path).convert("RGB")
        # [수정] draw_annotations_on_image API 변경 반영
        # 1. ann.data (dict) -> ann (Object)
        # 2. highlight_id (ID) -> highlight_indices (Index)
        annotated_image = draw_annotations_on_image(
            image.copy(), 
            doc.layout_dets, 
            highlight_indices=[st.session_state.selected_index]
        )
        coords = streamlit_image_coordinates(annotated_image, key="img_m", use_column_width=True)
        if coords:
            for i, ann in reversed(list(enumerate(doc.layout_dets))):
                if ann.is_inside(coords["x"], coords["y"]):
                    st.session_state.selected_index = i
                    st.rerun()

def _render_validation_tab(selected_det, doc):
    val_results = validate_annotation(selected_det.raw_data)
    if not val_results: st.success("이슈 없음")
    for res in val_results:
        if res.severity == Severity.ERROR: st.error(res.message)
        else: st.warning(res.message)

def _render_filter_tab(doc):
    categories = sorted(list(set([ann.category_type for ann in doc.layout_dets])))
    cat = st.selectbox("카테고리", ["전체"] + categories, key="s_cat")
    err = st.checkbox("⚠️ 검증 오류만 보기", value=st.session_state.show_only_errors, key="c_err")
    st.session_state.show_only_errors = err
    return cat, err

def _filter_annotations(doc, category_filter, show_only_errors):
    filtered_anns, filtered_indices = [], []
    for i, ann in enumerate(doc.layout_dets):
        if category_filter != "전체" and ann.category_type != category_filter: continue
        if show_only_errors:
            val_results = validate_annotation(ann.raw_data)
            if not any(r.severity in [Severity.ERROR, Severity.WARNING] for r in val_results): continue
        filtered_anns.append(ann)
        filtered_indices.append(i)
    return filtered_anns, filtered_indices

def _adjust_selected_index(selected_index, filtered_indices, doc):
    if selected_index not in filtered_indices:
        if filtered_indices:
            st.session_state.selected_index = filtered_indices[0]
            return 0
    return filtered_indices.index(st.session_state.selected_index) if filtered_indices else 0

def _render_info_tab(doc, selected_file):
    st.metric("총 어노테이션", f"{len(doc.layout_dets)}개")
    st.text(f"파일: {os.path.basename(selected_file)}")

def _load_ocr_cache():
    """OCR 캐시 파일을 로드합니다."""
    # [수정] config 로딩 실패 시 안전장치 (fallback)
    cache_file = getattr(config, 'OCR_CACHE_FILE', 
                        os.path.join(config.PROJECT_ROOT, ".ocr_cache", "batch_ocr_results.csv"))
    
    if not os.path.exists(cache_file):
        return None
    try:
        df = pd.read_csv(config.OCR_CACHE_FILE)
        # 검색 속도를 위해 dict로 변환: (filename, anno_id) -> row
        cache_dict = {}
        for _, row in df.iterrows():
            cache_dict[(row['filename'], row['anno_id'])] = row
        return cache_dict
    except Exception:
        return None

def _render_ocr_validation_section(selected_det, doc):
    """OCR 기반 검증 결과를 표시합니다 (캐시 우선)."""
    st.markdown("### 🤖 OCR 자동 검증")
    
    # 캐시 로드
    cache = _load_ocr_cache()
    cached_result = None
    
    current_filename = os.path.basename(st.session_state.current_file) if st.session_state.current_file else ""
    
    if cache and (current_filename, selected_det.anno_id) in cache:
        cached_result = cache[(current_filename, selected_det.anno_id)]
    
    if cached_result is not None:
        # 캐시된 결과 표시
        sim = float(cached_result['similarity'])
        ocr_text = str(cached_result['ocr_text'])
        
        # 색상 코딩
        if sim >= config.OCR_SIMILARITY_THRESHOLD:
            st.success(f"✅ OCR 검증 통과 (유사도: {sim:.1%})")
        elif sim >= 0.7:
            st.warning(f"⚠️ 텍스트 불일치 의심 (유사도: {sim:.1%})")
        else:
            st.error(f"🔴 텍스트 불일치 감지 (유사도: {sim:.1%})")
            
        with st.expander("🔍 OCR 상세 비교 (Cached)", expanded=True):
            col_a, col_b = st.columns(2)
            col_a.text_area("GT Text", value=selected_det.text, height=100, disabled=True)
            col_b.text_area("OCR Text", value=ocr_text, height=100, disabled=True)
            
    else:
        # 캐시 없음 - 수동 실행 버튼
        st.info("⚠️ 배치 처리가 되지 않은 항목입니다.")
        if st.button("지금 OCR 실행 (1건)"):
            # 기존 로직 (On-the-fly 실행)
            _run_ad_hoc_ocr(selected_det, doc)

def _run_ad_hoc_ocr(selected_det, doc):
    # from qa_visualizer.validation import validate_text_with_ocr (Removed)
    full_image_path = os.path.join(config.IMAGE_DIR, doc.image_path)
    
    with st.spinner("OCR 실행 중..."):
        ocr_results = validate_text_with_ocr(
            selected_det.raw_data,
            full_image_path,
            config.OCR_SIMILARITY_THRESHOLD,
            doc.raw_data
        )
        # 결과 표시 (기존 로직 재사용)
        if ocr_results:
            for res in ocr_results:
                if res.severity == Severity.ERROR: st.error(res.message)
                elif res.severity == Severity.WARNING: st.warning(res.message)
                else: st.info(res.message)
        else:
            st.success("✅ OCR 실행 완료 (이슈 없음)")

if __name__ == "__main__":
    inspect_page()