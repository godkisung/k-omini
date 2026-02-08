import os
import easyocr
import numpy as np
import logging
from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union, Tuple
from PIL import Image
try:
    from transformers import AutoModel, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
import Levenshtein
import streamlit as st
import pandas as pd

from src import config

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Enums & Validation Classes ---
class Severity(Enum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()

@dataclass
class ValidationResult:
    rule_id: str
    severity: Severity
    message: str
    details: Optional[Dict[str, Any]] = None

# --- OCR Engine Logic (from ocr_utils.py) ---

# Global flags
try:
    import torch
    # transformers가 없으면 dots.ocr도 사용 불가
    DOTS_OCR_AVAILABLE = True if (TRANSFORMERS_AVAILABLE and torch.cuda.is_available()) or os.environ.get("FORCE_DOTS_CPU") == "1" else False
    # 단순화: torch 있고 transformers 있으면 True (GPU 체크는 get_dots_model에서)
    DOTS_OCR_AVAILABLE = True if TRANSFORMERS_AVAILABLE else False
except ImportError:
    DOTS_OCR_AVAILABLE = False
    logger.warning("torch/transformers not found. dots.ocr disabled.")

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
        import torch
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

def extract_text_from_region(
    image_source: Any,  # str or Image.Image or np.ndarray
    bbox: List[int],
    _ocr_engine: Optional[easyocr.Reader] = None
) -> str:
    """이미지의 특정 영역에서 텍스트를 추출합니다."""
    if _ocr_engine is None: _ocr_engine = get_ocr_engine()
    if _ocr_engine is None:
        return ""
    
    try:
        # 이미지 소스 처리
        if isinstance(image_source, str):
            if not os.path.exists(image_source): return ""
            image = Image.open(image_source)
        elif isinstance(image_source, Image.Image):
            image = image_source
        elif isinstance(image_source, np.ndarray):
            image = Image.fromarray(image_source)
        else:
            return ""
        
        # BBox 변환 (Polygon인 경우)
        if len(bbox) >= 6:
            xs = [bbox[i] for i in range(0, len(bbox), 2)]
            ys = [bbox[i] for i in range(1, len(bbox), 2)]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        elif len(bbox) == 4:
            x1, y1, x2, y2 = bbox
        else:
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
        print(f"DEBUG: OCR Exception - {str(e)}")
        return ""

def extract_text_hybrid(
    image_source: Any, 
    bbox: List[int], 
    category: str
) -> str:
    """하이브리드 추출 전략: EasyOCR (Fast) + dots.ocr (Smart)"""
    fast_categories = ['text_block', 'code_txt', 'title', 'caption']
    
    if category in fast_categories or not DOTS_OCR_AVAILABLE:
        return extract_text_from_region(image_source, bbox, get_ocr_engine())
        
    dots = get_dots_model()
    # TODO: dots.ocr 추론 구현 시 여기에 추가
    
    # Fallback to EasyOCR
    return extract_text_from_region(image_source, bbox, get_ocr_engine())

def calculate_text_similarity(text1: str, text2: str) -> float:
    """두 텍스트 간의 유사도(Levenshtein ratio)를 계산합니다."""
    if not text1 or not text2:
        return 0.0
    return Levenshtein.ratio(text1.strip(), text2.strip())

# --- Validation Logic (from validation.py) ---

def validate_annotation(ann_dict: Dict[str, Any], rules_config: Dict[str, Any] = None) -> List[ValidationResult]:
    """단일 어노테이션에 대한 규칙 기반 검증을 수행합니다."""
    results = []
    category = ann_dict.get("category_type")
    
    # 1. 필수 키 검사
    required_keys = config.REQUIRED_KEYS.get(category, config.COMMON_REQUIRED_KEYS)
    for key in required_keys:
        if "." in key: # Nested key (e.g., attribute.text_language)
            parent, child = key.split(".")
            if parent not in ann_dict or child not in ann_dict[parent]:
                 results.append(ValidationResult("missing_key", Severity.ERROR, f"Missing required attribute: {key}"))
        else:
            if key not in ann_dict:
                results.append(ValidationResult("missing_key", Severity.ERROR, f"Missing required key: {key}"))

    # 2. Polygon 유효성 검사
    poly = ann_dict.get("poly", [])
    if not poly or len(poly) < 6: # 최소 삼각형? 보통 사각형=8개
         results.append(ValidationResult("invalid_poly", Severity.ERROR, "Polygon requires at least 3 points"))
    elif len(poly) % 2 != 0:
         results.append(ValidationResult("invalid_poly", Severity.ERROR, "Polygon coordinates must be even number"))

    return results

def validate_text_with_ocr(
    ann_dict: Dict[str, Any], 
    image_path: str, 
    threshold: float = 0.9,
    full_doc_data: Dict[str, Any] = None
) -> List[ValidationResult]:
    """OCR을 이용한 텍스트 검증 (On-the-fly)"""
    if "text" not in ann_dict or not ann_dict["text"]:
        return []
    
    ocr_text = extract_text_hybrid(image_path, ann_dict.get("poly", []), ann_dict.get("category_type", ""))
    sim = calculate_text_similarity(ann_dict["text"], ocr_text)
    
    results = []
    if sim < 0.5:
        results.append(ValidationResult("ocr_mismatch_critical", Severity.ERROR, f"Text mismatch critical (Sim: {sim:.2f})"))
    elif sim < threshold:
         results.append(ValidationResult("ocr_mismatch_warning", Severity.WARNING, f"Text mismatch warning (Sim: {sim:.2f})"))
    
    return results

# --- Analytics Logic (from analytics.py) ---

def calculate_category_stats(documents: List[Any]) -> pd.DataFrame:
    """문서 리스트에서 카테고리별 통계를 계산합니다."""
    stats = {}
    for doc in documents:
        for ann in doc.layout_dets:
            cat = ann.category_type
            if cat not in stats:
                stats[cat] = 0
            stats[cat] += 1
    
    df = pd.DataFrame(list(stats.items()), columns=["Category", "Count"])
    return df.sort_values("Count", ascending=False)

def calculate_bbox_from_poly(poly: List[float]) -> List[int]:
    """
    폴리곤 좌표에서 바운딩 박스를 계산합니다.
    Args:
        poly: 폴리곤 좌표 리스트 [x1, y1, x2, y2, ...]
    Returns:
        [x_min, y_min, x_max, y_max] 형태의 bbox
    """
    if not poly or len(poly) < 2:
        return [0, 0, 0, 0]
    
    x_coords = [poly[i] for i in range(0, len(poly), 2)]
    y_coords = [poly[i] for i in range(1, len(poly), 2)]
    return [int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords))]

def validate_table_structure_with_ocr(
    ann: Dict[str, Any],
    image_path: str,
    tolerance: int = 1
) -> List[ValidationResult]:
    """
    표 구조 검증 (Stub). 
    이전에는 PaddleOCR을 사용했으나, 현재는 dots.ocr로 마이그레이션 예정이므로 
    임시로 비활성화 상태입니다.
    """
    # TODO: Implement dots.ocr based validation
    return []

# --- 4. Analytics / Statistics ---
# Migrated from qa_visualizer/rules.py & analytics.py

DOC_TYPE_NAMES = {
    'IR': 'IR',
    'SK': 'SKON',
    'PB': '간행물(Publication)',
    'LT': '강의자료(LecTure)',
    'CB': '기업보고서(Company Business)',
    'ET': '기타(ETc)',
    'PP': '논문(PaPer)',
    'RP': '리포트(RePort)',
    'MG': '매뉴얼/가이드(Manual Guide)',
    'EX': '문제집(EXam)',
    'PR': '발표자료(PResentation)',
    'RT': '보고서(ReporT)',
    'IT': '소개자료(InTroduction)',
    'GR': '정부보고서(GoveRnment)',
}

# 텍스트 길이 규칙
TEXT_LENGTH_RULES: Dict[str, Dict[str, Tuple[int, int, str]]] = {
    'PP': {  # 논문
        'title': (5, 150, '논문 제목은 보통 5~150자'),
        'text_block': (20, 500, '논문 본문은 긴 문단'),
        'abstract': (50, 500, 'Abstract는 긴 문단'),
        'caption': (5, 100, '캡션은 짧음'),
        'equation': (1, 50, '수식은 짧음'),
        'reference': (10, 200, '참고문헌 항목'),
    },
    'PR': {  # 발표자료
        'title': (3, 80, '슬라이드 제목은 짧음'),
        'text_block': (5, 200, '발표자료는 짧은 불릿 포인트'),
        'caption': (3, 50, '캡션은 매우 짧음'),
        'list_item': (3, 100, '불릿 포인트'),
    },
    'DEFAULT': {  # 기본값
        'title': (3, 150, '제목'),
        'text_block': (5, 500, '본문'),
        'caption': (3, 100, '캡션'),
        'table': (5, 500, '표'),
        'list_item': (3, 200, '리스트'),
        'figure': (0, 50, '그림 레이블'),
        'chart': (0, 100, '차트 레이블'),
    }
}
# (다른 규칙들은 생략하거나 필요시 추가)
# BBOX_SIZE_RULES도 필요하지만, 일단 기본 기능 구현을 위해 핵심만 가져옴.
BBOX_SIZE_RULES: Dict[str, Dict[str, Tuple[float, float, Tuple[float, float]]]] = {
     'DEFAULT': {
        'title': (0.01, 0.2, (2.0, 15.0)),
        'text_block': (0.01, 0.6, (0.3, 5.0)),
        'figure': (0.05, 0.7, (0.3, 3.0)),
        'table': (0.05, 0.8, (0.3, 5.0)),
        'caption': (0.005, 0.15, (2.0, 10.0)),
        'chart': (0.05, 0.7, (0.5, 3.0)),
    }
}


def extract_doc_type_from_filename(filename: str) -> str:
    parts = os.path.basename(filename).split('_')
    if len(parts) > 0:
        doc_type = parts[0].upper()
        if doc_type in DOC_TYPE_NAMES:
            return doc_type
    return 'DEFAULT'

def calculate_bbox_area(poly: List) -> Dict[str, float]:
    if not poly or len(poly) < 2:
        return {'width': 0, 'height': 0, 'area': 0, 'aspect_ratio': 0}
    if isinstance(poly[0], (int, float)):
        poly = [[poly[i], poly[i+1]] for i in range(0, len(poly), 2)]
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    area = width * height
    aspect_ratio = width / height if height > 0 else 0
    return {
        'width': width, 'height': height, 'area': area, 'aspect_ratio': aspect_ratio
    }

def get_text_length_rule(doc_type: str, category: str) -> Optional[Tuple[int, int, str]]:
    if doc_type in TEXT_LENGTH_RULES and category in TEXT_LENGTH_RULES[doc_type]:
        return TEXT_LENGTH_RULES[doc_type][category]
    if category in TEXT_LENGTH_RULES['DEFAULT']:
        return TEXT_LENGTH_RULES['DEFAULT'][category]
    return None

def get_bbox_size_rule(doc_type: str, category: str) -> Optional[Tuple[float, float, Tuple[float, float]]]:
    if doc_type in BBOX_SIZE_RULES and category in BBOX_SIZE_RULES[doc_type]:
        return BBOX_SIZE_RULES[doc_type][category]
    if category in BBOX_SIZE_RULES['DEFAULT']:
        return BBOX_SIZE_RULES['DEFAULT'][category]
    return None

def detect_text_length_outliers(docs: List[Any], doc_type_filter: str = None) -> List[Dict[str, Any]]:
    outliers = []
    for doc in docs:
        doc_type = extract_doc_type_from_filename(doc.filename)
        if doc_type_filter and doc_type != doc_type_filter: continue
        
        for ann in doc.layout_dets:
            if not ann.text: continue
            text_length = len(ann.text)
            category = ann.category_type
            rule = get_text_length_rule(doc_type, category)
            if not rule: continue
            min_len, max_len, description = rule
            
            if text_length < min_len:
                outliers.append({
                    'file': doc.filename, 'doc_type': doc_type, 'anno_id': ann.anno_id,
                    'category': category, 'order': ann.order, 'length': text_length,
                    'min': min_len, 'max': max_len, 'reason': f'Too short (min {min_len})',
                    'text_preview': ann.text[:20]
                })
            elif text_length > max_len:
                outliers.append({
                    'file': doc.filename, 'doc_type': doc_type, 'anno_id': ann.anno_id,
                    'category': category, 'order': ann.order, 'length': text_length,
                    'min': min_len, 'max': max_len, 'reason': f'Too long (max {max_len})',
                    'text_preview': ann.text[:20]
                })
    return outliers

def detect_bbox_size_outliers(docs: List[Any], doc_type_filter: str = None) -> List[Dict[str, Any]]:
    outliers = []
    for doc in docs:
        doc_type = extract_doc_type_from_filename(doc.filename)
        if doc_type_filter and doc_type != doc_type_filter: continue
        
        # We need page size, assuming doc.page_info has width/height
        # Check if page_info is dict or object? data_engine.Document defines page_info as Dict.
        page_width = doc.page_info.get('width', 0)
        page_height = doc.page_info.get('height', 0)
        page_area = page_width * page_height
        
        for ann in doc.layout_dets:
            if not ann.poly: continue
            size_info = calculate_bbox_area(ann.poly)
            area_ratio = size_info['area'] / page_area if page_area > 0 else 0
            aspect_ratio = size_info['aspect_ratio']
            category = ann.category_type
            
            rule = get_bbox_size_rule(doc_type, category)
            if not rule: continue
            min_ratio, max_ratio, (min_aspect, max_aspect) = rule
            
            reasons = []
            if area_ratio < min_ratio: reasons.append(f'Too small (<{min_ratio:.1%})')
            if area_ratio > max_ratio: reasons.append(f'Too large (>{max_ratio:.1%})')
            if aspect_ratio < min_aspect or aspect_ratio > max_aspect: reasons.append(f'Odd AR ({aspect_ratio:.2f})')
            
            if reasons:
                outliers.append({
                    'file': doc.filename, 'doc_type': doc_type, 'anno_id': ann.anno_id,
                    'category': category, 'order': ann.order, 
                    'width': size_info['width'], 'height': size_info['height'],
                    'area_ratio': area_ratio*100, 'aspect_ratio': aspect_ratio,
                    'reason': ", ".join(reasons)
                })
    return outliers

def get_statistics_summary(docs: List[Any], doc_type_filter: str = None) -> Dict[str, Any]:
    filtered_docs = docs
    if doc_type_filter:
        filtered_docs = [d for d in docs if extract_doc_type_from_filename(d.filename) == doc_type_filter]
    
    total_files = len(filtered_docs)
    total_annotations = sum(len(d.layout_dets) for d in filtered_docs)
    
    text_lengths = [len(ann.text) for d in filtered_docs for ann in d.layout_dets if ann.text]
    
    # Calculate Areas
    bbox_areas = []
    for d in filtered_docs:
        page_area = d.page_info.get('width',0) * d.page_info.get('height',0)
        for ann in d.layout_dets:
            if ann.poly:
                s = calculate_bbox_area(ann.poly)
                if page_area > 0: bbox_areas.append(s['area']/page_area*100)
    
    category_counts = {}
    for d in filtered_docs:
        for ann in d.layout_dets:
            category_counts[ann.category_type] = category_counts.get(ann.category_type, 0) + 1
            
    return {
        'total_files': total_files,
        'total_annotations': total_annotations,
        'text_length': {
            'mean': np.mean(text_lengths) if text_lengths else 0,
            'max': max(text_lengths) if text_lengths else 0,
        },
        'bbox_area': {
            'mean': np.mean(bbox_areas) if bbox_areas else 0,
        },
        'category_distribution': category_counts
    }

