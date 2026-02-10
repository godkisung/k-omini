from abc import ABC, abstractmethod
from typing import Dict, List, Any, Tuple, Optional

class BaseConfig(ABC):
    """
    모든 프로젝트 설정 클래스가 상속받아야 하는 기본 클래스
    프로젝트별로 다른 규칙, 색상, 키 등을 정의합니다.
    """
    
    @property
    @abstractmethod
    def CATEGORY_COLORS(self) -> Dict[str, str]:
        pass

    @property
    @abstractmethod
    def REQUIRED_KEYS(self) -> Dict[str, List[str]]:
        pass
        
    @property
    def COMMON_REQUIRED_KEYS(self) -> List[str]:
        return ["anno_id", "category_type", "poly"]

    @property
    def OCR_ENABLED(self) -> bool:
        return True
    
    @property
    def TEXT_LENGTH_RULES(self) -> Dict[str, Dict[str, Tuple[int, int, str]]]:
        """
        문서 타입별 텍스트 길이 규칙
        Return: { 'DOC_TYPE': { 'category': (min, max, description) } }
        """
        return {}

    @property
    def BBOX_SIZE_RULES(self) -> Dict[str, Dict[str, Tuple[float, float, Tuple[float, float]]]]:
        """
        문서 타입별 BBox 크기 규칙
        Return: { 'DOC_TYPE': { 'category': (min_area_ratio, max_area_ratio, (min_aspect, max_aspect)) } }
        """
        return {}

    @property
    def VALID_PARENT_SON_PAIRS(self) -> Dict[str, List[str]]:
        return {}

    @property
    def UNORDERED_CATEGORIES(self) -> List[str]:
        return []
    
    def get_color(self, category: str) -> str:
        return self.CATEGORY_COLORS.get(category, self.CATEGORY_COLORS.get("default", "#000000"))
