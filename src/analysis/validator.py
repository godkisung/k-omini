from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set
from enum import Enum, auto
import re
from src.core.models import Annotation, Document
from src.config.base import BaseConfig
import numpy as np
from shapely.geometry import Polygon

# Optional LaTeX parsing dependency (pylatexenc)
try:
    from pylatexenc.latexwalker import LatexWalker, LatexWalkerParseError, LatexMacroNode
    HAS_PYLATEXENC = True
except Exception:
    HAS_PYLATEXENC = False

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

        # ignore 속성 종합 확인 (root 레벨 및 attribute 내부 모두 확인)
        is_ignored = getattr(ann, 'ignore', False)
        if hasattr(ann, 'attributes') and isinstance(ann.attributes, dict) and ann.attributes.get('ignore') is True:
            is_ignored = True
        elif ann.raw_data and isinstance(ann.raw_data.get('attribute'), dict) and ann.raw_data['attribute'].get('ignore') is True:
            is_ignored = True

        # 3. 빈 텍스트(Empty Text) 유효성 검사
        text_required_cats = {"text_block", "title", "header", "footer", "list_item", "table_caption", "figure_caption", "page_footnote"}
        if category in text_required_cats:
            if ann.text is not None and str(ann.text).strip() == "":
                severity = Severity.WARNING if is_ignored else Severity.ERROR
                msg = "텍스트(text) 값이 비어있습니다."
                if is_ignored:
                    msg += " (단, attribute 내 ignore=True로 설정되어 오류가 아님)"
                results.append(ValidationResult("empty_text", severity, msg))

        # 4. 빈 HTML 유효성 검사
        if category == "table":
            html_val = None
            if hasattr(ann, 'html') and ann.html is not None:
                html_val = ann.html
            elif ann.raw_data and 'html' in ann.raw_data:
                html_val = ann.raw_data.get('html')
                
            if html_val is None or str(html_val).strip() == "":
                severity = Severity.WARNING if is_ignored else Severity.ERROR
                msg = "테이블 요소의 html 값이 비어있거나 Null(None)입니다."
                if is_ignored:
                    msg += " (단, attribute 내 ignore=True로 설정되어 오류가 아님)"
                results.append(ValidationResult("empty_html", severity, msg))
        elif ann.raw_data and 'html' in ann.raw_data:
            # table이 아닌데 html을 가진 경우 (예: chart)에도 빈 값이면 경고
            html_val = ann.raw_data.get('html')
            if html_val is None or str(html_val).strip() == "":
                severity = Severity.WARNING
                msg = f"'{category}' 요소의 html 값이 비어있거나 Null(None)입니다."
                if is_ignored:
                    msg += " (단, attribute 내 ignore=True로 설정되어 정상 처리됨)"
                results.append(ValidationResult("empty_html", severity, msg))

        # 5. LaTeX 검증 (equation_isolated 카테고리 및 latex/text 내 인라인 수식)
        if category == "equation_isolated" or getattr(ann, 'latex', None) or (getattr(ann, 'text', None) and ("$" in ann.text or "\\" in ann.text)):
            # validate explicit latex field
            latex_field = getattr(ann, 'latex', None)
            if latex_field:
                results.extend(self._validate_latex_syntax(latex_field, source='latex_field', ann=ann))
            # validate inline formulas in text
            text_field = getattr(ann, 'text', None)
            if text_field:
                inline_formulas = self._extract_inline_latex(text_field)
                for idx, (formula, span) in enumerate(inline_formulas):
                    results.extend(self._validate_latex_syntax(formula, source='inline_text', ann=ann, span=span))

        # 6. [NEW] potential missing inlinelatex 검증
        if category in {"text_block", "chart_caption", "table_caption"}:
            text_field = getattr(ann, 'text', None)
            if text_field:
                results.extend(self._validate_missing_inlinelatex(text_field, ann=ann))

        return results

    def _validate_missing_inlinelatex(self, text: str, ann: Optional[Annotation] = None) -> List[ValidationResult]:
        """텍스트 내에 수식이나 과학적 기호가 포함되어 있는데 inlinelatex($...$) 처리가 누락되었는지 검사합니다."""
        results = []
        
        # 1. 이미 LaTeX로 감싸진 부분 제외하고 검색하기 위해 $...$ 제거한 임시 텍스트 생성
        clean_text = re.sub(r'\$.*?\$', ' ', text)
        
        # 2. 수식/과학적 기호 패턴 정의
        # - 하첨자/상첨자 패턴: x_2, y^2, H_2O 등
        # - 주요 수식 기호: \alpha, \beta, \times, \pm, \sqrt 등
        # - 연산자: \sum, \int, \log 등
        patterns = [
            (r'[a-zA-Z][0-9]_[a-zA-Z0-9]', "알파벳 뒤에 오는 숫자/문자 하첨자 가능성"),
            (r'[a-zA-Z]\^[a-zA-Z0-9]', "지수(상첨자) 표현 가능성"),
            (r'\\[a-zA-Z]+', "역슬래시(\\)로 시작하는 LaTeX 매크로 누락 가능성"),
            (r'[0-9]+\s*[xX]\s*[0-9]+', "곱셈 기호(x) 사용 (latex \\times 권장)"),
            (r'[a-zA-Z0-9]+/[a-zA-Z0-9]+', "분수 형태 표현 가능성"),
        ]
        
        for pattern, reason in patterns:
            match = re.search(pattern, clean_text)
            if match:
                results.append(ValidationResult(
                    rule_id="missing_inlinelatex",
                    severity=Severity.WARNING,
                    message=f"텍스트 내에 수식/과학적 표현({match.group()})이 발견되었으나 inlinelatex($...$) 처리가 누락된 것으로 의심됩니다. ({reason})",
                    details={"matched": match.group(), "reason": reason}
                ))
                # 하나라도 발견되면 중복 보고 방지를 위해 중단 (필요시 전체 탐색 가능)
                break
                
        return results

    def validate_document(self, doc: Document) -> List[ValidationResult]:
        """
        문서 (Document) 레벨의 검증을 수행합니다.
        주요 검증: figure 하위 요소(text_block, table, chart 등)의 종속 누락 여부 (IoA 90% 기준)
        """
        results = []
        
        # 0. 중복 anno_id 검사 (루트 레벨만 검사하여 sub_regions 오탐 방지)
        all_ids = set()
        duplicate_ids = set()
        
        if doc.raw_data and 'layout_dets' in doc.raw_data:
            for item in doc.raw_data['layout_dets']:
                if isinstance(item, dict) and 'anno_id' in item:
                    aid = item['anno_id']
                    if aid in all_ids:
                        duplicate_ids.add(aid)
                    else:
                        all_ids.add(aid)
            
        for dup_id in duplicate_ids:
            results.append(
                ValidationResult(
                    rule_id="duplicate_anno_id",
                    severity=Severity.ERROR,
                    message=f"문서 내에 중복된 anno_id({dup_id})가 존재합니다. (메인 목록과 sub_regions 등에서 ID 충돌)",
                    details={"anno_id": dup_id}
                )
            )
        
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

        # 3. Table: HTML 내 anno_id 참조 유효성 검증 및 물리적 포함 관계 검증
        results.extend(self._validate_table_html_anno_refs(doc))
        results.extend(self._validate_table_spatial_inclusion(doc))
        
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
                    rel_parent = rel.get('parent') if 'parent' in rel else rel.get('source_anno_id')
                    rel_son = rel.get('son') if 'son' in rel else rel.get('target_anno_id')
                    if rel_parent == figure.anno_id:
                        linked_child_ids.add(rel_son)

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
        # anno_id_N (숫자) 패턴 - 더 유연하게 (따옴표 포함 가능성 고려)
        pattern_img = re.compile(r'anno_id(?:_|[^\d]*?)\s*(\d+)', re.IGNORECASE)
        
        tables = [ann for ann in doc.layout_dets if ann.category_type == 'table']
        for tbl in tables:
            html = ''
            if tbl.html:
                 html = str(tbl.html)
            elif tbl.raw_data:
                html = str(tbl.raw_data.get('html', ''))
            
            if not html:
                continue
            
            # 두 패턴으로 참조 ID 추출
            ref_ids: Set[int] = set()
            for m in pattern_dollar.finditer(html):
                try:
                    ref_ids.add(int(m.group(1)))
                except ValueError: continue
            for m in pattern_img.finditer(html):
                try:
                    ref_ids.add(int(m.group(1)))
                except ValueError: continue
            
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

    def _validate_table_spatial_inclusion(self, doc: Document) -> List[ValidationResult]:
        """Table 영역 내에 물리적으로 포함된 figure, chart, table이 HTML 내에 참조되고 있는지 검증합니다."""
        results = []
        tables = [ann for ann in doc.layout_dets if ann.category_type == 'table']
        # 하위 요소 후보: figure, chart, table
        candidates = [ann for ann in doc.layout_dets if ann.category_type in ['figure', 'chart', 'table']]
        
        # HTML 내 anno_id 참조 패턴 (유연하게)
        pattern_ref = re.compile(r'anno_id(?:_|[^\d]*?)\s*(\d+)', re.IGNORECASE)

        for tbl in tables:
            # HTML 추출
            html = ''
            if tbl.html:
                 html = str(tbl.html)
            elif tbl.raw_data:
                html = str(tbl.raw_data.get('html', ''))
            
            # HTML 내 존재하는 모든 참조 ID 수집
            found_ids: Set[int] = set()
            if html:
                for m in pattern_ref.finditer(html):
                    try:
                        found_ids.add(int(m.group(1)))
                    except ValueError: continue
            
            for child in candidates:
                if child.anno_id == tbl.anno_id:
                    continue # 자기 자신 제외
                
                # 유효한 폴리곤인지 확인
                if not child.poly or len(child.poly) < 6 or not tbl.poly or len(tbl.poly) < 6:
                    continue
                    
                # 90% 이상 포함되어 있는지 확인
                ioa = self._calculate_ioa(tbl.poly, child.poly)
                
                if ioa >= 0.90:
                    if child.anno_id not in found_ids:
                        results.append(ValidationResult(
                            rule_id="table_html_missing_spatial_ref",
                            severity=Severity.ERROR,
                            message=(
                                f"Table(ID:{tbl.anno_id}) 영역 내에 '{child.category_type}'(ID:{child.anno_id})이 "
                                f"위치(IoA:{ioa:.1%})하지만 HTML 내에 참조(<img src='anno_id_{child.anno_id}'>)가 누락되었습니다."
                            ),
                            details={
                                "anno_id": tbl.anno_id, 
                                "missing_id": child.anno_id, 
                                "child_type": child.category_type,
                                "ioa": ioa
                            }
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

    # ---------------- LaTeX 검증 보조 메서드 ----------------
    def _extract_inline_latex(self, text: str) -> List[tuple]:
        """텍스트 내의 inline/display LaTeX 수식을 추출합니다. 반환값: [(formula, (start, end)), ...]"""
        results: List[tuple] = []
        if not text:
            return results
        # display math $$...$$ (DOTALL to capture newlines)
        for m in re.finditer(r'(?<!\\)\$\$(.+?)(?<!\\)\$\$', text, flags=re.DOTALL):
            results.append((m.group(1), m.span(1)))
        # inline math $...$
        for m in re.finditer(r'(?<!\\)\$(.+?)(?<!\\)\$', text):
            results.append((m.group(1), m.span(1)))
        return results

    def _validate_latex_syntax(self, latex_str: str, source: str = 'latex', ann: Optional[Annotation] = None, span: Optional[tuple] = None) -> List[ValidationResult]:
        """간단한 LaTeX 문법 검사기를 제공합니다. pylatexenc가 설치되어 있으면 파싱을 시도하고,
        중괄호/대괄호 매칭, 구분자, 빈 수식 등을 검사합니다.
        """
        results: List[ValidationResult] = []
        if latex_str is None:
            return results
        s = str(latex_str)
        s_strip = s.strip()
        if s_strip == "":
            results.append(ValidationResult("latex_empty_formula", Severity.ERROR, "빈 수식입니다.", details={"source": source, "ann_id": getattr(ann, 'anno_id', None), "span": span}))
            return results

        # Delimiters: check for mixed usage $ and $$ in the raw string
        # If original string contains both $$ and single $ (not part of $$), flag mixed delimiter
        if "$$" in s and "$" in s.replace("$$", ""):
            results.append(ValidationResult("latex_mixed_delimiters", Severity.ERROR, "$$와 $가 혼합 사용되었습니다.", details={"source": source, "ann_id": getattr(ann, 'anno_id', None), "span": span}))

        # Braces matching {}
        stack = []
        for idx, ch in enumerate(s):
            if ch == '{':
                stack.append(idx)
            elif ch == '}':
                if not stack:
                    results.append(ValidationResult("latex_unmatched_braces", Severity.ERROR, "닫는 중괄호 '}'가 짝이 맞지 않습니다.", details={"pos": idx, "source": source, "ann_id": getattr(ann, 'anno_id', None), "span": span}))
                else:
                    stack.pop()
        if stack:
            results.append(ValidationResult("latex_unmatched_braces", Severity.ERROR, "여는 중괄호 '{'가 닫히지 않았습니다.", details={"pos": stack[-1], "source": source, "ann_id": getattr(ann, 'anno_id', None), "span": span}))

        # Square brackets matching []
        stack_b = []
        for idx, ch in enumerate(s):
            if ch == '[':
                stack_b.append(idx)
            elif ch == ']':
                if not stack_b:
                    results.append(ValidationResult("latex_unmatched_brackets", Severity.ERROR, "닫는 대괄호 ']'가 짝이 맞지 않습니다.", details={"pos": idx, "source": source, "ann_id": getattr(ann, 'anno_id', None), "span": span}))
                else:
                    stack_b.pop()
        if stack_b:
            results.append(ValidationResult("latex_unmatched_brackets", Severity.ERROR, "여는 대괄호 '['가 닫히지 않았습니다.", details={"pos": stack_b[-1], "source": source, "ann_id": getattr(ann, 'anno_id', None), "span": span}))

        # Use pylatexenc to attempt a parse if available
        if HAS_PYLATEXENC:
            try:
                walker = LatexWalker(s)
                nodelist, pos, len_ = walker.get_latex_nodes(pos=0)

                # collect unknown macros (best-effort): treat any macro not in COMMON set as a warning
                COMMON_MACROS = {
                    'frac','sqrt','sum','int','lim','sin','cos','tan','log','ln','exp',
                    'alpha','beta','gamma','delta','epsilon','theta','phi','psi','omega',
                    'mathrm','mathbf','mathit','text','left','right','begin','end','label','ref',
                    'frac','cdot','times','leq','geq','le','ge','neq','pm','mp'
                }
                unknown = set()
                def _walk(nodes):
                    for node in nodes:
                        try:
                            from pylatexenc.latexwalker import LatexMacroNode
                            if isinstance(node, LatexMacroNode):
                                name = getattr(node, 'macroname', None)
                                if name and name not in COMMON_MACROS:
                                    unknown.add(name)
                        except Exception:
                            pass
                        # traverse children
                        child_nodes = getattr(node, 'nodelist', None)
                        if child_nodes:
                            _walk(child_nodes)
                _walk(nodelist)
                if unknown:
                    results.append(ValidationResult("latex_invalid_command", Severity.WARNING, f"알 수 없는 LaTeX 매크로 발견: {', '.join(sorted(unknown))}", details={"unknown_macros": list(sorted(unknown)), "source": source, "ann_id": getattr(ann, 'anno_id', None), "span": span}))

            except Exception as e:
                # Parsing error -> treat as syntax error
                results.append(ValidationResult("latex_invalid_command", Severity.ERROR, f"LaTeX 파싱 실패: {e}", details={"source": source, "ann_id": getattr(ann, 'anno_id', None), "span": span}))
        else:
            # No parser available: signal as warning
            results.append(ValidationResult("latex_no_parser", Severity.WARNING, "pylatexenc가 설치되어 있지 않아 상세 파싱을 수행하지 못했습니다.", details={"source": source, "ann_id": getattr(ann, 'anno_id', None)}))

        return results
