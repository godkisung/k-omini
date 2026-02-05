"""
PaddleOCR 기반 텍스트 추출 및 검증 유틸리티

이 모듈은 PaddleOCR을 사용하여 이미지에서 텍스트를 추출하고,
어노테이션 텍스트와 비교하여 오타를 감지하는 기능을 제공합니다.
"""

import os
import logging
from typing import List, Tuple, Dict, Any, Optional, TYPE_CHECKING
import streamlit as st
from PIL import Image
import Levenshtein
from bs4 import BeautifulSoup

# PIR 시스템 비활성화 (ConvertPirAttribute2RuntimeAttribute 오류 해결)
os.environ['FLAGS_enable_pir_api'] = '0'

# 로거 설정
logger = logging.getLogger(__name__)

# PaddleOCR import 전에 paddle 설정
try:
    import paddle
    paddle.set_flags({'FLAGS_enable_pir_api': 0})
    logger.info("PIR 시스템 비활성화 완료")
except ImportError:
    logger.warning("paddle 모듈을 찾을 수 없습니다. PIR 플래그 설정 건너뜀")

# PaddleOCR import
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
    logger.info("PaddleOCR 모듈 로드 성공")
except ImportError as e:
    PADDLEOCR_AVAILABLE = False
    PaddleOCR = Any  # type: ignore
    logger.warning(f"PaddleOCR을 import할 수 없습니다: {e}")

# PPStructure는 별도 모듈 (선택적)
try:
    from ppstructure.structure import PPStructure
    PPSTRUCTURE_AVAILABLE = True
    logger.info("PPStructure 모듈 로드 성공")
except ImportError as e:
    PPSTRUCTURE_AVAILABLE = False
    PPStructure = Any  # type: ignore
    logger.warning(f"PPStructure를 import할 수 없습니다: {e}")




@st.cache_resource
def get_ocr_engine() -> Optional[PaddleOCR]:
    """
    PaddleOCR 엔진을 초기화하고 캐싱합니다.
    
    Returns:
        PaddleOCR 인스턴스 또는 None (설치되지 않은 경우)
    """
    if not PADDLEOCR_AVAILABLE:
        return None
    
    try:
        # ONNX 엔진 사용 시도 (PIR 오류 우회)
        try:
            ocr = PaddleOCR(
                use_angle_cls=True,  # 텍스트 회전 감지
                lang='korean',  # 한국어 인식
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                device='cpu',
                use_onnx=True  # ONNX Runtime 사용 (PIR 우회)
            )
            logger.info("✅ PaddleOCR 엔진 초기화 성공 (ONNX 모드)")
            return ocr
        except Exception as onnx_error:
            # ONNX 실패 시 일반 모드로 재시도
            logger.warning(f"ONNX 모드 실패, 일반 모드로 재시도: {onnx_error}")
            ocr = PaddleOCR(
                use_angle_cls=True,
                lang='korean',
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                device='cpu'
            )
            logger.info("✅ PaddleOCR 엔진 초기화 성공 (일반 모드)")
            return ocr
    except Exception as e:
        logger.error(f"❌ OCR 엔진 초기화 실패: {str(e)}")
        return None


@st.cache_resource
def get_structure_engine() -> Optional[Any]:
    """
    PaddleOCR Structure 엔진을 초기화하고 캐싱합니다.
    
    현재 PPStructure는 지원되지 않습니다.
    
    Returns:
        None (현재 비활성화)
    """
    # PPStructure는 별도 설치가 필요하므로 당분간 비활성화
    logger.info("표 구조 검증은 현재 지원되지 않습니다.")
    return None


@st.cache_data
def extract_text_from_image(
    image_path: str,
    _ocr_engine: Optional[PaddleOCR] = None
) -> List[Tuple[str, float]]:
    """
    이미지에서 텍스트를 추출합니다.
    
    Args:
        image_path: 이미지 파일 경로
        _ocr_engine: PaddleOCR 엔진 인스턴스 (캐싱 방지를 위해 _ 접두사 사용)
    
    Returns:
        [(텍스트, 신뢰도), ...] 형태의 리스트
    """
    if _ocr_engine is None or not os.path.exists(image_path):
        return []
    
    try:
        # predict() 메서드 사용 (최신 PaddleOCR API)
        result = _ocr_engine.predict(input=image_path)
        
        if not result:
            return []
        
        # 결과 파싱
        text_list = []
        for res in result:
            # rec_texts와 rec_scores 추출
            if hasattr(res, 'rec_texts') and hasattr(res, 'rec_scores'):
                for text, score in zip(res.rec_texts, res.rec_scores):
                    text_list.append((text, score))
        
        return text_list
    except Exception as e:
        logger.error(f"❌ 텍스트 추출 실패: {str(e)}")
        return []


@st.cache_data
def extract_text_from_region(
    image_path: str,
    bbox: List[int],
    _ocr_engine: Optional[PaddleOCR] = None
) -> str:
    """
    이미지의 특정 영역에서 텍스트를 추출합니다.
    
    Args:
        image_path: 이미지 파일 경로
        bbox: [x1, y1, x2, y2] 형태의 바운딩 박스
        _ocr_engine: PaddleOCR 엔진 인스턴스
    
    Returns:
        추출된 텍스트 (공백으로 연결)
    """
    if _ocr_engine is None or not os.path.exists(image_path):
        return ""
    
    try:
        # 이미지 로드 및 영역 크롭
        image = Image.open(image_path)
        x1, y1, x2, y2 = bbox
        cropped = image.crop((x1, y1, x2, y2))
        
        # 임시 파일로 저장 (PaddleOCR은 파일 경로 필요)
        temp_path = "/tmp/temp_ocr_region.jpg"
        cropped.save(temp_path)
        
        # predict() 메서드 사용 (최신 PaddleOCR API)
        result = _ocr_engine.predict(input=temp_path)
        
        if not result:
            return ""
        
        # 텍스트 추출 및 연결
        texts = []
        for res in result:
            if hasattr(res, 'rec_texts'):
                texts.extend(res.rec_texts)
        
        return " ".join(texts)
    except Exception as e:
        logger.error(f"❌ 영역 텍스트 추출 실패: {str(e)}")
        return ""
    finally:
        # 임시 파일 삭제
        if os.path.exists("/tmp/temp_ocr_region.jpg"):
            os.remove("/tmp/temp_ocr_region.jpg")


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    두 텍스트의 유사도를 계산합니다 (레벤슈타인 거리 기반).
    
    Args:
        text1: 첫 번째 텍스트
        text2: 두 번째 텍스트
    
    Returns:
        유사도 (0.0 ~ 1.0, 1.0이 완전 일치)
    """
    if not text1 or not text2:
        return 0.0
    
    # 공백 정규화
    text1 = " ".join(text1.split())
    text2 = " ".join(text2.split())
    
    # 레벤슈타인 거리 계산
    distance = Levenshtein.distance(text1, text2)
    max_len = max(len(text1), len(text2))
    
    if max_len == 0:
        return 1.0
    
    # 유사도로 변환 (1 - 정규화된 거리)
    similarity = 1.0 - (distance / max_len)
    return similarity


def calculate_levenshtein_distance(text1: str, text2: str) -> int:
    """
    두 텍스트 간의 레벤슈타인 거리를 계산합니다.
    
    Args:
        text1: 첫 번째 텍스트
        text2: 두 번째 텍스트
    
    Returns:
        편집 거리 (정수)
    """
    return Levenshtein.distance(text1, text2)


@st.cache_data
def extract_table_structure(
    image_path: str,
    _structure_engine: Optional[PPStructure] = None
) -> Optional[Dict[str, Any]]:
    """
    이미지에서 표 구조를 추출합니다.
    
    Args:
        image_path: 이미지 파일 경로
        _structure_engine: PPStructure 엔진 인스턴스
    
    Returns:
        표 구조 정보 딕셔너리 또는 None
        {
            'rows': 행 개수,
            'cols': 열 개수,
            'cells': 셀 정보 리스트
        }
    """
    if _structure_engine is None or not os.path.exists(image_path):
        return None
    
    try:
        result = _structure_engine(image_path)
        
        # 표 구조 찾기
        for item in result:
            if item.get('type') == 'table':
                # HTML 파싱
                html = item.get('res', {}).get('html', '')
                if html:
                    return parse_table_html(html)
        
        return None
    except Exception as e:
        st.error(f"❌ 표 구조 추출 실패: {str(e)}")
        return None


def parse_table_html(html: str) -> Dict[str, Any]:
    """
    HTML 테이블을 파싱하여 행/열 정보를 추출합니다.
    
    Args:
        html: HTML 테이블 문자열
    
    Returns:
        표 구조 정보 딕셔너리
    """
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table')
    
    if not table:
        return {'rows': 0, 'cols': 0, 'cells': []}
    
    rows = table.find_all('tr')
    row_count = len(rows)
    
    # 열 개수 계산 (첫 번째 행 기준)
    col_count = 0
    if rows:
        first_row = rows[0]
        cols = first_row.find_all(['td', 'th'])
        col_count = sum(int(col.get('colspan', 1)) for col in cols)
    
    # 셀 정보 추출
    cells = []
    for row_idx, row in enumerate(rows):
        cols = row.find_all(['td', 'th'])
        for col_idx, col in enumerate(cols):
            cells.append({
                'row': row_idx,
                'col': col_idx,
                'text': col.get_text(strip=True),
                'rowspan': int(col.get('rowspan', 1)),
                'colspan': int(col.get('colspan', 1)),
            })
    
    return {
        'rows': row_count,
        'cols': col_count,
        'cells': cells
    }


def compare_table_structures(
    html1: str,
    html2: str
) -> Tuple[bool, str]:
    """
    두 HTML 테이블의 구조를 비교합니다.
    
    Args:
        html1: 첫 번째 HTML 테이블
        html2: 두 번째 HTML 테이블
    
    Returns:
        (일치 여부, 메시지) 튜플
    """
    struct1 = parse_table_html(html1)
    struct2 = parse_table_html(html2)
    
    if struct1['rows'] != struct2['rows']:
        return False, f"행 개수 불일치: {struct1['rows']} vs {struct2['rows']}"
    
    if struct1['cols'] != struct2['cols']:
        return False, f"열 개수 불일치: {struct1['cols']} vs {struct2['cols']}"
    
    return True, "표 구조 일치"


def get_full_text_from_image(image_path: str) -> str:
    """
    이미지에서 모든 텍스트를 추출하여 하나의 문자열로 반환합니다.
    
    Args:
        image_path: 이미지 파일 경로
    
    Returns:
        추출된 전체 텍스트
    """
    ocr_engine = get_ocr_engine()
    if ocr_engine is None:
        return ""
    
    text_list = extract_text_from_image(image_path, ocr_engine)
    return " ".join([text for text, _ in text_list])
