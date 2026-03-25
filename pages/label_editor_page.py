"""
Streamlit 라벨링 수정 페이지 (Label Editor)
"""
import streamlit as st

# Workaround for streamlit-drawable-canvas on Streamlit >= 1.34
import streamlit.elements.image as st_image
if not hasattr(st_image, 'image_to_url'):
    try:
        from streamlit.elements.lib.image_utils import image_to_url as new_image_to_url
        def patched_image_to_url(image, width, clamp, channels, output_format, image_id):
            class MockLayoutConfig:
                def __init__(self, w):
                    self.width = w
                    self.use_column_width = False
            return new_image_to_url(image, MockLayoutConfig(width) if isinstance(width, int) else width, clamp, channels, output_format, image_id)
        st_image.image_to_url = patched_image_to_url
    except ImportError:
        pass

import os
import json
import ast
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates
from streamlit_drawable_canvas import st_canvas

try:
    import streamlit_shortcuts as ss
    SHORTCUTS_AVAILABLE = True
except ImportError:
    SHORTCUTS_AVAILABLE = False

from src.config import get_config, DATA_DIR, IMAGE_DIR
from src.core.models import Document, get_json_files
from src.core.visualizer import draw_annotations_on_image

config = get_config()

def _initialize_session_state():
    if "ed_file_index" not in st.session_state:
        st.session_state.ed_file_index = 0
    if "ed_selected_index" not in st.session_state:
        st.session_state.ed_selected_index = 0
    if "ed_current_file" not in st.session_state:
        st.session_state.ed_current_file = None
    if "ed_canvas_mode" not in st.session_state:
        st.session_state.ed_canvas_mode = False
    if "ed_temp_poly" not in st.session_state:
        st.session_state.ed_temp_poly = None
    if "ed_draw_tool" not in st.session_state:
        st.session_state.ed_draw_tool = "transform"

@st.cache_data
def get_cached_files():
    return get_json_files(DATA_DIR)

def _is_point_in_poly(x, y, poly):
    if not poly or len(poly) < 6: return False
    points = [(poly[i], poly[i+1]) for i in range(0, len(poly), 2)]
    inside = False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]
        xj, yj = points[j]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside

def label_editor_page():
    _initialize_session_state()
    
    # ── Sidebar: File Navigation ──
    st.sidebar.title("📁 라벨링 파일 선택")
    json_files = get_cached_files()
    
    if not json_files:
        st.warning("데이터 파일이 없습니다.")
        return
        
    search_query = st.sidebar.text_input("🔍 파일 검색")
    filtered_files = [f for f in json_files if search_query.lower() in os.path.basename(f).lower()] if search_query else json_files
    
    if not filtered_files:
        st.sidebar.warning("검색 결과가 없습니다.")
        return
        
    if st.session_state.ed_file_index >= len(filtered_files):
        st.session_state.ed_file_index = max(0, len(filtered_files) - 1)
        
    total = len(filtered_files)
    curr = st.session_state.ed_file_index + 1
    
    st.sidebar.progress(curr / total, text=f"위치: {curr} / {total}")
    
    colA, colB = st.sidebar.columns(2)
    if colA.button("⏪ 이전", use_container_width=True, key="ed_prev_file"):
        if st.session_state.ed_file_index > 0:
            st.session_state.ed_file_index -= 1
            st.session_state.ed_canvas_mode = False
            st.session_state.ed_temp_poly = None
            st.rerun()
    if colB.button("다음 ⏩", use_container_width=True, key="ed_next_file"):
        if st.session_state.ed_file_index < len(filtered_files) - 1:
            st.session_state.ed_file_index += 1
            st.session_state.ed_canvas_mode = False
            st.session_state.ed_temp_poly = None
            st.rerun()
            
    selected_file = filtered_files[st.session_state.ed_file_index]
    st.sidebar.caption(f"📂 {os.path.basename(selected_file)}")
    
    # ── Document Load ──
    if st.session_state.ed_current_file != selected_file:
        st.session_state.ed_current_file = selected_file
        st.session_state.ed_selected_index = 0
        st.session_state.ed_canvas_mode = False
        st.session_state.ed_temp_poly = None
        
    try:
        doc = Document.from_json(selected_file)
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")
        return
        
    st.title("✏️ 라벨링 에디터 (Label Editor)")
    
    if not doc.layout_dets:
        st.info("어노테이션이 없습니다.")
        return
        
    if st.session_state.ed_selected_index >= len(doc.layout_dets):
        st.session_state.ed_selected_index = 0
        
    selected_ann = doc.layout_dets[st.session_state.ed_selected_index]
    
    # ── Main Layout: 좌우 분할 ──
    col_img, col_form = st.columns([2, 1])
    
    with col_img:
        _render_image_view(doc, selected_ann)
        
    with col_form:
        _render_editor_form(doc, selected_ann)

def _render_image_view(doc, selected_ann):
    st.markdown("### 🖼️ 시각화 영역")
    full_image_path = os.path.join(IMAGE_DIR, doc.image_path)
    if os.path.exists(full_image_path):
        image = Image.open(full_image_path).convert("RGB")
        relations = doc.raw_data.get("extra", {}).get("relation", [])
        
        if not st.session_state.ed_canvas_mode:
            annotated_image = draw_annotations_on_image(
                image.copy(), 
                doc.layout_dets, 
                config,
                highlight_indices=[st.session_state.ed_selected_index],
                relations=relations,
                show_all_relations=False,
                selected_anno_id=selected_ann.anno_id
            )
            coords = streamlit_image_coordinates(annotated_image, key=f"ed_img_{st.session_state.ed_file_index}_{st.session_state.ed_selected_index}", use_column_width=True)
            if coords:
                x, y = coords["x"], coords["y"]
                for i, ann in reversed(list(enumerate(doc.layout_dets))):
                    if _is_point_in_poly(x, y, ann.poly):
                        if st.session_state.ed_selected_index != i:
                            st.session_state.ed_selected_index = i
                            st.rerun()
                        break
        else:
            # 캔버스 모드
            st.warning("🖌️ **BBox 편집 모드 활성화됨**. 마우스를 드래그하여 영역을 선택하거나 줄이세요.")
            
            # Draw bg without selected rect to not overlap if drawing over it
            other_anns = [a for i, a in enumerate(doc.layout_dets) if i != st.session_state.ed_selected_index]
            bg_image = draw_annotations_on_image(
                image.copy(), 
                other_anns, 
                config,
                highlight_indices=[],
                relations=[],
                show_all_relations=False
            )
            
            initial_drawing = {"version": "4.4.0", "objects": []}
            if selected_ann.poly and len(selected_ann.poly) >= 8:
                xs = selected_ann.poly[0::2]
                ys = selected_ann.poly[1::2]
                left = min(xs)
                top = min(ys)
                width = max(xs) - left
                height = max(ys) - top
                initial_drawing["objects"].append({
                    "type": "rect",
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "fill": "rgba(255, 165, 0, 0.3)",
                    "stroke": "#ff0000",
                    "strokeWidth": 2,
                    "transparentCorners": False
                })
            
            draw_tool = st.session_state.get("ed_draw_tool", "transform")
            
            canvas_result = st_canvas(
                fill_color="rgba(255, 165, 0, 0.3)",
                stroke_width=2,
                stroke_color="#ff0000",
                background_image=bg_image,
                update_streamlit=True,
                height=bg_image.height,
                width=bg_image.width,
                drawing_mode=draw_tool,
                initial_drawing=initial_drawing if draw_tool == "transform" else None,
                key=f"ed_canvas_{st.session_state.ed_selected_index}_{draw_tool}",
            )
            
            if canvas_result.json_data is not None:
                objs = canvas_result.json_data["objects"]
                if len(objs) > 0:
                    last_obj = objs[-1]
                    left = last_obj.get("left", 0)
                    top = last_obj.get("top", 0)
                    width = last_obj.get("width", 0) * last_obj.get("scaleX", 1)
                    height = last_obj.get("height", 0) * last_obj.get("scaleY", 1)
                    new_poly = [float(left), float(top), float(left + width), float(top), float(left + width), float(top + height), float(left), float(top + height)]
                    
                    new_poly_str = str(new_poly)
                    if st.session_state.ed_temp_poly != new_poly_str:
                        st.session_state.ed_temp_poly = new_poly_str
                        st.session_state[f"poly_{selected_ann.anno_id}"] = new_poly_str
                        st.rerun()

    else:
        st.error(f"이미지를 찾을 수 없습니다: {full_image_path}")

def _render_editor_form(doc, selected_ann):
    st.markdown(f"### 📝 속성 수정 (ID: {selected_ann.anno_id})")
    
    # ── 빠른 객체 이동 ──
    col_q1, col_q2, col_q3 = st.columns([2, 1, 1])
    with col_q1:
        jump_val = st.number_input("이동할 ID / Order 번호", value=0, min_value=0, label_visibility="collapsed", key="jump_val", help="이동할 번호를 입력하세요.")
    with col_q2:
        if st.button("ID로 이동", use_container_width=True, key="btn_jump_id"):
            target_idx = next((i for i, a in enumerate(doc.layout_dets) if a.anno_id == int(jump_val)), None)
            if target_idx is not None:
                st.session_state.ed_selected_index = target_idx
                st.session_state.ed_canvas_mode = False
                st.session_state.ed_temp_poly = None
                st.rerun()
            else:
                st.error(f"ID가 {jump_val}인 객체를 찾을 수 없습니다.")
    with col_q3:
        if st.button("Order 이동", use_container_width=True, key="btn_jump_order"):
            target_idx = next((i for i, a in enumerate(doc.layout_dets) if a.order == int(jump_val)), None)
            if target_idx is not None:
                st.session_state.ed_selected_index = target_idx
                st.session_state.ed_canvas_mode = False
                st.session_state.ed_temp_poly = None
                st.rerun()
            else:
                st.error(f"Order가 {jump_val}인 객체를 찾을 수 없습니다.")

    # 내비게이션 버튼 추가
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("⬅️ 이전 객체 (순번)", use_container_width=True, key="btn_prev_ann"):
            if st.session_state.ed_selected_index > 0:
                st.session_state.ed_selected_index -= 1
                st.session_state.ed_canvas_mode = False
                st.session_state.ed_temp_poly = None
                st.rerun()
    with col_nav2:
        if st.button("다음 객체 (순번) ➡️", use_container_width=True, key="btn_next_ann"):
            if st.session_state.ed_selected_index < len(doc.layout_dets) - 1:
                st.session_state.ed_selected_index += 1
                st.session_state.ed_canvas_mode = False
                st.session_state.ed_temp_poly = None
                st.rerun()
    
    st.markdown("---")
    
    # UI Elements based on annotation attributes
    categories = sorted(list(set([ann.category_type for ann in doc.layout_dets] + ["text_block", "figure", "table", "header", "footer", "page_number", "equation", "chart"])))
    if selected_ann.category_type not in categories:
        categories.append(selected_ann.category_type)
        
    new_cat = st.selectbox("카테고리 (Category)", categories, index=categories.index(selected_ann.category_type), key=f"cat_{selected_ann.anno_id}")
    
    new_text = st.text_area("텍스트 (Text)", value=selected_ann.text if selected_ann.text else "", height=100, key=f"txt_{selected_ann.anno_id}")
    new_latex = st.text_area("LaTeX", value=selected_ann.latex if selected_ann.latex else "", height=100, key=f"lat_{selected_ann.anno_id}")
    new_html = st.text_area("HTML", value=selected_ann.html if selected_ann.html else "", height=100, key=f"htm_{selected_ann.anno_id}")
    
    # BBox coordinates
    poly_key = f"poly_{selected_ann.anno_id}"
    if poly_key not in st.session_state:
        st.session_state[poly_key] = str(selected_ann.poly)
        
    new_poly_str = st.text_input("바운딩 박스 BBox (poly)", key=poly_key, help="float 리스트 형태로 입력하세요.")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.session_state.ed_canvas_mode:
            if st.button("✅ 선택 완료 (닫기)", use_container_width=True, key=f"done_{selected_ann.anno_id}"):
                st.session_state.ed_canvas_mode = False
                st.rerun()
            draw_tool = st.selectbox("캔버스 도구", ["transform", "rect"], index=0 if st.session_state.get("ed_draw_tool") != "rect" else 1, key="sel_tool")
            if draw_tool != st.session_state.get("ed_draw_tool"):
                st.session_state.ed_draw_tool = draw_tool
                st.rerun()
        else:
            if st.button("✏️ 마우스로 BBox 그리기/수정", use_container_width=True, key=f"draw_{selected_ann.anno_id}"):
                st.session_state.ed_canvas_mode = True
                st.session_state.ed_temp_poly = str(selected_ann.poly)
                st.rerun()
                
    col1, col2 = st.columns(2)
    with col1:
        new_order_val = selected_ann.order if selected_ann.order is not None else 0
        new_order = st.number_input("순서 (Order)", value=int(new_order_val) if new_order_val else 0, step=1, key=f"ord_{selected_ann.anno_id}")
    with col2:
        new_ignore = st.checkbox("무시 (Ignore)", value=selected_ann.ignore, key=f"ign_{selected_ann.anno_id}")
    
    # sub_regions 관리
    existing_sub_regions = selected_ann.raw_data.get("sub_regions", [])
    if selected_ann.category_type in ["figure", "table", "chart", "equation"] or existing_sub_regions:
        st.markdown("#### 📂 Sub Regions")
        st.caption(f"현재 {len(existing_sub_regions)} 개의 서브 리전이 있습니다.")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("➕ 신규 Text Block", use_container_width=True, key=f"add_sub_{selected_ann.anno_id}"):
                max_id = max([a.anno_id for a in doc.layout_dets] + [0])
                for d in doc.layout_dets:
                    for sr in d.raw_data.get("sub_regions", []):
                        if hasattr(sr, 'get') and sr.get("anno_id", 0) > max_id:
                            max_id = sr.get("anno_id", 0)
                            
                new_id = max_id + 1
                new_sub = {
                    "category_type": "text_block",
                    "poly": selected_ann.poly, 
                    "ignore": False,
                    "order": None,
                    "anno_id": new_id,
                    "text": "신규 텍스트 블록",
                    "attribute": {
                        "text_background": False,
                        "text_rotate": "normal",
                        "text_language": "ko"
                    },
                    "type": "text_area",
                    "region_poly": selected_ann.poly
                }
                if "sub_regions" not in selected_ann.raw_data:
                    selected_ann.raw_data["sub_regions"] = []
                selected_ann.raw_data["sub_regions"].append(new_sub)
                
                # 루트 생성 (K-Omnidoc 규격)
                from src.core.models import Annotation
                new_ann = Annotation.from_dict(new_sub)
                doc.layout_dets.append(new_ann)
                
                # Relation 연동
                if "extra" not in doc.raw_data:
                    doc.raw_data["extra"] = {}
                if "relation" not in doc.raw_data["extra"]:
                    doc.raw_data["extra"]["relation"] = []
                # 중복 방지
                if not any(r.get("source_anno_id") == selected_ann.anno_id and r.get("target_anno_id") == new_id for r in doc.raw_data["extra"]["relation"]):
                    doc.raw_data["extra"]["relation"].append({
                        "source_anno_id": selected_ann.anno_id,
                        "target_anno_id": new_id,
                        "relation_type": "parent_son"
                    })
                
                doc.save()
                st.toast("✅ 신규 텍스트 블록 생성 완료!")
                st.rerun()

        with col_s2:
            st.markdown("**⬇️ 기존 객체 가져오기 (이동)**")
            other_anns = [a for a in doc.layout_dets if a.anno_id != selected_ann.anno_id]
            options = {str(a.anno_id): f"[{a.anno_id}] {a.category_type}" + (f" ({str(a.text)[:10]}...)" if a.text else "") for a in other_anns}
            
            selected_to_add = st.selectbox(
                "편입할 객체 선택", 
                options=[""] + list(options.keys()), 
                format_func=lambda x: "객체 선택..." if x == "" else options[x],
                key=f"sel_sub_{selected_ann.anno_id}",
                label_visibility="collapsed"
            )
            
            if selected_to_add != "" and st.button("적용 (현재 영역으로 이동)", use_container_width=True, key=f"move_sub_{selected_ann.anno_id}"):
                child_ann = next((a for a in doc.layout_dets if str(a.anno_id) == selected_to_add), None)
                if child_ann:
                    if "sub_regions" not in selected_ann.raw_data:
                        selected_ann.raw_data["sub_regions"] = []
                    
                    child_dict = child_ann.to_dict()
                    
                    # 서브 리전 전용 포맷 추가 (호환성 목적)
                    if "type" not in child_dict:
                        child_dict["type"] = "text_area"
                    if "region_poly" not in child_dict:
                        child_dict["region_poly"] = child_dict.get("poly", [])
                        
                    selected_ann.raw_data["sub_regions"].append(child_dict)
                    
                    # 주의: doc.layout_dets.remove(child_ann) 제거 (루트에 유지되어야 함)
                    
                    # Relation 연동
                    if "extra" not in doc.raw_data:
                        doc.raw_data["extra"] = {}
                    if "relation" not in doc.raw_data["extra"]:
                        doc.raw_data["extra"]["relation"] = []
                    # 중복 방지
                    if not any(r.get("source_anno_id") == selected_ann.anno_id and r.get("target_anno_id") == child_ann.anno_id for r in doc.raw_data["extra"]["relation"]):
                        doc.raw_data["extra"]["relation"].append({
                            "source_anno_id": selected_ann.anno_id,
                            "target_anno_id": child_ann.anno_id,
                            "relation_type": "parent_son"
                        })
                    
                    doc.save()
                    
                    new_idx = doc.layout_dets.index(selected_ann) if selected_ann in doc.layout_dets else 0
                    st.session_state.ed_selected_index = new_idx
                    
                    st.toast(f"✅ ID {selected_to_add} 객체가 내부로 이동되었습니다.")
                    st.rerun()

    st.markdown("---")
    
    if st.button("💾 변경사항 저장", type="primary", use_container_width=True, key=f"save_{selected_ann.anno_id}"):
        try:
            # Update attributes
            selected_ann.category_type = new_cat
            selected_ann.text = new_text if new_text else None
            selected_ann.latex = new_latex if new_latex else None
            selected_ann.html = new_html if new_html else None
            selected_ann.order = new_order
            selected_ann.ignore = new_ignore
            
            # Poly parsing
            try:
                parsed_poly = ast.literal_eval(new_poly_str)
                if isinstance(parsed_poly, list):
                    selected_ann.poly = parsed_poly
                else:
                    st.error("BBox는 리스트 형태여야 합니다.")
                    return
            except Exception as e:
                st.error(f"BBox 파싱 오류: {e}")
                return
                
            doc.save()
            st.session_state.ed_canvas_mode = False
            st.session_state.ed_temp_poly = None
            st.success("✅ 저장이 성공적으로 완료되었습니다!")
            st.rerun()
            
        except Exception as e:
            st.error(f"저장 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    label_editor_page()
