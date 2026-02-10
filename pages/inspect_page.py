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

# [Refactor] New Module Imports
from src.config import get_config, DATA_DIR, IMAGE_DIR, OCR_CACHE_FILE
from src.core.models import Document, get_json_files
from src.core.visualizer import draw_annotations_on_image
from src.analysis.validator import Validator, Severity
# from src.analysis.outlier_detector import OutlierDetector # Not used in this file yet but available
from src.core.ocr_engine import extract_text_from_region

# Config Injection
config = get_config()
validator = Validator(config)

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
    # DATA_DIR from config init
    return get_json_files(DATA_DIR)

# --- 2. 메인 페이지 로직 ---
def inspect_page():
    _initialize_session_state()
    _render_global_shortcuts()

    # Sidebar: Tabs
    tab_inspect, tab_file, tab_filter, tab_info = st.sidebar.tabs(["🔍 검수", "📂 파일", "⚙️ 필터", "ℹ️ 정보"])
    
    with tab_file:
        selected_file, filtered_files = _render_file_navigation_tab()
    
    if not selected_file:
        st.info("파일을 선택하세요.")
        return

    # File Change Detection
    if st.session_state.current_file != selected_file:
        st.session_state.current_file = selected_file
        st.session_state.selected_index = 0
        st.rerun()

    # Load Document
    try:
        doc = Document.from_json(selected_file)
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")
        return

    with tab_filter:
        category_filter, show_only_errors = _render_filter_tab(doc)
    
    with tab_info:
        _render_info_tab(doc, selected_file)

    # Filter Annotations
    filtered_anns, filtered_indices = _filter_annotations(doc, category_filter, show_only_errors)
    
    if not filtered_anns:
        st.warning("⚠️ 필터 조건에 맞는 어노테이션이 없습니다.")
        # But allow viewing file? No, just stop logic for visualizer
        # st.stop() # Stopping here prevents seeing the image if everything is filtered. 
        # Maybe show empty image? Let's keep behavior but warn.
        
    # Validation of generic index
    if not filtered_indices:
        current_filtered_idx = 0
        # If no anns, selected_index doesn't matter much or should be reset
    else:
        current_filtered_idx = _adjust_selected_index(st.session_state.selected_index, filtered_indices, doc)

    # Main UI
    _render_main_visual_ui(doc, filtered_anns, filtered_indices, current_filtered_idx)
    
    with tab_inspect:
        # [Moved] Page Attributes Display (Always Visible in Inspect Tab)
        if doc.page_info and "page_attribute" in doc.page_info:
            with st.expander("📄 Page Attributes", expanded=True):
                st.json(doc.page_info["page_attribute"])
        
        st.divider() # Visual separation
        
        if filtered_anns:
            _render_inspection_panel(doc, filtered_anns, filtered_indices, current_filtered_idx)
        else:
            st.info("선택된 어노테이션이 없습니다.")

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

    if st.session_state.file_index >= len(filtered_files):
        st.session_state.file_index = max(0, len(filtered_files) - 1)

    total = len(filtered_files)
    curr = st.session_state.file_index + 1
    
    progress_val = min(max(curr / total, 0.0), 1.0)
    st.progress(progress_val, text=f"파일 위치: {curr} / {total}")
    
    col_a, col_b = st.columns([3, 1])
    with col_a:
        page_num = st.number_input("페이지 번호", min_value=1, max_value=total, value=curr, step=1, key="page_jump", label_visibility="collapsed")
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
    st.caption(f"📂 {os.path.basename(selected_file)}") # basename only for cleaner UI
    return selected_file, filtered_files

# --- 4. 상세 검수 및 콘텐츠 렌더링 ---
def _render_inspection_panel(doc, filtered_anns, filtered_indices, current_filtered_idx):
    if not filtered_indices: return
    
    selected_ann = doc.layout_dets[st.session_state.selected_index]
    
    st.markdown(f"## {selected_ann.category_type}")
    


    col1, col2 = st.columns(2)
    col1.metric("📋 순서", selected_ann.order if selected_ann.order is not None else "N/A")
    col2.metric("🆔 ID", str(selected_ann.anno_id)[:8] if selected_ann.anno_id else "N/A")
    
    st.markdown("---")
    _render_content_tab(selected_ann)
    
    # OCR 검증 결과 표시
    # Config option for OCR?
    _render_ocr_validation_section(selected_ann, doc)
    
    st.markdown("### ⚙️ 속성")
    if selected_ann.attributes: st.json(selected_ann.attributes)
    
    with st.expander("✅ 검증 결과", expanded=False):
        _render_validation_tab(selected_ann, doc)

def _render_content_tab(selected_ann):
    cat = selected_ann.category_type
    attrs = selected_ann.attributes or {}
    
    # 1. 코드
    if cat == 'code_txt' and selected_ann.text:
        lang = attrs.get('text_language', 'text')
        st.markdown(f"**💻 코드** (언어: `{lang}`)")
        st.code(selected_ann.text, language=lang if lang not in ['null', None] else None)
        return

    # 2. 기본 텍스트
    if selected_ann.text and selected_ann.text.strip():
        st.markdown("**📝 텍스트**")
        st.text_area("Content", value=selected_ann.text, height=150, key=f"tx_{selected_ann.anno_id}", disabled=True, label_visibility="collapsed")
        
        # [Latex Rendering Support]
        # Check for $ (inline/block delimiters) OR \ (latex commands like \frac, \text)
        if "$" in selected_ann.text or "\\" in selected_ann.text:
            with st.expander("👁️ LaTeX 렌더링 미리보기", expanded=False):
                st.info("텍스트 내의 LaTeX 수식을 렌더링합니다.")
                
                # 1. Markdown Rendering (Supports $...$)
                st.markdown(selected_ann.text)
                
                # 2. Force Block Latex (For raw latex without $)
                if "$" not in selected_ann.text and "\\" in selected_ann.text:
                    st.caption("🔽 강제 수식 렌더링 (Block Mode)")
                    try:
                        st.latex(selected_ann.text)
                    except Exception:
                        st.warning("Raw LaTeX 렌더링 실패 (문법 오류 가능성)")
    
    # 3. LaTeX
    if selected_ann.latex:
        formula_type = attrs.get('formula_type', 'General')
        with st.expander(f"📐 LaTeX 수식 ({formula_type})", expanded=True):
            raw_latex = selected_ann.latex.strip()
            clean_latex = raw_latex.replace("$$", "").strip()
            try:
                st.latex(clean_latex)
            except Exception as e:
                st.error(f"LaTeX 렌더링 실패: {str(e)}")
            st.code(raw_latex, language="latex")
            
    # 4. HTML
    if selected_ann.html:
        type_info = ""
        if cat == 'chart':
            type_info = f"({attrs.get('chart_type', 'Chart')})"
        elif cat == 'table':
            type_info = f"({attrs.get('table_layout', 'Table')})"
            
        with st.expander(f"📊 HTML 미리보기 {type_info}", expanded=True):
            st.markdown(selected_ann.html, unsafe_allow_html=True)

# --- 5. 보조 함수들 ---
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
    if not filtered_indices:
        st.info("시각화할 항목이 없습니다.")
        return

    st.subheader(f"📍 {current_filtered_idx + 1} / {len(filtered_anns)}")
    
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

    full_image_path = os.path.join(IMAGE_DIR, doc.image_path)
    if os.path.exists(full_image_path):
        image = Image.open(full_image_path).convert("RGB")
        
        # [Visualizer Update] Relations
        relations = doc.raw_data.get("extra", {}).get("relation", [])
        selected_ann = doc.layout_dets[st.session_state.selected_index]
        
        annotated_image = draw_annotations_on_image(
            image.copy(), 
            doc.layout_dets, 
            config, # Inject Config
            highlight_indices=[st.session_state.selected_index],
            relations=relations,
            show_all_relations=st.session_state.get("show_all_relations", False),
            selected_anno_id=selected_ann.anno_id
        )
        
        # Streamlit Image Coordinates
        coords = streamlit_image_coordinates(annotated_image, key="img_m", use_column_width=True)
        
        # Interaction Logic
        if coords:
            # Need 'is_inside' logic for Annotation or Generic Poly check
            # Let's implement simple poly check here or assume it was in Document
            # Document from src.data_engine had it? Let's assume No and implement/restore it.
            # Current `Annotation` dataclass is simple. We need helper.
            # Or use shapely? Let's use simple logic for now.
            x, y = coords["x"], coords["y"]
            
            # Find clicked annotation
            # Iterate reversed to find top-most
            for i, ann in reversed(list(enumerate(doc.layout_dets))):
                if _is_point_in_poly(x, y, ann.poly):
                    if st.session_state.selected_index != i:
                        st.session_state.selected_index = i
                        st.rerun()
                    break
    else:
        st.error(f"이미지 파일을 찾을 수 없습니다: {full_image_path}")

def _is_point_in_poly(x, y, poly):
    """Simple Ray Casting algorithm for point in polygon"""
    if not poly or len(poly) < 6: return False
    # Convert [x1, y1, x2, y2] to [(x1,y1), ...]
    points = [(poly[i], poly[i+1]) for i in range(0, len(poly), 2)]
    
    inside = False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]
        xj, yj = points[j]
        
        intersect = ((yi > y) != (yj > y)) and \
                    (x < (xj - xi) * (y - yi) / (yj - yi) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside

def _render_validation_tab(selected_ann, doc):
    # Use injected validator
    val_results = validator.validate_annotation(selected_ann)
    if not val_results: st.success("이슈 없음")
    for res in val_results:
        if res.severity == Severity.ERROR: st.error(res.message)
        else: st.warning(res.message)

def _render_filter_tab(doc):
    categories = sorted(list(set([ann.category_type for ann in doc.layout_dets])))
    cat = st.selectbox("카테고리", ["전체"] + categories, key="s_cat")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        err = st.checkbox("⚠️ 검증 오류만 보기", value=st.session_state.show_only_errors, key="c_err")
    with col_f2:
        rel = st.checkbox("🔗 전체 관계 보기", value=st.session_state.get("show_all_relations", False), key="c_rel")
        
    st.session_state.show_only_errors = err
    st.session_state.show_all_relations = rel
    return cat, err

def _filter_annotations(doc, category_filter, show_only_errors):
    filtered_anns, filtered_indices = [], []
    for i, ann in enumerate(doc.layout_dets):
        if category_filter != "전체" and ann.category_type != category_filter: continue
        if show_only_errors:
            val_results = validator.validate_annotation(ann) # Use validator
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
    
    st.markdown("---")
    st.markdown("### 📄 페이지 정보 (Page Info)")
    
    if doc.page_info:
        # 1. Basic Info
        st.json(doc.page_info, expanded=True)
        
        # 2. Highlight Page Attribute if exists (User Request)
        if "page_attribute" in doc.page_info:
            st.markdown("#### ✨ Page Attributes")
            st.json(doc.page_info["page_attribute"], expanded=True)
    else:
        st.info("Page Info가 없습니다.")

# OCR Caching Logic (Simplified)
def _load_ocr_cache():
    if not os.path.exists(OCR_CACHE_FILE):
        return None
    try:
        df = pd.read_csv(OCR_CACHE_FILE)
        cache_dict = {}
        for _, row in df.iterrows():
            cache_dict[(row['filename'], row['anno_id'])] = row
        return cache_dict
    except Exception:
        return None

def _render_ocr_validation_section(selected_ann, doc):
    st.markdown("### 🤖 OCR 자동 검증")
    
    cache = _load_ocr_cache()
    cached_result = None
    current_fn = os.path.basename(doc.filename) # Document object has filename
    
    if cache and (current_fn, selected_ann.anno_id) in cache:
        cached_result = cache[(current_fn, selected_ann.anno_id)]
    
    if cached_result is not None:
        sim = float(cached_result['similarity'])
        ocr_text = str(cached_result['ocr_text'])
        
        if sim >= 0.9: st.success(f"✅ Pass (Sim: {sim:.1%})") # Magic number 0.9 -> Config?
        elif sim >= 0.7: st.warning(f"⚠️ Warning (Sim: {sim:.1%})")
        else: st.error(f"🔴 Fail (Sim: {sim:.1%})")
            
        with st.expander("🔍 OCR 상세 비교", expanded=True):
            col_a, col_b = st.columns(2)
            col_a.text_area("GT Text", value=selected_ann.text, height=100, disabled=True)
            col_b.text_area("OCR Text", value=ocr_text, height=100, disabled=True)
    else:
        st.info("⚠️ 배치 처리가 되지 않은 항목입니다.")
        if st.button("지금 OCR 실행 (1건)"):
            _run_ad_hoc_ocr(selected_ann, doc)

def _run_ad_hoc_ocr(selected_ann, doc):
    import Levenshtein
    full_image_path = os.path.join(IMAGE_DIR, doc.image_path)
    
    with st.spinner("OCR 실행 중..."):
        # Use simple OCR Engine
        ocr_text = extract_text_from_region(full_image_path, selected_ann.poly)
        
        sim = Levenshtein.ratio(selected_ann.text, ocr_text) if selected_ann.text else 0.0
        
        if sim < 0.5: st.error(f"Mismatch Critical (Sim: {sim:.2f})")
        elif sim < 0.9: st.warning(f"Mismatch Warning (Sim: {sim:.2f})")
        else: st.success(f"Pass (Sim: {sim:.2f})")
        
        st.text_area("Extracted", value=ocr_text)

if __name__ == "__main__":
    inspect_page()