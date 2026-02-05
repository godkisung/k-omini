# K-OmniDocBench QA Visualizer 기능 명세서 (Ver 2.2)

## 1. 개요 (Introduction)
* **목적:** K-Omnidoc Benchmark 데이터셋의 레이아웃 좌표, OCR 텍스트, LaTeX 수식 및 세부 속성(Attribute)의 무결성 검증.
* **핵심 기능:** 이미지 원본과 JSON 데이터(Text/LaTeX/HTML)의 1:1 대조 및 키 누락 자동 검사.

---

## 2. UI 레이아웃 및 시각화 명세
### 2.1. 메인 뷰어 (Main Canvas)
* [cite_start]**[F-01] Poly 드로잉:** `poly` 좌표(float/int)를 기반으로 다각형 박스 렌더링[cite: 56].
* [cite_start]**[F-02] 속성별 색상 코드:** `category_type`에 따라 박스 테두리 색상을 차별화하여 시각적 인지 속도 향상[cite: 46, 54].
* [cite_start]**[F-03] 관계 시각화:** `extra.relation`을 참조하여 `parent_son` 및 `truncated` 객체 간 연결 선 표시 [cite: 423-430, 468].

### 2.2. 정밀 검수 패널 (Inspector)
* **[F-04] OCR 대조 창:** 선택된 객체의 크롭 이미지와 추출된 `text` 혹은 `latex` 값을 병렬 배치.
* **[F-05] Key 유효성 검사:** 각 카테고리별 필수 키(Key)가 JSON 구조 내에 존재하는지 자동 스캔 및 누락 시 경고.

---

## 3. 카테고리별 필수 검수 키(Key) 리스트

사용자 분석 데이터를 바탕으로 정의된 카테고리별 필수 필드입니다. QA Tool은 객체 클릭 시 해당 키들이 올바르게 채워져 있는지 확인해야 합니다.

### 3.1. Text & Metadata Groups
[cite_start]텍스트 내용과 함께 언어, 회전도, 배경색 속성을 중점 검수합니다 [cite: 271-278].
* **해당 카테고리:** `code_txt`, `text_block`, `title`, `figure_caption`, `figure_footnote`, `table_caption`, `table_footnote`, `page_footnote`, `header`, `footer`, `page_number`, `reference`, `code_txt_caption`, `equation_caption`, `equation_explanation`
* **필수 검수 키:**
    * [cite_start]`anno_id`, `category_type`, `ignore`, `order`, `poly`, `text` [cite: 43-49, 264]
    * `attribute.text_background` (str/bool)
    * [cite_start]`attribute.text_language` (str: text_han, text_english 등) [cite: 273-277]
    * `attribute.text_rotate` (str/float)

### 3.2. Mathematical Formulas (Group 2)
[cite_start]LaTeX 렌더링 결과와 이미지의 일치성을 확인합니다 [cite: 68-75].
* **해당 카테고리:** `equation_isolated`
* **필수 검수 키:**
    * [cite_start]`anno_id`, `category_type`, `ignore`, `order`, `poly` [cite: 43-49]
    * [cite_start]`latex` (추출된 수식 문자열) [cite: 71]
    * [cite_start]`attribute.equation_language`, `attribute.formula_type` [cite: 72-74]

### 3.3. Tabular Structures (Group 3)
[cite_start]HTML 복원력과 표 특화 속성을 확인합니다 [cite: 76-95].
* **해당 카테고리:** `table`, `table_mask`
* **필수 검수 키:**
    * [cite_start]`anno_id`, `category_type`, `ignore`, `order`, `poly` [cite: 43-49]
    * [cite_start]`html` (테이블 태그 - table_mask는 제외 가능) [cite: 81, 93]
    * [cite_start]`table_edit_status` (검수 상태) [cite: 82]
    * [cite_start]`attribute.line`, `attribute.table_layout`, `attribute.language` [cite: 83, 87, 89]
    * [cite_start]`attribute.with_span`, `attribute.include_background/equation/photo` [cite: 84-86]

### 3.4. Specialized Visuals (Group 7 & Chart)
[cite_start]중첩 구조와 차트 난이도별 속성을 확인합니다 [cite: 247-251].
* **해당 카테고리:** `figure`, `chart`
* **필수 검수 키 (Figure):**
    * [cite_start]`anno_id`, `category_type`, `ignore`, `order`, `poly` [cite: 43-49]
    * [cite_start]`attribute.contains_elements`, `sub_regions` [cite: 16, 248]
    * [cite_start]`attribute.sub_regions.type`, `attribute.sub_regions.region_poly` [cite: 250-251]
* **필수 검수 키 (Chart):**
    * `anno_id`, `category_type`, `ignore`, `order`, `poly`, `html`
    * `attribute.chart_type`, `attribute.language`
    * `attribute.include_background/equation/photo`

### 3.5. Excluded & Mask Groups
* **해당 카테고리:** `abandon`, `need_mask`, `text_mask`, `table_mask`
* [cite_start]**필수 검수 키:** `anno_id`, `category_type`, `ignore`, `order`, `poly` [cite: 64-67, 230-236]

---

## 4. 데이터 무결성 자동 검증 규칙 (Validation Rules)

| ID | 검증 규칙 명칭 | 상세 내용 |
| :--- | :--- | :--- |
| **V-01** | **LaTeX Renderer** | [cite_start]`latex` 필드 값을 시각화하여 원본 이미지 수식과 대조 [cite: 71] |
| **V-02** | **Key Presence** | 카테고리별 정의된 `attribute` 키가 JSON 내에 존재하는지 전수 조사 |
| **V-03** | **Logic Cross-check** | `chart` 카테고리에서 수치 유무(`is_indexed`)와 `text` 존재 여부 교차 검증 |
| **V-04** | **Language Match** | [cite_start]`text_language` 속성값과 실제 추출된 `text` 문자열의 언어 일치 여부 확인 [cite: 273-277] |

---