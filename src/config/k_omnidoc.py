from .base import BaseConfig
from typing import Dict, List, Tuple
import os

class KOmniDocConfig(BaseConfig):
    """
    K-Omnidoc Benchmark 데이터셋 전용 설정
    """

    # --- 카테고리별 색상 ---
    @property
    def CATEGORY_COLORS(self) -> Dict[str, str]:
        return {
            "title": "#FF6347",
            "text_block": "#4169E1",
            "figure": "#2E8B57",
            "table": "#FFA500",
            "list": "#9370DB",
            "header": "#FF00FF",
            "footer": "#00FFFF",
            "figure_caption": "#A52A2A",
            "table_caption": "#A52A2A",
            "equation_isolated": "#008080",
            "default": "#343a40",
            "page_number": "#808080",
        }

    # --- 필수 키 검증 ---
    @property
    def COMMON_REQUIRED_KEYS(self) -> List[str]:
        return ["anno_id", "category_type", "ignore", "poly"]

    @property
    def REQUIRED_KEYS(self) -> Dict[str, List[str]]:
        common = self.COMMON_REQUIRED_KEYS
        return {
            "text_group": common + ["text", "attribute.text_language", "attribute.text_rotate"],
            "equation_isolated": common + ["latex", "attribute.equation_language", "attribute.formula_type"],
            "table": common + [
                "html", "table_edit_status", "attribute.line", 
                "attribute.table_layout", "attribute.language"
            ],
            "figure": common + ["attribute.contains_elements", "sub_regions"],
            "chart": common + [
                "html", "attribute.chart_type", "attribute.language", 
                "attribute.chart_level", "attribute.is_indexed"
            ],
            "mask_group": common,
        }

    # --- 관계 검증 규칙 ---
    @property
    def VALID_PARENT_SON_PAIRS(self) -> Dict[str, List[str]]:
        return {
            "Figure": ["figure_caption", "figure_footnote", "text_block", "figure", "table", "equation_isolated"],
            "Table": ["table_caption", "table_footnote", "text_block", "figure", "table", "equation_isolated"],
            "Equation": ["eq_caption", "explanation", "text_block"],
        }
    
    @property
    def UNORDERED_CATEGORIES(self) -> List[str]:
        return ["header", "page_number", "abandon", "footer", "page_footnote", "need_mask"]

    # --- 이상치 탐지 규칙 (Text Length) ---
    @property
    def TEXT_LENGTH_RULES(self) -> Dict[str, Dict[str, Tuple[int, int, str]]]:
        return {
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

    # --- 이상치 탐지 규칙 (BBox Size) ---
    @property
    def BBOX_SIZE_RULES(self) -> Dict[str, Dict[str, Tuple[float, float, Tuple[float, float]]]]:
        return {
             'DEFAULT': {
                'title': (0.01, 0.2, (2.0, 15.0)),
                'text_block': (0.01, 0.6, (0.3, 5.0)),
                'figure': (0.05, 0.7, (0.3, 3.0)),
                'table': (0.05, 0.8, (0.3, 5.0)),
                'caption': (0.005, 0.15, (2.0, 10.0)),
                'chart': (0.05, 0.7, (0.5, 3.0)),
            }
        }

    # --- Helper Methods ---
    def get_doc_type_from_filename(self, filename: str) -> str:
        """K-Omnidoc 파일명 규칙 기반 문서 타입 추출 (IR_xxx.json -> IR)"""
        parts = os.path.basename(filename).split('_')
        doc_types = [
            'IR', 'SK', 'PB', 'LT', 'CB', 'ET', 'PP', 
            'RP', 'MG', 'EX', 'PR', 'RT', 'IT', 'GR'
        ]
        
        if len(parts) > 0:
            doc_type = parts[0].upper()
            if doc_type in doc_types:
                return doc_type
        return 'DEFAULT'

# 싱글톤 인스턴스 (Import해서 바로 사용 가능)
config = KOmniDocConfig()
