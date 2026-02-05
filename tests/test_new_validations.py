"""
새로 추가된 검증 규칙에 대한 테스트
"""

import pytest
from qa_visualizer.validation import (
    validate_polygon_coordinates,
    validate_order_uniqueness,
    validate_text_length,
    validate_rotation_angle,
    Severity,
)


class TestValidatePolygonCoordinates:
    """validate_polygon_coordinates 함수 테스트"""

    def test_valid_polygon(self):
        """유효한 폴리곤 (사각형)"""
        ann = {"poly": [0, 0, 100, 0, 100, 100, 0, 100]}
        results = validate_polygon_coordinates(ann)
        assert len(results) == 0

    def test_valid_triangle(self):
        """유효한 삼각형"""
        ann = {"poly": [0, 0, 100, 0, 50, 100]}
        results = validate_polygon_coordinates(ann)
        assert len(results) == 0

    def test_odd_number_coordinates(self):
        """홀수 개의 좌표 (오류)"""
        ann = {"poly": [0, 0, 100, 0, 100]}
        results = validate_polygon_coordinates(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.ERROR for r in results)
        assert any("odd number" in r.message for r in results)

    def test_too_few_points(self):
        """점이 3개 미만 (오류)"""
        ann = {"poly": [0, 0, 100, 100]}  # 2개 점만
        results = validate_polygon_coordinates(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.ERROR for r in results)
        assert any("Minimum 3 points" in r.message for r in results)

    def test_negative_coordinates(self):
        """음수 좌표 (경고)"""
        ann = {"poly": [-10, -10, 100, 0, 100, 100, 0, 100]}
        results = validate_polygon_coordinates(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.WARNING for r in results)
        assert any("negative" in r.message for r in results)

    def test_very_large_coordinates(self):
        """매우 큰 좌표 (경고)"""
        ann = {"poly": [0, 0, 20000, 0, 20000, 20000, 0, 20000]}
        results = validate_polygon_coordinates(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.WARNING for r in results)
        assert any("large" in r.message for r in results)

    def test_no_poly(self):
        """poly가 없는 경우"""
        ann = {"anno_id": "test"}
        results = validate_polygon_coordinates(ann)
        assert len(results) == 0


class TestValidateOrderUniqueness:
    """validate_order_uniqueness 함수 테스트"""

    def test_unique_orders(self):
        """모든 order가 고유한 경우"""
        full_data = {
            "layout_dets": [
                {"anno_id": "ann_001", "order": 1},
                {"anno_id": "ann_002", "order": 2},
                {"anno_id": "ann_003", "order": 3},
            ]
        }
        results = validate_order_uniqueness(full_data)
        assert len(results) == 0

    def test_duplicate_orders(self):
        """중복된 order가 있는 경우"""
        full_data = {
            "layout_dets": [
                {"anno_id": "ann_001", "order": 1},
                {"anno_id": "ann_002", "order": 1},
                {"anno_id": "ann_003", "order": 2},
            ]
        }
        results = validate_order_uniqueness(full_data)
        assert len(results) >= 1
        assert any(r.severity == Severity.WARNING for r in results)
        assert any("Duplicate order" in r.message for r in results)
        assert any("ann_001" in r.message and "ann_002" in r.message for r in results)

    def test_multiple_duplicate_orders(self):
        """여러 중복 order가 있는 경우"""
        full_data = {
            "layout_dets": [
                {"anno_id": "ann_001", "order": 1},
                {"anno_id": "ann_002", "order": 1},
                {"anno_id": "ann_003", "order": 2},
                {"anno_id": "ann_004", "order": 2},
            ]
        }
        results = validate_order_uniqueness(full_data)
        assert len(results) >= 2  # 2개의 중복 그룹

    def test_empty_layout_dets(self):
        """layout_dets가 비어있는 경우"""
        full_data = {"layout_dets": []}
        results = validate_order_uniqueness(full_data)
        assert len(results) == 0

    def test_missing_order(self):
        """order가 없는 어노테이션"""
        full_data = {
            "layout_dets": [
                {"anno_id": "ann_001", "order": 1},
                {"anno_id": "ann_002"},  # order 없음
            ]
        }
        results = validate_order_uniqueness(full_data)
        assert len(results) == 0  # order가 없는 것은 무시


class TestValidateTextLength:
    """validate_text_length 함수 테스트"""

    def test_normal_text(self):
        """정상적인 길이의 텍스트"""
        ann = {"text": "This is a normal text with reasonable length."}
        results = validate_text_length(ann)
        assert len(results) == 0

    def test_empty_string(self):
        """빈 문자열 (오류)"""
        ann = {"text": ""}
        results = validate_text_length(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.ERROR for r in results)
        assert any("empty string" in r.message for r in results)

    def test_very_long_text(self):
        """매우 긴 텍스트 (경고)"""
        ann = {"text": "a" * 15000}
        results = validate_text_length(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.WARNING for r in results)
        assert any("extremely long" in r.message for r in results)

    def test_whitespace_only(self):
        """공백만 있는 텍스트 (경고)"""
        ann = {"text": "   \n\t  "}
        results = validate_text_length(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.WARNING for r in results)
        assert any("whitespace" in r.message for r in results)

    def test_no_text_field(self):
        """text 필드가 없는 경우"""
        ann = {"anno_id": "test"}
        results = validate_text_length(ann)
        assert len(results) == 0

    def test_none_text(self):
        """text가 None인 경우"""
        ann = {"text": None}
        results = validate_text_length(ann)
        assert len(results) == 0


class TestValidateRotationAngle:
    """validate_rotation_angle 함수 테스트 (문자열 타입 검증)"""

    def test_valid_rotation_string(self):
        """유효한 회전 각도 문자열"""
        ann = {"attribute": {"text_rotate": "0"}}
        results = validate_rotation_angle(ann)
        assert len(results) == 0

    def test_valid_rotation_string_90(self):
        """유효한 회전 각도 문자열 90"""
        ann = {"attribute": {"text_rotate": "90"}}
        results = validate_rotation_angle(ann)
        assert len(results) == 0

    def test_valid_rotation_string_180(self):
        """유효한 회전 각도 문자열 180"""
        ann = {"attribute": {"text_rotate": "180"}}
        results = validate_rotation_angle(ann)
        assert len(results) == 0

    def test_valid_rotation_string_270(self):
        """유효한 회전 각도 문자열 270"""
        ann = {"attribute": {"text_rotate": "270"}}
        results = validate_rotation_angle(ann)
        assert len(results) == 0

    def test_rotation_integer_type_error(self):
        """정수 타입 (오류 - 문자열이어야 함)"""
        ann = {"attribute": {"text_rotate": 0}}
        results = validate_rotation_angle(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.ERROR for r in results)
        assert any("must be a string" in r.message for r in results)

    def test_rotation_float_type_error(self):
        """소수 타입 (오류 - 문자열이어야 함)"""
        ann = {"attribute": {"text_rotate": 45.5}}
        results = validate_rotation_angle(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.ERROR for r in results)
        assert any("must be a string" in r.message for r in results)

    def test_empty_string_warning(self):
        """빈 문자열 (경고)"""
        ann = {"attribute": {"text_rotate": ""}}
        results = validate_rotation_angle(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.WARNING for r in results)
        assert any("empty" in r.message or "whitespace" in r.message for r in results)

    def test_whitespace_only_warning(self):
        """공백만 있는 문자열 (경고)"""
        ann = {"attribute": {"text_rotate": "   "}}
        results = validate_rotation_angle(ann)
        assert len(results) >= 1
        assert any(r.severity == Severity.WARNING for r in results)

    def test_no_rotation_attribute(self):
        """회전 속성이 없는 경우"""
        ann = {"attribute": {}}
        results = validate_rotation_angle(ann)
        assert len(results) == 0

    def test_no_attribute(self):
        """attribute 자체가 없는 경우"""
        ann = {}
        results = validate_rotation_angle(ann)
        assert len(results) == 0
