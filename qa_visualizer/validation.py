import re
from functools import reduce
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional

from .config import REQUIRED_KEYS, VALID_PARENT_SON_PAIRS, UNORDERED_CATEGORIES


class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ValidationResult:
    rule_id: str
    severity: Severity
    message: str
    category: Optional[str] = None  # 어노테이션 카테고리
    anno_id: Optional[str] = None   # 어노테이션 ID
    order: Optional[int] = None     # 어노테이션 순서


def get_prop(obj, path):
    """Safely get a nested property from a dict using a dot-separated path."""
    return reduce(
        lambda d, key: d.get(key) if isinstance(d, dict) else None, path.split("."), obj
    )


def check_required_keys(ann: Dict[str, Any]) -> List[ValidationResult]:
    """Check if an annotation has all required keys for its category."""
    category = ann.get("category_type", "")
    key_group = "mask_group" # Default key group
    
    # Determine key_group based on category
    if category in ["table", "figure", "chart", "equation_isolated"]:
        key_group = category
    elif "text" in category or any(
        t in category
        for t in ["title", "caption", "footnote", "header", "footer", "reference"]
    ):
        key_group = "text_group"

    required = REQUIRED_KEYS.get(key_group, []).copy() # Use .copy() to avoid modifying original list

    # Conditionally add 'order' to required keys
    if category not in UNORDERED_CATEGORIES:
        # Check if 'order' is already in required (it shouldn't be with new config)
        if "order" not in required:
            required.append("order")

    missing = [key for key in required if get_prop(ann, key) is None]
    if missing:
        return [
            ValidationResult(
                rule_id="required_keys",
                severity=Severity.ERROR,
                message=f"Missing required key(s): {', '.join(missing)}",
            )
        ]
    return []


def validate_language(ann: Dict[str, Any]) -> List[ValidationResult]:
    """Validate language consistency in text annotations (Korean/English)."""
    lang = get_prop(ann, "attribute.text_language")
    text = ann.get("text")
    if not lang or not text:
        return []

    # 한글 및 영어 검출
    has_korean = bool(re.search("[\uac00-\ud7a3]", text))
    has_english = bool(re.search("[a-zA-Z]", text))
    
    results = []
    
    # 1. "ko"로 선언했는데 한글이 없는 경우
    if lang == "ko" and not has_korean:
        results.append(
            ValidationResult(
                rule_id="language_mismatch",
                severity=Severity.WARNING,
                message="Language mismatch: Declared 'ko' but no Korean characters found.",
            )
        )
    
    # 2. "ko"로 선언했는데 영어가 포함된 경우
    if lang == "ko" and has_english:
        results.append(
            ValidationResult(
                rule_id="language_mismatch",
                severity=Severity.WARNING,
                message="Language mismatch: Declared 'ko' but English characters found. Consider using 'ko_en_mixed'.",
            )
        )
    
    # 3. "en"으로 선언했는데 영어가 없는 경우
    if lang == "en" and not has_english:
        results.append(
            ValidationResult(
                rule_id="language_mismatch",
                severity=Severity.WARNING,
                message="Language mismatch: Declared 'en' but no English characters found.",
            )
        )
    
    # 4. "en"으로 선언했는데 한글이 포함된 경우
    if lang == "en" and has_korean:
        results.append(
            ValidationResult(
                rule_id="language_mismatch",
                severity=Severity.WARNING,
                message="Language mismatch: Declared 'en' but Korean characters found. Consider using 'ko_en_mixed'.",
            )
        )
    
    # 5. "ko_en_mixed"로 선언했는데 한글이나 영어 중 하나만 있는 경우
    if lang == "ko_en_mixed":
        if has_korean and not has_english:
            results.append(
                ValidationResult(
                    rule_id="language_mismatch",
                    severity=Severity.WARNING,
                    message="Language mismatch: Declared 'ko_en_mixed' but only Korean found. Consider using 'ko'.",
                )
            )
        elif has_english and not has_korean:
            results.append(
                ValidationResult(
                    rule_id="language_mismatch",
                    severity=Severity.WARNING,
                    message="Language mismatch: Declared 'ko_en_mixed' but only English found. Consider using 'en'.",
                )
            )
        elif not has_korean and not has_english:
            results.append(
                ValidationResult(
                    rule_id="language_mismatch",
                    severity=Severity.WARNING,
                    message="Language mismatch: Declared 'ko_en_mixed' but no Korean or English found.",
                )
            )
    
    return results


def validate_parent_son(
    ann: Dict[str, Any], full_data: Dict[str, Any]
) -> List[ValidationResult]:
    """Validate the logical consistency of parent-son relationships."""
    ann_id = ann.get("anno_id")
    ann_cat = ann.get("category_type")
    if not ann_id or not ann_cat or ann_cat not in VALID_PARENT_SON_PAIRS:
        return []

    results = []
    all_relations = get_prop(full_data, "extra.relation") or []
    layout_dets_map = {
        det.get("anno_id"): det for det in full_data.get("layout_dets", [])
    }

    parent_relations = [
        rel
        for rel in all_relations
        if rel.get("source_anno_id") == ann_id
        and rel.get("relation_type") == "parent_son"
    ]

    valid_child_types = VALID_PARENT_SON_PAIRS.get(ann_cat, [])
    for rel in parent_relations:
        child_ann = layout_dets_map.get(rel.get("target_anno_id"))
        if child_ann and child_ann.get("category_type") not in valid_child_types:
            results.append(
                ValidationResult(
                    rule_id="parent_son_logic",
                    severity=Severity.WARNING,
                    message=f"Suspicious relation: '{ann_cat}' is parent to '{child_ann.get('category_type')}'. Please verify.",
                )
            )
    return results


def validate_chart(ann: Dict[str, Any]) -> List[ValidationResult]:
    """Validate chart-specific attributes."""
    if ann.get("category_type") != "chart":
        return []
    results = []
    if get_prop(ann, "attribute.is_indexed") is None:
        results.append(
            ValidationResult(
                rule_id="chart_attributes",
                severity=Severity.WARNING,
                message="Missing chart-specific attribute 'is_indexed'.",
            )
        )
    if get_prop(ann, "attribute.is_sampled") is None:
        results.append(
            ValidationResult(
                rule_id="chart_attributes",
                severity=Severity.WARNING,
                message="Missing chart-specific attribute 'is_sampled'.",
            )
        )
    return results


def validate_polygon_coordinates(ann: Dict[str, Any]) -> List[ValidationResult]:
    """Validate polygon coordinates are valid."""
    poly = ann.get("poly")
    if not poly:
        return []

    results = []

    # Check if poly has even number of coordinates (x, y pairs)
    if len(poly) % 2 != 0:
        results.append(
            ValidationResult(
                rule_id="polygon_coordinates",
                severity=Severity.ERROR,
                message=f"Polygon has odd number of coordinates ({len(poly)}). Must be x,y pairs.",
            )
        )
        return results

    # Check if polygon has at least 3 points (6 coordinates)
    if len(poly) < 6:
        results.append(
            ValidationResult(
                rule_id="polygon_coordinates",
                severity=Severity.ERROR,
                message=f"Polygon has only {len(poly)//2} point(s). Minimum 3 points required.",
            )
        )

    # Check for negative coordinates (warning, not error - some docs may have negative coords)
    has_negative = any(coord < 0 for coord in poly)
    if has_negative:
        results.append(
            ValidationResult(
                rule_id="polygon_coordinates",
                severity=Severity.WARNING,
                message="Polygon contains negative coordinates. Please verify if this is intentional.",
            )
        )

    # Check for extremely large coordinates (potential data error)
    MAX_REASONABLE_COORD = 10000
    has_large = any(coord > MAX_REASONABLE_COORD for coord in poly)
    if has_large:
        results.append(
            ValidationResult(
                rule_id="polygon_coordinates",
                severity=Severity.WARNING,
                message=f"Polygon contains very large coordinates (>{MAX_REASONABLE_COORD}). Please verify.",
            )
        )

    return results


def validate_order_uniqueness(full_data: Dict[str, Any]) -> List[ValidationResult]:
    """Validate that order values are unique within a document."""
    layout_dets = full_data.get("layout_dets", [])
    if not layout_dets:
        return []

    order_map: Dict[int, List[str]] = {}
    for det in layout_dets:
        order = det.get("order")
        anno_id = det.get("anno_id", "N/A")
        if order is not None:
            if order not in order_map:
                order_map[order] = []
            order_map[order].append(anno_id)

    results = []
    for order, anno_ids in order_map.items():
        if len(anno_ids) > 1:
            results.append(
                ValidationResult(
                    rule_id="order_uniqueness",
                    severity=Severity.WARNING,
                    message=f"Duplicate order value {order} found in annotations: {', '.join(anno_ids)}",
                )
            )

    return results


def validate_text_length(ann: Dict[str, Any]) -> List[ValidationResult]:
    """Validate text length for potential anomalies."""
    text = ann.get("text")
    if text is None:
        return []

    results = []
    text_len = len(text)

    # Check for suspiciously short text (less than 1 character is definitely wrong)
    if text_len == 0:
        results.append(
            ValidationResult(
                rule_id="text_length",
                severity=Severity.ERROR,
                message="Text field exists but is empty string.",
            )
        )

    # Check for extremely long text (potential OCR error or data corruption)
    MAX_REASONABLE_LENGTH = 10000
    if text_len > MAX_REASONABLE_LENGTH:
        results.append(
            ValidationResult(
                rule_id="text_length",
                severity=Severity.WARNING,
                message=f"Text is extremely long ({text_len} characters). Please verify if this is correct.",
            )
        )

    # Check for text that is only whitespace
    if text_len > 0 and text.strip() == "":
        results.append(
            ValidationResult(
                rule_id="text_length",
                severity=Severity.WARNING,
                message="Text contains only whitespace characters.",
            )
        )

    return results


def validate_rotation_angle(ann: Dict[str, Any]) -> List[ValidationResult]:
    """Validate rotation angle is a valid string if it exists."""
    rotate = get_prop(ann, "attribute.text_rotate")
    if rotate is None:
        return []

    # According to the schema, the type should be 'str'.
    if not isinstance(rotate, str):
        return [
            ValidationResult(
                rule_id="rotation_angle_type",
                severity=Severity.ERROR,
                message=f"attribute.text_rotate must be a string, but got {type(rotate).__name__}.",
            )
        ]
    
    # Since specific categories are not yet defined, we can check for an empty string.
    if not rotate.strip():
        return [
            ValidationResult(
                rule_id="rotation_angle_value",
                severity=Severity.WARNING,
                message="attribute.text_rotate is an empty or whitespace-only string.",
            )
        ]

    return []



def validate_cross_references(full_data: Dict[str, Any]) -> List[ValidationResult]:
    """Check for dangling references in relations."""
    all_relations = get_prop(full_data, "extra.relation") or []
    if not all_relations:
        return []

    valid_ids = {det.get("anno_id") for det in full_data.get("layout_dets", [])}
    results = []

    for rel in all_relations:
        source_id = rel.get("source_anno_id")
        target_id = rel.get("target_anno_id")
        if source_id and source_id not in valid_ids:
            results.append(
                ValidationResult(
                    rule_id="dangling_reference",
                    severity=Severity.ERROR,
                    message=f"Dangling reference: Relation source_anno_id '{source_id}' does not exist.",
                )
            )
        if target_id and target_id not in valid_ids:
            results.append(
                ValidationResult(
                    rule_id="dangling_reference",
                    severity=Severity.ERROR,
                    message=f"Dangling reference: Relation target_anno_id '{target_id}' does not exist.",
                )
            )
    # This rule is document-wide, but we can return it once. We'll return unique results.
    # A more advanced implementation might attach this error to the document level.
    unique_results = list({res.message: res for res in results}.values())
    return unique_results


def run_full_doc_validation(full_data: Dict[str, Any]) -> List[ValidationResult]:
    """Run all validation checks for an entire document."""
    all_results = []

    # Run document-wide checks first
    all_results.extend(validate_cross_references(full_data))
    all_results.extend(validate_order_uniqueness(full_data))

    # Run annotation-specific checks for every annotation
    for ann in full_data.get("layout_dets", []):
        results = (
            check_required_keys(ann)
            + validate_language(ann)
            + validate_parent_son(ann, full_data)
            + validate_chart(ann)
            + validate_polygon_coordinates(ann)
            + validate_text_length(ann)
            + validate_rotation_angle(ann)
        )
        
        # 메타데이터 추가
        category = ann.get("category_type", "N/A")
        anno_id = ann.get("anno_id", "N/A")
        order = ann.get("order")
        
        # Add file and annotation info to each result for context in bulk reports
        for res in results:
            res.category = category
            res.anno_id = anno_id
            res.order = order
            # 메시지 형식: [category] Anno ID xxx (Order yyy): message
            res.message = f"[{category}] Anno ID {anno_id} (Order {order if order is not None else 'N/A'}): {res.message}"
        all_results.extend(results)

    return all_results


def run_validation(
    ann: Optional[Dict[str, Any]], full_data: Dict[str, Any]
) -> List[ValidationResult]:
    """Run all validation checks for a single annotation."""
    if not ann:
        return []

    # Annotation-specific validations
    results = (
        check_required_keys(ann)
        + validate_language(ann)
        + validate_parent_son(ann, full_data)
        + validate_chart(ann)
        + validate_polygon_coordinates(ann)
        + validate_text_length(ann)
        + validate_rotation_angle(ann)
    )

    # Add document-wide validations, ensuring they appear only once in the UI
    if ann.get("order") == 0:
        doc_wide_results = validate_cross_references(full_data) + validate_order_uniqueness(full_data)
        for res in doc_wide_results:
            res.message = f"[Document-wide] {res.message}"
        results.extend(doc_wide_results)

    if not results:
        return [
            ValidationResult(
                rule_id="all_ok",
                severity=Severity.INFO,
                message="OK: All checks passed.",
            )
        ]
    return results


# ==================== OCR 기반 검증 ====================

def validate_text_with_ocr(
    ann: Dict[str, Any],
    image_path: str,
    similarity_threshold: float = 0.9
) -> List[ValidationResult]:
    """
    OCR로 추출한 텍스트와 어노테이션 텍스트를 비교하여 오타를 감지합니다.
    
    Args:
        ann: 어노테이션 데이터
        image_path: 이미지 파일 경로
        similarity_threshold: 유사도 임계값 (기본 0.9 = 90%)
    
    Returns:
        검증 결과 리스트
    """
    from .ocr_utils import (
        get_ocr_engine,
        extract_text_from_region,
        calculate_text_similarity,
        calculate_levenshtein_distance,
        PADDLEOCR_AVAILABLE
    )
    
    # OCR이 비활성화된 경우 스킵
    if not PADDLEOCR_AVAILABLE:
        return []
    
    # 텍스트가 없는 어노테이션은 스킵
    ann_text = ann.get("text")
    if not ann_text or not ann_text.strip():
        return []
    
    # 폴리곤 좌표가 없으면 스킵
    poly = ann.get("poly")
    if not poly or len(poly) < 6:
        return []
    
    try:
        # 바운딩 박스 계산 (4-point polygon에서 min/max 추출)
        x_coords = [poly[i] for i in range(0, len(poly), 2)]
        y_coords = [poly[i] for i in range(1, len(poly), 2)]
        bbox = [int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords))]
        
        # bbox 검증
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            return [
                ValidationResult(
                    rule_id="ocr_text_comparison",
                    severity=Severity.WARNING,
                    message=f"잘못된 bbox 좌표: {bbox}",
                )
            ]
        
        # OCR 엔진 가져오기
        ocr_engine = get_ocr_engine()
        if ocr_engine is None:
            return []
        
        # 해당 영역에서 텍스트 추출
        ocr_text = extract_text_from_region(image_path, bbox, ocr_engine)
        
        if not ocr_text or not ocr_text.strip():
            return [
                ValidationResult(
                    rule_id="ocr_text_comparison",
                    severity=Severity.WARNING,
                    message=f"OCR로 텍스트를 추출할 수 없습니다.\n"
                            f"bbox: {bbox}\n"
                            f"어노테이션 텍스트: '{ann_text[:100]}...'",
                )
            ]
        
        # 유사도 및 edit distance 계산
        similarity = calculate_text_similarity(ann_text, ocr_text)
        edit_distance = calculate_levenshtein_distance(ann_text, ocr_text)
        
        results = []
        
        # 항상 정보 표시 (디버깅용)
        results.append(
            ValidationResult(
                rule_id="ocr_text_comparison",
                severity=Severity.INFO,
                message=f"🔍 OCR 검증 결과:\n"
                        f"• 유사도: {similarity:.1%}\n"
                        f"• Edit Distance: {edit_distance}\n"
                        f"• 어노테이션 길이: {len(ann_text)} 문자\n"
                        f"• OCR 추출 길이: {len(ocr_text)} 문자\n"
                        f"\n📝 어노테이션: '{ann_text}'\n"
                        f"\n🤖 OCR 추출: '{ocr_text}'",
            )
        )
        
        # 유사도가 임계값보다 낮으면 경고
        if similarity < similarity_threshold:
            diff_percent = (1 - similarity) * 100
            results.append(
                ValidationResult(
                    rule_id="ocr_text_comparison",
                    severity=Severity.ERROR if similarity < 0.7 else Severity.WARNING,
                    message=f"🔴 텍스트 불일치 감지!\n"
                            f"• 유사도: {similarity:.1%} (차이: {diff_percent:.1f}%)\n"
                            f"• Edit Distance: {edit_distance}",
                )
            )
        
        return results
        
    except Exception as e:
        import traceback
        return [
            ValidationResult(
                rule_id="ocr_text_comparison",
                severity=Severity.WARNING,
                message=f"OCR 검증 중 오류 발생: {str(e)}\n{traceback.format_exc()}",
            )
        ]


def validate_table_structure_with_ocr(
    ann: Dict[str, Any],
    image_path: str,
    tolerance: int = 1
) -> List[ValidationResult]:
    """
    PaddleOCR Structure로 표 구조를 인식하고 HTML과 비교합니다.
    
    Args:
        ann: 어노테이션 데이터
        image_path: 이미지 파일 경로
        tolerance: 행/열 개수 허용 오차 (기본 1)
    
    Returns:
        검증 결과 리스트
    """
    from .ocr_utils import (
        get_structure_engine,
        extract_table_structure,
        parse_table_html,
        PADDLEOCR_AVAILABLE
    )
    
    # OCR이 비활성화된 경우 스킵
    if not PADDLEOCR_AVAILABLE:
        return []
    
    # 표가 아닌 경우 스킵
    if ann.get("category_type") != "table":
        return []
    
    # HTML이 없으면 스킵
    html = get_prop(ann, "html")
    if not html:
        return []
    
    # 폴리곤 좌표가 없으면 스킵
    poly = ann.get("poly")
    if not poly or len(poly) < 6:
        return []
    
    try:
        # Structure 엔진 가져오기
        structure_engine = get_structure_engine()
        if structure_engine is None:
            return []
        
        # 바운딩 박스 계산 및 영역 크롭
        from PIL import Image
        import os
        
        x_coords = [poly[i] for i in range(0, len(poly), 2)]
        y_coords = [poly[i] for i in range(1, len(poly), 2)]
        bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
        
        # 이미지 크롭
        image = Image.open(image_path)
        x1, y1, x2, y2 = bbox
        cropped = image.crop((x1, y1, x2, y2))
        
        # 임시 파일로 저장
        temp_path = "/tmp/temp_table_structure.jpg"
        cropped.save(temp_path)
        
        # 표 구조 추출
        ocr_structure = extract_table_structure(temp_path, structure_engine)
        
        # 임시 파일 삭제
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if not ocr_structure:
            return [
                ValidationResult(
                    rule_id="table_structure_ocr",
                    severity=Severity.WARNING,
                    message="OCR로 표 구조를 인식할 수 없습니다.",
                )
            ]
        
        # HTML 파싱
        html_structure = parse_table_html(html)
        
        results = []
        
        # 행 개수 비교
        row_diff = abs(ocr_structure['rows'] - html_structure['rows'])
        if row_diff > tolerance:
            results.append(
                ValidationResult(
                    rule_id="table_structure_ocr",
                    severity=Severity.ERROR,
                    message=f"🔴 표 행 개수 불일치! HTML: {html_structure['rows']}행, OCR: {ocr_structure['rows']}행 (차이: {row_diff})",
                )
            )
        
        # 열 개수 비교
        col_diff = abs(ocr_structure['cols'] - html_structure['cols'])
        if col_diff > tolerance:
            results.append(
                ValidationResult(
                    rule_id="table_structure_ocr",
                    severity=Severity.ERROR,
                    message=f"🔴 표 열 개수 불일치! HTML: {html_structure['cols']}열, OCR: {ocr_structure['cols']}열 (차이: {col_diff})",
                )
            )
        
        return results
        
    except Exception as e:
        return [
            ValidationResult(
                rule_id="table_structure_ocr",
                severity=Severity.WARNING,
                message=f"표 구조 OCR 검증 중 오류 발생: {str(e)}",
            )
        ]
