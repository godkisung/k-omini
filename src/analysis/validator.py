from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum, auto
from src.core.models import Annotation, Document
from src.config.base import BaseConfig

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

class Validator:
    def __init__(self, config: BaseConfig):
        self.config = config

    def validate_annotation(self, ann: Annotation) -> List[ValidationResult]:
        """단일 어노테이션에 대한 규칙 기반 검증을 수행합니다."""
        results = []
        category = ann.category_type
        
        # 1. 필수 키 검사 (Config에서 규칙 로드)
        required_keys = self.config.REQUIRED_KEYS.get(category, self.config.COMMON_REQUIRED_KEYS)
        
        # Annotation attributes vs raw data check
        # ann.attributes는 이미 'attribute.' 접두사가 제거된 상태일 수 있음 (구현에 따라 다름)
        # 하지만 raw_data를 검사하는 것이 가장 확실함.
        if ann.raw_data:
            target_data = ann.raw_data
        else:
            # raw_data가 없으면 복원 시도 (불완전할 수 있음)
            target_data = ann.__dict__ 

        for key in required_keys:
            # Nested Key Logic (e.g. 'attribute.text_language')
            if "." in key:
                 # flattened check? or nested check?
                 # Assuming raw_data is flattened or structured?
                 # JSON label format usually flat at top level: "attribute.text_language": "ko"
                 if key not in target_data:
                      # Check if passed via attributes dict
                      if key.startswith("attribute."):
                          attr_key = key.split(".", 1)[1] # text_language
                          if ann.attributes and attr_key in ann.attributes:
                              continue # Found in attributes
                          # print(f"DEBUG: Missing nested key {key} (attr_key={attr_key}). Attributes: {ann.attributes}")
                      results.append(ValidationResult("missing_key", Severity.ERROR, f"Missing required key: {key}"))
            else:
                if key not in target_data:
                    # Generic properties check
                    if hasattr(ann, key) and getattr(ann, key) is not None:
                        continue
                    results.append(ValidationResult("missing_key", Severity.ERROR, f"Missing required key: {key}"))

        # 2. Polygon 유효성 검사 (Generic Rule)
        poly = ann.poly
        if not poly or len(poly) < 6: # 최소 삼각형 (3점 * 2좌표)
             results.append(ValidationResult("invalid_poly", Severity.ERROR, "Polygon requires at least 3 points"))
        elif len(poly) % 2 != 0:
             results.append(ValidationResult("invalid_poly", Severity.ERROR, "Polygon coordinates must be even number"))

        return results
