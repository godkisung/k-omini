"""
qa_visualizer.validation 모듈에 대한 단위 테스트
"""

import pytest
from typing import Dict, Any, List
from qa_visualizer.validation import (
    check_required_keys,
    validate_language,
    validate_parent_son,
    validate_chart,
    validate_cross_references,
    run_validation,
    run_full_doc_validation,
    Severity,
    ValidationResult,
    get_prop,
)


class TestGetProp:
    """get_prop 함수 테스트"""

    def test_simple_property(self):
        """단순 속성 접근 테스트"""
        obj = {"name": "test", "value": 123}
        assert get_prop(obj, "name") == "test"
        assert get_prop(obj, "value") == 123

    def test_nested_property(self):
        """중첩된 속성 접근 테스트"""
        obj = {"attribute": {"text_language": "english", "text_rotate": 0}}
        assert get_prop(obj, "attribute.text_language") == "english"
        assert get_prop(obj, "attribute.text_rotate") == 0

    def test_missing_property(self):
        """존재하지 않는 속성 접근 테스트"""
        obj = {"name": "test"}
        assert get_prop(obj, "missing") is None
        assert get_prop(obj, "attribute.missing") is None

    def test_deep_nested_property(self):
        """깊이 중첩된 속성 접근 테스트"""
        obj = {"a": {"b": {"c": {"d": "value"}}}}
        assert get_prop(obj, "a.b.c.d") == "value"


class TestCheckRequiredKeys:
    """check_required_keys 함수 테스트"""

    def test_text_group_valid(self):
        """텍스트 그룹 카테고리의 유효한 어노테이션"""
        ann = {
            "anno_id": "test_001",
            "category_type": "text_block",
            "ignore": False,
            "order": 1,
            "poly": [0, 0, 100, 0, 100, 100, 0, 100],
            "text": "Sample text",
            "attribute": {"text_language": "english", "text_rotate": 0},
        }
        results = check_required_keys(ann)
        assert len(results) == 0

    def test_text_group_missing_text(self):
        """텍스트가 누락된 경우"""
        ann = {
            "anno_id": "test_001",
            "category_type": "text_block",
            "ignore": False,
            "order": 1,
            "poly": [0, 0, 100, 0, 100, 100, 0, 100],
            "attribute": {"text_language": "english", "text_rotate": 0},
        }
        results = check_required_keys(ann)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "text" in results[0].message

    def test_table_valid(self):
        """테이블 카테고리의 유효한 어노테이션"""
        ann = {
            "anno_id": "test_002",
            "category_type": "table",
            "ignore": False,
            "order": 2,
            "poly": [0, 0, 200, 0, 200, 200, 0, 200],
            "html": "<table></table>",
            "table_edit_status": "edited",
            "attribute": {"line": True, "table_layout": "simple", "language": "english"},
        }
        results = check_required_keys(ann)
        assert len(results) == 0

    def test_equation_missing_latex(self):
        """LaTeX가 누락된 수식"""
        ann = {
            "anno_id": "test_003",
            "category_type": "equation_isolated",
            "ignore": False,
            "order": 3,
            "poly": [0, 0, 150, 0, 150, 50, 0, 50],
            "attribute": {"equation_language": "latex", "formula_type": "inline"},
        }
        results = check_required_keys(ann)
        assert len(results) == 1
        assert results[0].severity == Severity.ERROR
        assert "latex" in results[0].message


class TestValidateLanguage:
    """validate_language 함수 테스트"""

    def test_english_text_correct(self):
        """영어 텍스트와 영어 언어 선언이 일치"""
        ann = {
            "text": "This is English text",
            "attribute": {"text_language": "english"},
        }
        results = validate_language(ann)
        assert len(results) == 0

    def test_han_text_correct(self):
        """한자 텍스트와 한자 언어 선언이 일치"""
        ann = {"text": "这是中文文本", "attribute": {"text_language": "han"}}
        results = validate_language(ann)
        assert len(results) == 0

    def test_language_mismatch_han_declared_no_han(self):
        """한자로 선언했지만 한자가 없는 경우"""
        ann = {"text": "This is English", "attribute": {"text_language": "han"}}
        results = validate_language(ann)
        assert len(results) == 1
        assert results[0].severity == Severity.WARNING
        assert "Han" in results[0].message

    def test_language_mismatch_english_declared_has_han(self):
        """영어로 선언했지만 한자가 있는 경우"""
        ann = {"text": "这是中文", "attribute": {"text_language": "english"}}
        results = validate_language(ann)
        assert len(results) == 1
        assert results[0].severity == Severity.WARNING
        assert "English" in results[0].message

    def test_no_language_attribute(self):
        """언어 속성이 없는 경우"""
        ann = {"text": "Some text"}
        results = validate_language(ann)
        assert len(results) == 0

    def test_no_text(self):
        """텍스트가 없는 경우"""
        ann = {"attribute": {"text_language": "english"}}
        results = validate_language(ann)
        assert len(results) == 0


class TestValidateParentSon:
    """validate_parent_son 함수 테스트"""

    def test_valid_figure_caption_relation(self):
        """유효한 Figure-Caption 관계"""
        ann = {"anno_id": "fig_001", "category_type": "Figure"}
        full_data = {
            "layout_dets": [
                ann,
                {"anno_id": "cap_001", "category_type": "figure_caption"},
            ],
            "extra": {
                "relation": [
                    {
                        "source_anno_id": "fig_001",
                        "target_anno_id": "cap_001",
                        "relation_type": "parent_son",
                    }
                ]
            },
        }
        results = validate_parent_son(ann, full_data)
        assert len(results) == 0

    def test_invalid_figure_relation(self):
        """잘못된 Figure 관계 (Figure가 title을 자식으로 가짐)"""
        ann = {"anno_id": "fig_001", "category_type": "Figure"}
        full_data = {
            "layout_dets": [ann, {"anno_id": "title_001", "category_type": "title"}],
            "extra": {
                "relation": [
                    {
                        "source_anno_id": "fig_001",
                        "target_anno_id": "title_001",
                        "relation_type": "parent_son",
                    }
                ]
            },
        }
        results = validate_parent_son(ann, full_data)
        assert len(results) == 1
        assert results[0].severity == Severity.WARNING
        assert "Suspicious relation" in results[0].message

    def test_no_relations(self):
        """관계가 없는 경우"""
        ann = {"anno_id": "fig_001", "category_type": "Figure"}
        full_data = {"layout_dets": [ann], "extra": {"relation": []}}
        results = validate_parent_son(ann, full_data)
        assert len(results) == 0

    def test_non_parent_category(self):
        """부모가 될 수 없는 카테고리"""
        ann = {"anno_id": "text_001", "category_type": "text_block"}
        full_data = {"layout_dets": [ann], "extra": {"relation": []}}
        results = validate_parent_son(ann, full_data)
        assert len(results) == 0


class TestValidateChart:
    """validate_chart 함수 테스트"""

    def test_chart_with_all_attributes(self):
        """모든 속성을 가진 차트"""
        ann = {
            "category_type": "chart",
            "attribute": {"is_indexed": True, "is_sampled": False},
        }
        results = validate_chart(ann)
        assert len(results) == 0

    def test_chart_missing_is_indexed(self):
        """is_indexed가 누락된 차트"""
        ann = {"category_type": "chart", "attribute": {"is_sampled": False}}
        results = validate_chart(ann)
        assert len(results) >= 1
        assert any("is_indexed" in r.message for r in results)

    def test_chart_missing_is_sampled(self):
        """is_sampled가 누락된 차트"""
        ann = {"category_type": "chart", "attribute": {"is_indexed": True}}
        results = validate_chart(ann)
        assert len(results) >= 1
        assert any("is_sampled" in r.message for r in results)

    def test_non_chart_category(self):
        """차트가 아닌 카테고리"""
        ann = {"category_type": "table", "attribute": {}}
        results = validate_chart(ann)
        assert len(results) == 0


class TestValidateCrossReferences:
    """validate_cross_references 함수 테스트"""

    def test_valid_references(self):
        """유효한 참조"""
        full_data = {
            "layout_dets": [
                {"anno_id": "ann_001"},
                {"anno_id": "ann_002"},
            ],
            "extra": {
                "relation": [
                    {
                        "source_anno_id": "ann_001",
                        "target_anno_id": "ann_002",
                        "relation_type": "parent_son",
                    }
                ]
            },
        }
        results = validate_cross_references(full_data)
        assert len(results) == 0

    def test_dangling_source_reference(self):
        """존재하지 않는 source_anno_id"""
        full_data = {
            "layout_dets": [{"anno_id": "ann_001"}],
            "extra": {
                "relation": [
                    {
                        "source_anno_id": "missing_001",
                        "target_anno_id": "ann_001",
                        "relation_type": "parent_son",
                    }
                ]
            },
        }
        results = validate_cross_references(full_data)
        assert len(results) >= 1
        assert any("missing_001" in r.message for r in results)
        assert any(r.severity == Severity.ERROR for r in results)

    def test_dangling_target_reference(self):
        """존재하지 않는 target_anno_id"""
        full_data = {
            "layout_dets": [{"anno_id": "ann_001"}],
            "extra": {
                "relation": [
                    {
                        "source_anno_id": "ann_001",
                        "target_anno_id": "missing_002",
                        "relation_type": "parent_son",
                    }
                ]
            },
        }
        results = validate_cross_references(full_data)
        assert len(results) >= 1
        assert any("missing_002" in r.message for r in results)

    def test_no_relations(self):
        """관계가 없는 경우"""
        full_data = {"layout_dets": [{"anno_id": "ann_001"}], "extra": {}}
        results = validate_cross_references(full_data)
        assert len(results) == 0


class TestRunValidation:
    """run_validation 함수 통합 테스트"""

    def test_valid_annotation(self):
        """모든 검증을 통과하는 어노테이션"""
        ann = {
            "anno_id": "test_001",
            "category_type": "text_block",
            "ignore": False,
            "order": 1,
            "poly": [0, 0, 100, 0, 100, 100, 0, 100],
            "text": "Valid text",
            "attribute": {"text_language": "english", "text_rotate": "0"},
        }
        full_data = {"layout_dets": [ann], "extra": {"relation": []}}
        results = run_validation(ann, full_data)
        # 모든 검증 통과 시 INFO 메시지 반환
        assert len(results) >= 1
        assert any(r.severity == Severity.INFO for r in results)

    def test_annotation_with_errors(self):
        """오류가 있는 어노테이션"""
        ann = {
            "anno_id": "test_002",
            "category_type": "text_block",
            "ignore": False,
            "order": 2,
            "poly": [0, 0, 100, 0, 100, 100, 0, 100],
            # text 누락
            "attribute": {"text_language": "english", "text_rotate": "0"},
        }
        full_data = {"layout_dets": [ann], "extra": {"relation": []}}
        results = run_validation(ann, full_data)
        assert len(results) >= 1
        assert any(r.severity == Severity.ERROR for r in results)

    def test_none_annotation(self):
        """None 어노테이션"""
        full_data = {"layout_dets": [], "extra": {"relation": []}}
        results = run_validation(None, full_data)
        assert len(results) == 0


class TestRunFullDocValidation:
    """run_full_doc_validation 함수 통합 테스트"""

    def test_valid_document(self):
        """유효한 문서"""
        full_data = {
            "layout_dets": [
                {
                    "anno_id": "ann_001",
                    "category_type": "text_block",
                    "ignore": False,
                    "order": 1,
                    "poly": [0, 0, 100, 0, 100, 100, 0, 100],
                    "text": "Text 1",
                    "attribute": {"text_language": "english", "text_rotate": "0"},
                },
                {
                    "anno_id": "ann_002",
                    "category_type": "text_block",
                    "ignore": False,
                    "order": 2,
                    "poly": [0, 100, 100, 100, 100, 200, 0, 200],
                    "text": "Text 2",
                    "attribute": {"text_language": "english", "text_rotate": "0"},
                },
            ],
            "extra": {"relation": []},
        }
        results = run_full_doc_validation(full_data)
        # 유효한 문서는 오류/경고가 없어야 함
        errors_and_warnings = [
            r for r in results if r.severity in [Severity.ERROR, Severity.WARNING]
        ]
        assert len(errors_and_warnings) == 0

    def test_document_with_errors(self):
        """오류가 있는 문서"""
        full_data = {
            "layout_dets": [
                {
                    "anno_id": "ann_001",
                    "category_type": "text_block",
                    "ignore": False,
                    "order": 1,
                    "poly": [0, 0, 100, 0, 100, 100, 0, 100],
                    # text 누락
                    "attribute": {"text_language": "english", "text_rotate": "0"},
                }
            ],
            "extra": {"relation": []},
        }
        results = run_full_doc_validation(full_data)
        assert len(results) >= 1
        assert any(r.severity == Severity.ERROR for r in results)

    def test_document_with_dangling_references(self):
        """참조 오류가 있는 문서"""
        full_data = {
            "layout_dets": [{"anno_id": "ann_001", "category_type": "text_block"}],
            "extra": {
                "relation": [
                    {
                        "source_anno_id": "ann_001",
                        "target_anno_id": "missing",
                        "relation_type": "parent_son",
                    }
                ]
            },
        }
        results = run_full_doc_validation(full_data)
        assert len(results) >= 1
        assert any(r.severity == Severity.ERROR for r in results)
        assert any("missing" in r.message for r in results)
