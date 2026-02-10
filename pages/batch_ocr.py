import streamlit as st
import os
import pandas as pd
import time
from src.config import get_config, DATA_DIR, IMAGE_DIR, OCR_CACHE_FILE
from src.core.models import Document, get_json_files
from src.core.ocr_engine import (
    extract_text_hybrid, 
    calculate_text_similarity, 
    get_ocr_engine
)

# Config
config = get_config()
# Ensure cache dir exists
BATCH_CACHE_FILE = OCR_CACHE_FILE

def ensure_cache_dir():
    cache_dir = os.path.dirname(BATCH_CACHE_FILE)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

def batch_ocr_page():
    st.title("🚀 OCR 일괄 처리 (Batch Processing)")
    st.markdown("""
    이 페이지에서는 전체 문서에 대해 OCR을 미리 실행하고 결과를 저장합니다.
    **검수 페이지(Inspect Page)**에서 매번 OCR을 돌리는 대기 시간을 없애기 위함입니다.
    
    *   **현재 모드**: EasyOCR 단일 사용 (Fast)
    *   **참고**: DotsOCR 기능은 제거되었습니다.
    """)
    
    ensure_cache_dir()
    cache_exists = os.path.exists(BATCH_CACHE_FILE)
    
    if cache_exists:
        try:
            df = pd.read_csv(BATCH_CACHE_FILE)
            st.success(f"✅ 기존 캐시 파일 발견: {len(df)}개 레코드")
            st.dataframe(df.head())
        except Exception:
            st.warning("⚠️ 캐시 파일이 손상되었습니다.")

    if st.button("▶️ 일괄 처리 시작"):
        _run_batch_process()

def _run_batch_process():
    # get_json_files returns full paths
    full_paths = get_json_files(DATA_DIR)
    if not full_paths:
        st.error("처리할 파일이 없습니다.")
        return

    with st.spinner("엔진 초기화 중..."):
        _ = get_ocr_engine()
        # DotsOCR removed

    total_files = len(full_paths)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    start_time = time.time()
    
    for i, file_path in enumerate(full_paths):
        filename = os.path.basename(file_path)
        status_text.text(f"처리 중 ({i+1}/{total_files}): {filename}")
        progress_bar.progress((i + 1) / total_files)
        
        try:
            doc = Document.from_json(file_path)
            full_image_path = os.path.join(IMAGE_DIR, doc.image_path)
            
            # Optimized Image Loading
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            
            try:
                pil_image = Image.open(full_image_path)
                pil_image.load()
            except Exception as e:
                print(f"Error loading image {filename}: {e}")
                continue

            processed_count = 0
            for ann in doc.layout_dets:
                gt_text = ann.text
                if not gt_text or not gt_text.strip():
                    continue
                    
                ocr_text = extract_text_hybrid(pil_image, ann.poly, ann.category_type)
                sim = calculate_text_similarity(gt_text, ocr_text)
                
                results.append({
                    "filename": filename,
                    "anno_id": ann.anno_id,
                    "category": ann.category_type,
                    "gt_text": gt_text,
                    "ocr_text": ocr_text,
                    "similarity": sim,
                    "timestamp": time.time()
                })
                processed_count += 1
                
        except Exception as e:
            st.warning(f"파일 처리 실패 {filename}: {e}")
            
    end_time = time.time()
    elapsed = end_time - start_time
    
    df = pd.DataFrame(results)
    df.to_csv(BATCH_CACHE_FILE, index=False)
    
    st.success(f"✅ 처리가 완료되었습니다! (총 {len(results)}개, 소요시간: {elapsed:.1f}초)")
    st.dataframe(df)

if __name__ == "__main__":
    batch_ocr_page()
