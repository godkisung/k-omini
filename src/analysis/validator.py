from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set
from enum import Enum, auto
import re
from src.core.models import Annotation, Document
from src.config.base import BaseConfig
import numpy as np
from shapely.geometry import Polygon

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

        # 3. 빈 텍스트(Empty Text) 유효성 검사
        text_required_cats = {"text_block", "title", "header", "footer", "list_item", "table_caption", "figure_caption", "page_footnote"}
        if category in text_required_cats:
            if ann.text is not None and str(ann.text).strip() == "":
                # ignore=True인 경우 상대적으로 덜 중요하므로 WARNING, 아닌 경우는 ERROR
                severity = Severity.WARNING if getattr(ann, 'ignore', False) else Severity.ERROR
                results.append(ValidationResult("empty_text", severity, "텍스트(text) 값이 비어있습니다."))

        return results

    def validate_document(self, doc: Document) -> List[ValidationResult]:
        """
        문서 (Document) 레벨의 검증을 수행합니다.
        주요 검증: figure 하위 요소(text_block, table, chart 등)의 종속 누락 여부 (IoA 90% 기준)
        """
        results = []
        
        # 1. 자기 참조(Self-referencing) 관계 오류 검사
        if doc.raw_data and 'extra' in doc.raw_data and 'relation' in doc.raw_data['extra']:
            for rel in doc.raw_data['extra']['relation']:
                parent = rel.get('parent') if 'parent' in rel else rel.get('source_anno_id')
                son = rel.get('son') if 'son' in rel else rel.get('target_anno_id')
                if parent is not None and son is not None and parent == son:
                    results.append(
                        ValidationResult(
                            rule_id="self_referencing_relation",
                            severity=Severity.ERROR,
                            message=f"자기 자신을 참조하는 비정상적인 관계가 발견되었습니다. (ID: {parent})",
                            details={"anno_id": parent}
                        )
                    )

        # 2. Table: attribute.include_* 속성 ↔ extra.relation 일관성 검증
        results.extend(self._validate_table_include_relations(doc))

        # 3. Table: HTML 내 anno_id 참조 유효성 검증
        results.extend(self._validate_table_html_anno_refs(doc))
        
        # 4. 모든 Figure 추출
        figures = [ann for ann in doc.layout_dets if ann.category_type == 'figure']
        if not figures:
            return results
            
        # 2. Figure의 자식(sub_regions)이 될 수 있는 요소 추출
        child_candidates = [
            ann for ann in doc.layout_dets 
            if ann.category_type in ['text_block', 'table', 'chart']
        ]
        
        for figure in figures:
            # 기존에 명시적으로 연결된 하위 요소 IDs 확인
            linked_child_ids = set()
            if figure.raw_data and 'sub_regions' in figure.raw_data:
                for sub in figure.raw_data['sub_regions']:
                    if isinstance(sub, dict) and 'anno_id' in sub:
                        linked_child_ids.add(sub['anno_id'])
                        
            if doc.raw_data and 'extra' in doc.raw_data and 'relation' in doc.raw_data['extra']:
                for rel in doc.raw_data['extra']['relation']:
                    if rel.get('parent') == figure.anno_id:
                        linked_child_ids.add(rel.get('son'))

            for child in child_candidates:
                if child.anno_id in linked_child_ids:
                    continue # 이미 정상적으로 종속된 경우는 스킵
                    
                # 유효한 폴리곤인지 확인
                if not child.poly or len(child.poly) < 6 or not figure.poly or len(figure.poly) < 6:
                    continue
                    
                # 3. 교차 면적 비율(IoA) 계산 (오탐 방지를 위해 buffer는 0.0으로 엄격하게 적용)
                # 자식 박스가 부모 박스에 90% 이상 겹칠 경우만 누락으로 간주
                ioa = self._calculate_ioa(figure.poly, child.poly, parent_buffer=0.0)
                
                # 4. IoA가 0.90(90%) 이상인데 종속되어 있지 않으면 에러
                if ioa >= 0.90:
                    msg = f"'{child.category_type}' (ID: {child.anno_id}) 요소가 'figure' (ID: {figure.anno_id}) 내부에 완전히(IoA: {ioa:.2%}) 위치하지만 종속관계(sub_regions)가 누락되었습니다."
                    results.append(
                        ValidationResult(
                            rule_id="missing_figure_dependency",
                            severity=Severity.ERROR,
                            message=msg,
                            details={
                                "parent_id": figure.anno_id, 
                                "child_id": child.anno_id, 
                                "ioa": ioa
                            }
                        )
                    )
                    
        return results

    def _validate_table_include_relations(self, doc: Document) -> List[ValidationResult]:
        """Table 어노테이션의 attribute.include_* 값과 extra.relation의 일관성을 검증합니다.
        
        include_photo=true → extra.relation에 figure를 target으로 하는 parent_son 관계 필요.
        include_chart=true → chart target 관계 필요.
        include_table=true → table target 관계 필요.
        역도 마찬가지로 relation이 있는데 attribute가 false이면 ERROR.
        """
        results = []
        
        # extra.relation 편의 접근 (source_anno_id → target 카테고리 mapping)
        anno_by_id: Dict[Any, str] = {ann.anno_id: ann.category_type for ann in doc.layout_dets}
        relations = []
        if doc.raw_data and 'extra' in doc.raw_data:
            for rel in doc.raw_data['extra'].get('relation', []):
                src = rel.get('source_anno_id') if 'source_anno_id' in rel else rel.get('parent')
                tgt = rel.get('target_anno_id') if 'target_anno_id' in rel else rel.get('son')
                if src is not None and tgt is not None:
                    relations.append((src, tgt, rel.get('relation_type', '')))
        
        # attribute → 기대 target 카테고리 매핑
        ATTR_TO_CAT = {
            'include_photo': 'figure',
            'include_chart': 'chart',
            'include_table': 'table',
        }
        
        tables = [ann for ann in doc.layout_dets if ann.category_type == 'table']
        for tbl in tables:
            attr = {}
            if tbl.raw_data:
                attr = tbl.raw_data.get('attribute', {})
            elif tbl.attributes:
                attr = tbl.attributes
            
            # 테이블이 parent인 parent_son 관계에서 실제 target 카테고리 목록
            actual_child_cats: Set[str] = set()
            for src, tgt, rel_type in relations:
                if src == tbl.anno_id and 'parent_son' in rel_type:
                    tgt_cat = anno_by_id.get(tgt)
                    if tgt_cat:
                        actual_child_cats.add(tgt_cat)
            
            for attr_key, expected_cat in ATTR_TO_CAT.items():
                is_flagged: bool = bool(attr.get(attr_key, False))
                has_relation: bool = expected_cat in actual_child_cats
                
                if is_flagged and not has_relation:
                    results.append(ValidationResult(
                        rule_id="table_include_attr_relation_mismatch",
                        severity=Severity.ERROR,
                        message=(
                            f"Table(ID:{tbl.anno_id}) attribute.{attr_key}=true이지만 "
                            f"'{expected_cat}'를 target으로 하는 parent_son 관계가 없습니다."
                        ),
                        details={"anno_id": tbl.anno_id, "attr_key": attr_key, "expected_cat": expected_cat}
                    ))
                elif not is_flagged and has_relation:
                    results.append(ValidationResult(
                        rule_id="table_include_attr_relation_mismatch",
                        severity=Severity.ERROR,
                        message=(
                            f"Table(ID:{tbl.anno_id}) '{expected_cat}'를 target으로 하는 "
                            f"parent_son 관계가 있지만 attribute.{attr_key}=false입니다."
                        ),
                        details={"anno_id": tbl.anno_id, "attr_key": attr_key, "expected_cat": expected_cat}
                    ))
        
        return results

    def _validate_table_html_anno_refs(self, doc: Document) -> List[ValidationResult]:
        """Table HTML 내 anno_id 참조($$figure_N$$ 또는 <img src='anno_id_N'>) 유효성을 검증합니다.
        
        참조된 ID가 해당 문서의 layout_dets에 실제 존재하지 않으면 ERROR.
        """
        results = []
        valid_ids: Set[Any] = {ann.anno_id for ann in doc.layout_dets}
        
        # 참조 패턴: $$figure_01$$ 또는 <img src="anno_id_5">
        # $$..._{digits}$$ → 숫자 부분이 anno_id
        pattern_dollar = re.compile(r'\$\$[^$]*_(\d+)\$\$')
        # anno_id_N (숫자) 패턴
        pattern_img = re.compile(r'anno_id[_]?(\d+)', re.IGNORECASE)
        
        tables = [ann for ann in doc.layout_dets if ann.category_type == 'table']
        for tbl in tables:
            html = ''
            if tbl.raw_data:
                html = str(tbl.raw_data.get('html', ''))
            
            if not html:
                continue
            
            # 두 패턴으로 참조 ID 추출
            ref_ids: Set[int] = set()
            for m in pattern_dollar.finditer(html):
                ref_ids.add(int(m.group(1)))
            for m in pattern_img.finditer(html):
                ref_ids.add(int(m.group(1)))
            
            for ref_id in ref_ids:
                if ref_id not in valid_ids:
                    results.append(ValidationResult(
                        rule_id="table_html_invalid_anno_ref",
                        severity=Severity.ERROR,
                        message=(
                            f"Table(ID:{tbl.anno_id}) HTML이 존재하지 않는 anno_id={ref_id}를 참조하고 있습니다."
                        ),
                        details={"anno_id": tbl.anno_id, "ref_id": ref_id}
                    ))
        
        return results

    def _calculate_ioa(self, parent_poly_coords: List[float], child_poly_coords: List[float], parent_buffer: float = 0.0) -> float:
        """
        자식 폴리곤(child)이 부모 폴리곤(parent) 안에 얼마나 포함되어 있는지 (Intersection over Area) 비율(0~1) 계산
        """
        try:
            # [x1, y1, x2, y2, ...] -> [(x1, y1), (x2, y2), ...]
            p_pts = [(parent_poly_coords[i], parent_poly_coords[i+1]) for i in range(0, len(parent_poly_coords), 2)]
            c_pts = [(child_poly_coords[i], child_poly_coords[i+1]) for i in range(0, len(child_poly_coords), 2)]
            
            parent_poly = Polygon(p_pts)
            child_poly = Polygon(c_pts)
            
            # self-intersect나 꼬인 점 해결 버퍼(0) 처리
            if not parent_poly.is_valid:
                parent_poly = parent_poly.buffer(0)
            if not child_poly.is_valid:
                child_poly = child_poly.buffer(0)
                
            # 부모 폴리곤에 여유 공간(margin) 부여
            if parent_buffer > 0:
                parent_poly = parent_poly.buffer(parent_buffer)
                
            child_area = child_poly.area
            if child_area == 0:
                return 0.0
                
            intersection = parent_poly.intersection(child_poly)
            return intersection.area / child_area
            
        except Exception:
            # shapely 연산 중 에러 시 Fail Safe
            return 0.0
