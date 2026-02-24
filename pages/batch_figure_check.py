import streamlit as st
import os
import time
from PIL import Image

from src.config import get_config, DATA_DIR, IMAGE_DIR
from src.core.models import Document, get_json_files
from src.analysis.validator import Validator

# Config Setup
config = get_config()
validator = Validator(config)

def _show_batch_cropped_error(doc, parent_id, child_id):
    parent_ann = next((a for a in doc.layout_dets if a.anno_id == parent_id), None)
    child_ann = next((a for a in doc.layout_dets if a.anno_id == child_id), None)
    
    if not parent_ann or not child_ann:
        return
        
    full_image_path = os.path.join(IMAGE_DIR, doc.image_path)
    if os.path.exists(full_image_path):
        from src.core.visualizer import draw_annotations_on_image
        image = Image.open(full_image_path).convert("RGB")
        
        p_poly = parent_ann.poly
        min_x = max(0, min(p_poly[0::2]) - 50)
        min_y = max(0, min(p_poly[1::2]) - 50)
        max_x = min(image.width, max(p_poly[0::2]) + 50)
        max_y = min(image.height, max(p_poly[1::2]) + 50)
        
        annotated_image = draw_annotations_on_image(
            image.copy(), 
            [parent_ann, child_ann], 
            config,
            highlight_indices=[0, 1] 
        )
        
        cropped_image = annotated_image.crop((min_x, min_y, max_x, max_y))
        st.image(cropped_image, caption=f"결함 영역 크롭 (Figure ID: {parent_id}, 누락 요소 ID: {child_id})", use_column_width=True)
    else:
        st.error(f"이미지 파일을 찾을 수 없습니다: {full_image_path}")

def batch_figure_page():
    st.title("🗂️ Batch Figure Check")
    st.markdown("""
    데이터셋 전체를 스캔하여 **Figure 내부 요소의 종속(sub_regions) 누락 에러**를 일괄 검증합니다.
    """)
    
    if "batch_results" not in st.session_state:
        st.session_state.batch_results = None
    
    files = get_json_files(DATA_DIR)
    
    st.info(f"📂 스캔 대기 중인 문서: 총 {len(files)}개")
    
    if st.button("🚀 배치 일괄 검증 시작", type="primary"):
        st.session_state.batch_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_files = len(files)
        error_count = 0
        
        for i, file_path in enumerate(files):
            try:
                doc = Document.from_json(file_path)
                val_results = validator.validate_document(doc)
                
                missing_deps = [res for res in val_results if res.rule_id == "missing_figure_dependency"]
                if missing_deps:
                    error_count += len(missing_deps)
                    st.session_state.batch_results.append({
                        "file_path": file_path,
                        "doc": doc,
                        "errors": missing_deps
                    })
            except Exception as e:
                pass
                
            # 진행률 업데이트
            progress = (i + 1) / total_files
            progress_bar.progress(progress)
            status_text.text(f"진행 중... ({i+1}/{total_files}) - 발견된 누락 에러: {error_count}건")
            
        status_text.success(f"✅ 검증 완료! (총 탐색: {total_files}개 문서 | 발견된 에러: {error_count}건)")
        
    # 결과 표출 UI
    if st.session_state.batch_results is not None:
        if len(st.session_state.batch_results) == 0:
            st.success("🎉 모든 문서가 검증을 통과했습니다. (누락 에러 없음)")
        else:
            st.warning(f"🚨 총 {len(st.session_state.batch_results)}개의 문서에서 에러가 발견되었습니다.")
            
            for doc_idx, result in enumerate(st.session_state.batch_results):
                file_name = os.path.basename(result["file_path"])
                errors = result["errors"]
                doc = result["doc"]
                
                with st.expander(f"📄 {file_name} (에러 {len(errors)}건)", expanded=False):
                    for err_idx, error in enumerate(errors):
                        st.markdown(f"**- {error.message}**")
                        parent_id = error.details["parent_id"]
                        child_id = error.details["child_id"]
                        
                        btn_key = f"batch_crop_{doc_idx}_{err_idx}_{parent_id}_{child_id}"
                        if st.button(f"🖼️ 위반 영역(Figure) 크롭 보기", key=btn_key):
                            _show_batch_cropped_error(doc, parent_id, child_id)
                    st.divider()

if __name__ == "__main__":
    batch_figure_page()
