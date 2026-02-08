"""
PaddleOCR 기반 텍스트 추출 및 검증 유틸리티 (EasyOCR로 교체됨)

이 모듈은 EasyOCR을 사용하여 이미지에서 텍스트를 추출하고,
어노테이션 텍스트와 비교하여 오타를 감지하는 기능을 제공합니다.
PaddleOCR의 PIR/OneDNN 백엔드 호환성 문제로 인해 EasyOCR로 마이그레이션되었습니다.
"""

import os
import logging
from typing import List, Tuple, Dict, Any, Optional
import streamlit as st
from PIL import Image
import Levenshtein
import easyocr
import numpy as np
import numpy as np

# 로거 설정
logger = logging.getLogger(__name__)

# 전역 설정
# 전역 설정
OCR_AVAILABLE = True
DOTS_OCR_AVAILABLE = False  # transformers 설치 여부 확인 후 True로 변경됨

try:
    import torch
    from transformers import AutoModel, AutoTokenizer
    DOTS_OCR_AVAILABLE = True
except ImportError:
    DOTS_OCR_AVAILABLE = False


@st.cache_resource
def get_ocr_engine() -> Optional[easyocr.Reader]:
    """EasyOCR (Fast Lane) - 단순 텍스트용"""
    try:
        import torch
        use_gpu = torch.cuda.is_available()
        # CPU에서는 verbose=False로 설정하여 로그 최소화
        reader = easyocr.Reader(['ko', 'en'], gpu=use_gpu, verbose=False)
        return reader
    except Exception as e:
        logger.error(f"❌ EasyOCR 초기화 실패: {str(e)}")
        return None


@st.cache_resource
def get_dots_model():
    """dots.ocr (Smart Lane) - 표/수식용 (1.7B VLM)"""
    if not DOTS_OCR_AVAILABLE:
        return None
    
    try:
        import os
        use_gpu = torch.cuda.is_available()
        force_cpu = os.environ.get("FORCE_DOTS_CPU", "0") == "1"
        
        # CPU 환경에서는 dots.ocr 비활성화 (권장) - 너무 느림
        if not use_gpu and not force_cpu:
            logger.warning("⚠️ CPU 환경에서는 dots.ocr이 너무 느려 비활성화됩니다. (GPU 필요)\n💡 테스트하려면 환경변수 `FORCE_DOTS_CPU=1`을 설정하세요.")
            return None

        logger.info("dots.ocr 모델 로딩 중... (GPU)")
        # 실제 모델 경로는 huggingface hub ID 또는 로컬 경로
        model_id = "rednote-hilab/dots-ocr-1.7b" 
        
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        model = AutoModel.from_pretrained(model_id, trust_remote_code=True, device_map='cuda' if use_gpu else 'cpu')
        
        return {"model": model, "tokenizer": tokenizer}
    except Exception as e:
        logger.error(f"❌ dots.ocr 로딩 실패 (무시됨): {str(e)}")
        return None


def extract_text_hybrid(
    image_source: Any, 
    bbox: List[int], 
    category: str
) -> str:
    """
    하이브리드 추출 전략:
    - 단순 텍스트/코드 -> EasyOCR (Fast)
    - 표/수식 -> dots.ocr (Smart) -> 실패 시 EasyOCR fallback
    """
    # 1. Fast Lane (EasyOCR)
    fast_categories = ['text_block', 'code_txt', 'title', 'caption']
    
    # 표/수식이 아니거나, dots.ocr이 없을 때
    if category in fast_categories or not DOTS_OCR_AVAILABLE:
        return extract_text_from_region(image_source, bbox, get_ocr_engine())
        
    # 2. Smart Lane (dots.ocr)
    dots = get_dots_model()
    if dots:
        # TODO: dots.ocr 추론 구현 (현재는 placeholder)
        # return infer_dots_ocr(dots, image_path, bbox)
        pass
        
    # Fallback to EasyOCR
    return extract_text_from_region(image_path, bbox, get_ocr_engine())

# 기존 함수 유지 (하위 호환성)
def extract_text_from_region(
    image_source: Any,  # str or Image.Image or np.ndarray
    bbox: List[int],
    _ocr_engine: Optional[easyocr.Reader] = None
) -> str:
    """
    이미지의 특정 영역에서 텍스트를 추출합니다.
    
    Args:
        image_source: 이미지 파일 경로(str) 또는 PIL.Image 객체
        bbox: [x1, y1, x2, y2] 형태의 바운딩 박스 (또는 Polygon)
        _ocr_engine: EasyOCR Reader 인스턴스 (easyocr.Reader)
    
    Returns:
        추출된 텍스트 (공백으로 연결)
    """
    if _ocr_engine is None: _ocr_engine = get_ocr_engine()
    if _ocr_engine is None:
        logger.warning("OCR 엔진이 없습니다.")
        return ""
    
    try:
        # 이미지 소스 처리
        if isinstance(image_source, str):
            if not os.path.exists(image_source):
                logger.warning(f"이미지 파일 없음: {image_source}")
                return ""
            image = Image.open(image_source)
        elif isinstance(image_source, Image.Image):
            image = image_source
        elif isinstance(image_source, np.ndarray):
            image = Image.fromarray(image_source)
        else:
            logger.warning(f"지원되지 않는 이미지 타입: {type(image_source)}")
            return ""
        
        # BBox 변환 (Polygon인 경우)
        if len(bbox) >= 6:
            xs = [bbox[i] for i in range(0, len(bbox), 2)]
            ys = [bbox[i] for i in range(1, len(bbox), 2)]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        elif len(bbox) == 4:
            x1, y1, x2, y2 = bbox
        else:
            logger.error(f"유효하지 않은 bbox 형태: {bbox}")
            return ""
            
        width, height = image.size
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
        
        if x2 <= x1 or y2 <= y1: return ""
            
        cropped = image.crop((x1, y1, x2, y2))
        cropped_np = np.array(cropped)
        
        # EasyOCR 실행
        result = _ocr_engine.readtext(cropped_np, detail=0)
        return " ".join(result)
    except Exception as e:
        logger.error(f"❌ OCR 예외 발생: {str(e)}")
        print(f"DEBUG: OCR Exception - {str(e)}") # 터미널 출력 추가
        return ""

def calculate_text_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2: return 0.0
    text1, text2 = " ".join(text1.split()), " ".join(text2.split())
    dist = Levenshtein.distance(text1, text2)
    maxlen = max(len(text1), len(text2))
    return 1.0 - (dist / maxlen) if maxlen > 0 else 1.0

def calculate_levenshtein_distance(text1: str, text2: str) -> int:
    return Levenshtein.distance(text1, text2)

# Stubbed functions
def get_structure_engine(): return None
def extract_table_structure(*args): return None
def parse_table_html(*args): return {'rows': 0, 'cols': 0}

