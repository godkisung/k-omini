"""
문서 타입별 이상치 분석 규칙 정의

이 모듈은 다양한 문서 타입(논문, 발표자료, 보고서 등)에 따라
텍스트 길이, 폴리곤 크기, 카테고리 분포의 정상 범위를 정의합니다.
"""

from typing import Dict, Tuple, Optional

# 문서 타입 코드 및 이름 매핑
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
# {문서타입: {카테고리: (최소, 최대, 설명)}}
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
    'LT': {  # 강의자료
        'title': (3, 80, '강의 제목은 짧음'),
        'text_block': (5, 300, '강의자료는 중간 길이'),
        'list_item': (3, 100, '리스트 항목은 짧음'),
        'caption': (3, 50, '캡션'),
    },
    'CB': {  # 기업보고서
        'title': (5, 100, '보고서 제목'),
        'text_block': (20, 800, '보고서는 긴 문단'),
        'table': (10, 500, '표 내용'),
        'chart': (5, 100, '차트 레이블'),
        'caption': (5, 100, '캡션'),
    },
    'MG': {  # 매뉴얼/가이드
        'title': (5, 100, '매뉴얼 제목'),
        'text_block': (10, 400, '단계별 설명'),
        'list_item': (5, 200, '단계 항목'),
        'caption': (5, 100, '이미지 설명'),
    },
    'EX': {  # 문제집
        'title': (3, 50, '문제 번호/제목'),
        'text_block': (10, 300, '문제 본문'),
        'list_item': (1, 100, '선택지'),
        'caption': (3, 50, '캡션'),
    },
    'PB': {  # 간행물
        'title': (5, 150, '기사 제목'),
        'text_block': (20, 600, '기사 본문'),
        'caption': (5, 100, '사진 캡션'),
    },
    'GR': {  # 정부보고서
        'title': (10, 150, '정부 보고서 제목'),
        'text_block': (30, 1000, '정부 보고서는 매우 긴 문단'),
        'table': (20, 800, '정부 보고서 표는 큼'),
        'caption': (5, 100, '캡션'),
    },
    'RP': {  # 리포트
        'title': (5, 100, '리포트 제목'),
        'text_block': (20, 600, '리포트 본문'),
        'table': (10, 400, '리포트 표'),
        'caption': (5, 100, '캡션'),
    },
    'RT': {  # 보고서
        'title': (5, 100, '보고서 제목'),
        'text_block': (20, 600, '보고서 본문'),
        'table': (10, 400, '보고서 표'),
        'caption': (5, 100, '캡션'),
    },
    'IT': {  # 소개자료
        'title': (3, 80, '소개자료 제목'),
        'text_block': (5, 200, '소개자료는 짧은 설명'),
        'caption': (3, 80, '이미지 캡션'),
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

# 폴리곤 크기 규칙
# {문서타입: {카테고리: (최소비율, 최대비율, (가로세로비율_최소, 가로세로비율_최대))}}
BBOX_SIZE_RULES: Dict[str, Dict[str, Tuple[float, float, Tuple[float, float]]]] = {
    'PP': {  # 논문
        'title': (0.01, 0.15, (2.0, 10.0)),  # 제목은 가로로 김
        'text_block': (0.05, 0.5, (0.5, 3.0)),  # 2단 레이아웃
        'figure': (0.05, 0.4, (0.5, 2.0)),
        'table': (0.05, 0.6, (0.5, 3.0)),
        'equation': (0.005, 0.2, (1.0, 10.0)),
        'caption': (0.005, 0.1, (2.0, 10.0)),
    },
    'PR': {  # 발표자료
        'title': (0.02, 0.2, (3.0, 15.0)),  # 제목은 매우 가로로 김
        'text_block': (0.01, 0.4, (0.5, 5.0)),
        'figure': (0.1, 0.7, (0.5, 2.0)),  # 발표자료는 큰 이미지
        'chart': (0.1, 0.7, (0.5, 2.0)),
        'list_item': (0.01, 0.3, (2.0, 10.0)),
    },
    'LT': {  # 강의자료
        'title': (0.02, 0.2, (3.0, 15.0)),
        'text_block': (0.01, 0.5, (0.5, 5.0)),
        'figure': (0.05, 0.6, (0.5, 2.0)),
        'list_item': (0.01, 0.3, (2.0, 10.0)),
    },
    'CB': {  # 기업보고서
        'title': (0.01, 0.15, (2.0, 10.0)),
        'text_block': (0.02, 0.6, (0.3, 3.0)),
        'table': (0.1, 0.8, (0.5, 3.0)),  # 표가 큼
        'chart': (0.1, 0.7, (0.5, 2.0)),
    },
    'MG': {  # 매뉴얼/가이드
        'title': (0.01, 0.15, (2.0, 10.0)),
        'text_block': (0.02, 0.5, (0.5, 5.0)),
        'figure': (0.05, 0.6, (0.3, 3.0)),  # 설명 이미지
        'list_item': (0.01, 0.3, (1.0, 10.0)),
    },
    'EX': {  # 문제집
        'title': (0.005, 0.1, (2.0, 15.0)),  # 문제 번호는 작음
        'text_block': (0.02, 0.5, (0.5, 5.0)),
        'list_item': (0.005, 0.2, (2.0, 10.0)),  # 선택지는 작음
    },
    'DEFAULT': {
        'title': (0.01, 0.2, (2.0, 15.0)),
        'text_block': (0.01, 0.6, (0.3, 5.0)),
        'figure': (0.05, 0.7, (0.3, 3.0)),
        'table': (0.05, 0.8, (0.3, 5.0)),
        'caption': (0.005, 0.15, (2.0, 10.0)),
        'chart': (0.05, 0.7, (0.5, 3.0)),
    }
}


def get_text_length_rule(doc_type: str, category: str) -> Optional[Tuple[int, int, str]]:
    """
    문서 타입과 카테고리에 맞는 텍스트 길이 규칙 반환
    
    Args:
        doc_type: 문서 타입 코드 (예: 'PP', 'PR')
        category: 카테고리 (예: 'title', 'text_block')
    
    Returns:
        (최소, 최대, 설명) 튜플, 없으면 None
    """
    # 문서 타입별 규칙 확인
    if doc_type in TEXT_LENGTH_RULES:
        if category in TEXT_LENGTH_RULES[doc_type]:
            return TEXT_LENGTH_RULES[doc_type][category]
    
    # 기본 규칙 확인
    if category in TEXT_LENGTH_RULES['DEFAULT']:
        return TEXT_LENGTH_RULES['DEFAULT'][category]
    
    return None


def get_bbox_size_rule(doc_type: str, category: str) -> Optional[Tuple[float, float, Tuple[float, float]]]:
    """
    문서 타입과 카테고리에 맞는 폴리곤 크기 규칙 반환
    
    Args:
        doc_type: 문서 타입 코드 (예: 'PP', 'PR')
        category: 카테고리 (예: 'title', 'text_block')
    
    Returns:
        (최소비율, 최대비율, (가로세로비율_최소, 가로세로비율_최대)) 튜플, 없으면 None
    """
    # 문서 타입별 규칙 확인
    if doc_type in BBOX_SIZE_RULES:
        if category in BBOX_SIZE_RULES[doc_type]:
            return BBOX_SIZE_RULES[doc_type][category]
    
    # 기본 규칙 확인
    if category in BBOX_SIZE_RULES['DEFAULT']:
        return BBOX_SIZE_RULES['DEFAULT'][category]
    
    return None


def extract_doc_type_from_filename(filename: str) -> str:
    """
    파일명에서 문서 타입 추출
    
    Args:
        filename: 파일명 (예: 'PP_1001115_eng_page_015.json')
    
    Returns:
        문서 타입 코드 (예: 'PP'), 없으면 'DEFAULT'
    """
    # 파일명에서 첫 번째 언더스코어 이전 부분 추출
    parts = filename.split('_')
    if len(parts) > 0:
        doc_type = parts[0].upper()
        if doc_type in DOC_TYPE_NAMES:
            return doc_type
    
    return 'DEFAULT'
