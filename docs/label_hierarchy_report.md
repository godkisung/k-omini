# 블록 단위 라벨 계층 구조 가이드

이 문서는 'block' 단위 라벨링을 위한 카테고리별 계층 구조와 주요 특성을 설명합니다.

---
## 그룹: `code_txt, figure_caption, figure_footnote, page_footnote, table_caption, table_footnote, text_block, title`

**주요 특성:**
- `merge_list` (비어 있지 않은 인스턴스 발견)
- `line_with_spans` (비어 있지 않은 인스턴스 발견)

**포함되는 카테고리별 상세 정보:**

### 카테고리: `code_txt`

- **설명:** 코드 블록 텍스트.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, order, poly, text

### 카테고리: `figure_caption`

- **설명:** `figure`에 대한 설명 텍스트.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, order, poly, text

### 카테고리: `figure_footnote`

- **설명:** 그림에 대한 각주.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, order, poly, text

### 카테고리: `page_footnote`

- **설명:** 페이지 하단에 위치하는 각주.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, order, poly, text
- **비고:**
  - 키 `order`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `table_caption`

- **설명:** `table`에 대한 설명 텍스트.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, order, poly, text

### 카테고리: `table_footnote`

- **설명:** `table`에 대한 각주 텍스트.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, order, poly, text

### 카테고리: `text_block`

- **설명:** 일반적인 본문 단락.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, order, poly, text

### 카테고리: `title`

- **설명:** 문서, 챕터, 섹션 등의 제목을 나타내는 텍스트.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, order, poly, text

---
## 그룹: `equation_caption, equation_isolated, footer, header, page_number, reference`

**주요 특성:**
- `line_with_spans` (비어 있지 않은 인스턴스 발견)

**포함되는 카테고리별 상세 정보:**

### 카테고리: `equation_caption`

- **설명:** 수식에 대한 설명 텍스트.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, category_type, ignore, line_with_spans, order, poly, text
- **비고:**
  - 키 `attribute`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `equation_isolated`

- **설명:** 독립된 줄을 차지하는 수학 공식 또는 화학식.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.equation_language, attribute.formula_type, category_type, ignore, latex, line_with_spans, order, poly

### 카테고리: `footer`

- **설명:** 페이지 하단에 반복적으로 나타나는 꼬리글.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, line_with_spans, order, poly, text
- **비고:**
  - 키 `order`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `header`

- **설명:** 페이지 상단에 반복적으로 나타나는 머리글.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, line_with_spans, order, poly, text
- **비고:**
  - 키 `order`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `page_number`

- **설명:** 페이지 번호.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, line_with_spans, order, poly, text
- **비고:**
  - 키 `order`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `reference`

- **설명:** 참고 문헌 항목.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.text_background, attribute.text_language, attribute.text_rotate, category_type, ignore, line_with_spans, order, poly, text

---
## 그룹: `abandon, code_txt_caption, equation_explanation, figure, need_mask, table, table_mask, text_mask`

**주요 특성:**
- `merge_list` 및 `line_with_spans` (비어 있지 않은 인스턴스 없음)

**포함되는 카테고리별 상세 정보:**

### 카테고리: `abandon`

- **설명:** 분석에서 제외할 영역 (예: 광고, 노이즈).
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, category_type, ignore, order, poly
- **비고:**
  - 키 `order`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `code_txt_caption`

- **설명:** 코드 블록에 대한 설명 텍스트.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, category_type, ignore, line_with_spans, order, poly, text
- **비고:**
  - 키 `attribute`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.
  - 키 `line_with_spans`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `equation_explanation`

- **설명:** 수식에 대한 상세 설명.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, category_type, ignore, line_with_spans, order, poly, text
- **비고:**
  - 키 `attribute`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.
  - 키 `line_with_spans`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `figure`

- **설명:** 이미지, 차트, 다이어그램 등의 시각적 자료.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, category_type, ignore, order, poly

### 카테고리: `need_mask`

- **설명:** 마스킹이 필요한 영역.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, category_type, ignore, order, poly
- **비고:**
  - 키 `order`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

### 카테고리: `table`

- **설명:** 행과 열의 격자 구조를 가지는 모든 종류의 표 데이터.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, attribute, attribute.include_background, attribute.include_equation, attribute.include_photo, attribute.language, attribute.line, attribute.table_layout, attribute.with_span, category_type, html, ignore, order, poly

### 카테고리: `table_mask`

- **설명:** 테이블 위에 겹쳐진 마스크 영역.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, category_type, ignore, order, poly

### 카테고리: `text_mask`

- **설명:** 텍스트 위에 겹쳐져 내용을 가리는 마스크 영역.
- **발견된 총 블록 수:** 0
- **항상 존재하는 주요 키:** anno_id, category_type, ignore, order, poly
- **비고:**
  - 키 `order`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다.

---
