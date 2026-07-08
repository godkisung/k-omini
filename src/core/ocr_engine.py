import os
import easyocr
import logging
from typing import Optional, Any
import numpy as np
from PIL import Image, ImageOps
import streamlit as st
import tempfile
import torch
import Levenshtein

logger = logging.getLogger(__name__)

@st.cache_resource
def get_ocr_engine() -> Optional[easyocr.Reader]:
    """EasyOCR (Fast Lane) - 단순 텍스트용"""
    try:
        use_gpu = torch.cuda.is_available()
        reader = easyocr.Reader(['ko', 'en'], gpu=use_gpu, verbose=False)
        return reader
    except Exception as e:
        logger.error(f"❌ EasyOCR 초기화 실패: {str(e)}")
        return None

def extract_text_from_region(
    image_source: Any,
    bbox: list,
    _ocr_engine: Optional[easyocr.Reader] = None
) -> str:
    """이미지의 특정 영역에서 텍스트를 추출합니다 (EasyOCR 사용)."""
    if _ocr_engine is None: _ocr_engine = get_ocr_engine()
    if _ocr_engine is None:
        return ""
    
    try:
        # Load/Crop Image Logic
        cropped_np = _crop_image_as_np(image_source, bbox)
        if cropped_np is None: return ""
        
        # Run EasyOCR
        result = _ocr_engine.readtext(cropped_np, detail=0)
        return " ".join(result)
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        return ""

def _crop_image_as_np(image_source: Any, bbox: list) -> Optional[np.ndarray]:
    """Helper to crop image and return numpy array"""
    try:
        if isinstance(image_source, str):
            if not os.path.exists(image_source): return None
            image = ImageOps.exif_transpose(Image.open(image_source))
        elif isinstance(image_source, Image.Image):
            image = image_source
        elif isinstance(image_source, np.ndarray):
            image = Image.fromarray(image_source)
        else:
            return None
            
        if len(bbox) >= 6:
            xs = [bbox[i] for i in range(0, len(bbox), 2)]
            ys = [bbox[i] for i in range(1, len(bbox), 2)]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        elif len(bbox) == 4:
            x1, y1, x2, y2 = bbox
        else:
            return None
            
        width, height = image.size
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
        if x2 <= x1 or y2 <= y1: return None
            
        cropped = image.crop((x1, y1, x2, y2))
        return np.array(cropped)
    except Exception:
        return None

def extract_text_hybrid(
    image_source: Any, 
    bbox: list, 
    category: str
) -> str:
    """
    텍스트 추출 함수 (기존 Hybrid에서 EasyOCR 단일 모드로 변경됨)
    User Request: DotsOCR 기능 제거
    """
    # Simply use EasyOCR for everything
    return extract_text_from_region(image_source, bbox, get_ocr_engine())


def calculate_text_similarity(text1: str, text2: str) -> float:
    """두 텍스트 간의 유사도(Levenshtein ratio)를 계산합니다."""
    if not text1 or not text2:
        return 0.0
    return Levenshtein.ratio(text1.strip(), text2.strip())
