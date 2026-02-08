import streamlit as st
import os
import pandas as pd
import time
from src import config
from src.data_engine import get_json_files, load_document, Document
from src.analysis_engine import extract_text_hybrid, calculate_text_similarity, get_ocr_engine, get_dots_model

# Force reload configs
import importlib
importlib.reload(config)

# Use the constant from config.py
# If imported config does not have it yet (runtime issue), fallback or reload
if not hasattr(config, 'OCR_CACHE_FILE'):
    BATCH_CACHE_FILE = os.path.join(config.PROJECT_ROOT, ".ocr_cache", "batch_ocr_results.csv")
else:
    BATCH_CACHE_FILE = config.OCR_CACHE_FILE

def ensure_cache_dir():
    cache_dir = os.path.dirname(BATCH_CACHE_FILE)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

def batch_ocr_page():
    st.title("🚀 OCR 일괄 처리 (Batch Processing)")
    st.markdown("""
    이 페이지에서는 전체 문서에 대해 OCR을 미리 실행하고 결과를 저장합니다.
    **검수 페이지(Inspect Page)**에서 매번 OCR을 돌리는 대기 시간을 없애기 위함입니다.
    
    *   **CPU 환경**: EasyOCR만 사용 (빠름)
    *   **GPU 환경 + `sys.dots_ocr`**: Hybrid 모드 (속도/성능 균형)
    *   **FORCE_DOTS_CPU=1**: CPU에서도 강제 실행 (매우 느림)
    """)
    
    # 캐시 상태 확인
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
    files = get_json_files()
    if not files:
        st.error("처리할 파일이 없습니다.")
        return

    # 엔진 초기화 (강제 로딩)
    with st.spinner("엔진 초기화 중..."):
        _ = get_ocr_engine()
        _ = get_dots_model()

    total_files = len(files)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    
    start_time = time.time()
    
    for i, file_path in enumerate(files):
        filename = os.path.basename(file_path)
        status_text.text(f"처리 중 ({i+1}/{total_files}): {filename}")
        progress_bar.progress((i + 1) / total_files)
        
        try:
            doc = load_document(file_path)
            full_image_path = os.path.join(config.IMAGE_DIR, doc.image_path)
            
            # [최적화] 대용량 이미지 1회 로딩
            print(f"Processing File: {filename}") # 터미널 로그
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None  # DecompressionBombWarning 해제
            
            try:
                pil_image = Image.open(full_image_path)
                pil_image.load() # 강제 로딩
            except Exception as e:
                print(f"Error loading image {filename}: {e}")
                continue

            # Hybrid extraction handles filtering logic internally, 
            # but we iterate over layout_dets
            processed_count = 0
            for ann in doc.layout_dets:
                # 텍스트 있는 것만 처리
                gt_text = ann.text
                if not gt_text or not gt_text.strip():
                    continue
                    
                # Hybrid OCR 추출 (이미지 객체 전달)
                # 터미널 로그 (디버깅용)
                # print(f"  - [{ann.category_type}] ID:{ann.anno_id} Processing...") 
                
                ocr_text = extract_text_hybrid(pil_image, ann.poly, ann.category_type)
                
                # 유사도 계산
                sim = calculate_text_similarity(gt_text, ocr_text)
                
                print(f"  - ID:{ann.anno_id} | GT:{len(gt_text)} chars | OCR:{len(ocr_text)} chars | Sim:{sim:.2f}")
                
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
            
            print(f"Done {filename}: {processed_count} annotations processed.")
                
        except Exception as e:
            st.warning(f"파일 처리 실패 {filename}: {e}")
            
    end_time = time.time()
    elapsed = end_time - start_time
    
    # 저장
    df = pd.DataFrame(results)
    df.to_csv(BATCH_CACHE_FILE, index=False)
    
    st.success(f"✅ 처리가 완료되었습니다! (총 {len(results)}개, 소요시간: {elapsed:.1f}초)")
    st.dataframe(df)

if __name__ == "__main__":
    batch_ocr_page()
