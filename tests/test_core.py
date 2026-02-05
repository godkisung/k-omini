"""
qa_visualizer.core 모듈에 대한 단위 테스트
"""

import pytest
import json
import tempfile
import os
from qa_visualizer.core import Annotation, Document


class TestAnnotation:
    """Annotation 클래스 테스트"""

    @pytest.fixture
    def sample_annotation_data(self):
        """테스트용 샘플 어노테이션 데이터"""
        return {
            "anno_id": "test_001",
            "category_type": "text_block",
            "order": 1,
            "poly": [10, 10, 110, 10, 110, 60, 10, 60],
            "text": "Sample text",
            "attribute": {"text_language": "english", "text_rotate": 0},
        }

    def test_annotation_creation(self, sample_annotation_data):
        """어노테이션 객체 생성 테스트"""
        ann = Annotation(sample_annotation_data)
        assert ann.data == sample_annotation_data

    def test_annotation_properties(self, sample_annotation_data):
        """어노테이션 속성 접근 테스트"""
        ann = Annotation(sample_annotation_data)
        assert ann.anno_id == "test_001"
        assert ann.category_type == "text_block"
        assert ann.order == 1
        assert ann.poly == [10, 10, 110, 10, 110, 60, 10, 60]
        assert ann.text == "Sample text"
        assert ann.attributes == {"text_language": "english", "text_rotate": 0}

    def test_annotation_optional_properties(self):
        """선택적 속성이 없는 경우 테스트"""
        ann_data = {
            "anno_id": "test_002",
            "category_type": "figure",
            "order": 2,
            "poly": [0, 0, 100, 0, 100, 100, 0, 100],
        }
        ann = Annotation(ann_data)
        assert ann.text is None
        assert ann.html is None
        assert ann.latex is None
        assert ann.attributes == {}

    def test_annotation_default_order(self):
        """order가 없는 경우 기본값 테스트"""
        ann_data = {"anno_id": "test_003", "category_type": "text_block"}
        ann = Annotation(ann_data)
        assert ann.order == float("inf")

    def test_is_inside_point_inside_rectangle(self):
        """사각형 내부의 점 테스트"""
        ann_data = {
            "anno_id": "test_004",
            "poly": [0, 0, 100, 0, 100, 100, 0, 100],  # 사각형
        }
        ann = Annotation(ann_data)
        assert ann.is_inside(50, 50) is True
        assert ann.is_inside(10, 10) is True
        assert ann.is_inside(90, 90) is True

    def test_is_inside_point_outside_rectangle(self):
        """사각형 외부의 점 테스트"""
        ann_data = {
            "anno_id": "test_005",
            "poly": [0, 0, 100, 0, 100, 100, 0, 100],
        }
        ann = Annotation(ann_data)
        assert ann.is_inside(150, 50) is False
        assert ann.is_inside(50, 150) is False
        assert ann.is_inside(-10, 50) is False

    def test_is_inside_point_on_edge(self):
        """경계선 위의 점 테스트"""
        ann_data = {
            "anno_id": "test_006",
            "poly": [0, 0, 100, 0, 100, 100, 0, 100],
        }
        ann = Annotation(ann_data)
        # 경계선 위의 점은 구현에 따라 다를 수 있음
        result = ann.is_inside(0, 50)
        assert isinstance(result, bool)

    def test_is_inside_triangle(self):
        """삼각형 폴리곤 테스트"""
        ann_data = {
            "anno_id": "test_007",
            "poly": [50, 0, 100, 100, 0, 100],  # 삼각형
        }
        ann = Annotation(ann_data)
        assert ann.is_inside(50, 50) is True
        assert ann.is_inside(50, 90) is True
        assert ann.is_inside(10, 10) is False

    def test_is_inside_no_poly(self):
        """poly가 없는 경우"""
        ann_data = {"anno_id": "test_008"}
        ann = Annotation(ann_data)
        assert ann.is_inside(50, 50) is False

    def test_getattr_access(self, sample_annotation_data):
        """__getattr__를 통한 직접 접근 테스트"""
        ann = Annotation(sample_annotation_data)
        # data 딕셔너리에 직접 접근하여 존재하지 않는 키 확인
        assert ann.data.get("ignore") is None
        # 존재하는 키는 property로 접근 가능
        assert ann.anno_id == "test_001"

    def test_getattr_missing_attribute(self, sample_annotation_data):
        """존재하지 않는 속성 접근 시 AttributeError"""
        ann = Annotation(sample_annotation_data)
        with pytest.raises(AttributeError):
            _ = ann.nonexistent_attribute


class TestDocument:
    """Document 클래스 테스트"""

    @pytest.fixture
    def sample_document_data(self):
        """테스트용 샘플 문서 데이터"""
        return {
            "layout_dets": [
                {
                    "anno_id": "ann_001",
                    "category_type": "text_block",
                    "order": 2,
                    "poly": [0, 0, 100, 0, 100, 50, 0, 50],
                    "text": "Second text",
                },
                {
                    "anno_id": "ann_002",
                    "category_type": "title",
                    "order": 1,
                    "poly": [0, 50, 100, 50, 100, 100, 0, 100],
                    "text": "First title",
                },
                {
                    "anno_id": "ann_003",
                    "category_type": "figure",
                    "order": 3,
                    "poly": [0, 100, 100, 100, 100, 200, 0, 200],
                },
            ],
            "extra": {
                "relation": [
                    {
                        "source_anno_id": "ann_003",
                        "target_anno_id": "ann_001",
                        "relation_type": "parent_son",
                    }
                ]
            },
            "page_info": {"image_path": "test_image.jpg", "page_no": 1},
        }

    def test_document_creation(self, sample_document_data):
        """문서 객체 생성 테스트"""
        doc = Document(sample_document_data)
        assert doc.raw_data == sample_document_data
        assert len(doc.layout_dets) == 3
        assert len(doc.relations) == 1

    def test_document_annotations_sorted_by_order(self, sample_document_data):
        """어노테이션이 order 순으로 정렬되는지 테스트"""
        doc = Document(sample_document_data)
        assert doc.layout_dets[0].order == 1
        assert doc.layout_dets[1].order == 2
        assert doc.layout_dets[2].order == 3
        assert doc.layout_dets[0].anno_id == "ann_002"
        assert doc.layout_dets[1].anno_id == "ann_001"
        assert doc.layout_dets[2].anno_id == "ann_003"

    def test_document_image_path(self, sample_document_data):
        """이미지 경로 속성 테스트"""
        doc = Document(sample_document_data)
        assert doc.image_path == "test_image.jpg"

    def test_document_no_image_path(self):
        """이미지 경로가 없는 경우"""
        data = {"layout_dets": [], "page_info": {}}
        doc = Document(data)
        assert doc.image_path is None

    def test_document_get_annotation_by_id(self, sample_document_data):
        """ID로 어노테이션 찾기 테스트"""
        doc = Document(sample_document_data)
        ann = doc.get_annotation_by_id("ann_002")
        assert ann is not None
        assert ann.anno_id == "ann_002"
        assert ann.category_type == "title"

    def test_document_get_annotation_by_id_not_found(self, sample_document_data):
        """존재하지 않는 ID로 검색"""
        doc = Document(sample_document_data)
        ann = doc.get_annotation_by_id("nonexistent")
        assert ann is None

    def test_document_from_json(self, sample_document_data):
        """JSON 파일에서 문서 로드 테스트"""
        # 임시 JSON 파일 생성
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(sample_document_data, f)
            temp_path = f.name

        try:
            doc = Document.from_json(temp_path)
            assert len(doc.layout_dets) == 3
            assert doc.image_path == "test_image.jpg"
        finally:
            os.unlink(temp_path)

    def test_document_empty_layout_dets(self):
        """layout_dets가 비어있는 경우"""
        data = {"layout_dets": [], "extra": {"relation": []}}
        doc = Document(data)
        assert len(doc.layout_dets) == 0
        assert len(doc.relations) == 0

    def test_document_no_relations(self):
        """관계가 없는 경우"""
        data = {
            "layout_dets": [
                {"anno_id": "ann_001", "category_type": "text_block", "order": 1}
            ],
            "extra": {},
        }
        doc = Document(data)
        assert len(doc.relations) == 0

    def test_document_annotations_are_annotation_objects(self, sample_document_data):
        """layout_dets의 각 항목이 Annotation 객체인지 확인"""
        doc = Document(sample_document_data)
        for ann in doc.layout_dets:
            assert isinstance(ann, Annotation)

    def test_document_relations_structure(self, sample_document_data):
        """관계 데이터 구조 테스트"""
        doc = Document(sample_document_data)
        assert len(doc.relations) == 1
        rel = doc.relations[0]
        assert rel["source_anno_id"] == "ann_003"
        assert rel["target_anno_id"] == "ann_001"
        assert rel["relation_type"] == "parent_son"


class TestAnnotationIsInsideEdgeCases:
    """is_inside 메서드의 엣지 케이스 테스트"""

    def test_complex_polygon(self):
        """복잡한 다각형 테스트"""
        ann_data = {
            "anno_id": "complex",
            "poly": [0, 0, 100, 0, 100, 50, 50, 50, 50, 100, 0, 100],  # L자 모양
        }
        ann = Annotation(ann_data)
        assert ann.is_inside(25, 25) is True  # 왼쪽 상단
        assert ann.is_inside(25, 75) is True  # 왼쪽 하단
        assert ann.is_inside(75, 25) is True  # 오른쪽 상단
        assert ann.is_inside(75, 75) is False  # 오른쪽 하단 (L자 빈 공간)

    def test_very_small_polygon(self):
        """매우 작은 폴리곤"""
        ann_data = {"anno_id": "small", "poly": [0, 0, 1, 0, 1, 1, 0, 1]}
        ann = Annotation(ann_data)
        assert ann.is_inside(0.5, 0.5) is True
        assert ann.is_inside(2, 2) is False

    def test_large_coordinates(self):
        """큰 좌표값"""
        ann_data = {
            "anno_id": "large",
            "poly": [1000, 1000, 2000, 1000, 2000, 2000, 1000, 2000],
        }
        ann = Annotation(ann_data)
        assert ann.is_inside(1500, 1500) is True
        assert ann.is_inside(500, 500) is False

    def test_negative_coordinates(self):
        """음수 좌표"""
        ann_data = {
            "anno_id": "negative",
            "poly": [-100, -100, 0, -100, 0, 0, -100, 0],
        }
        ann = Annotation(ann_data)
        assert ann.is_inside(-50, -50) is True
        assert ann.is_inside(50, 50) is False
