# 어노테이션 라벨링 규칙 (Block 단위 기준)

이 문서는 `block` 단위로 라벨링될 때의 카테고리별 속성 및 구조를 상세히 기술한 가이드입니다.

---
## 그룹: `need_mask`

**포함되는 카테고리 및 설명:**
- **`need_mask`**: 마스킹이 필요한 영역.

### 공통 속성
이 그룹에 포함된 모든 조합은 아래의 키 구조를 가집니다.

| 키 이름 | 데이터 타입 | 설명 |
| --- | --- | --- |
| `anno_id` | `int` | 각 어노테이션의 고유 식별자. |
| `category_type` | `str` | 객체의 유형 (예: "text_block", "table"). |
| `ignore` | `bool` | 해당 객체를 무시할지 여부. |
| `order` | `int` | 페이지 내에서 읽기 순서를 나타내는 정수. (NoneType도 가능) |
| `poly` | `list` | 객체의 외곽선 다각형 좌표 목록. |

### 특성
- `merge_list`와 `line_with_spans`를 포함하지 않습니다.

### 공통 작성 가이드
1. 이 그룹의 조합은 주로 기본 키(poly, order 등)만을 사용합니다.

---
## 그룹: `equation_isolated`

**포함되는 카테고리 및 설명:**
- **`equation_isolated`**: 독립된 줄을 차지하는 수학 공식 또는 화학식.

### 공통 속성
이 그룹에 포함된 모든 조합은 아래의 키 구조를 가집니다.

| 키 이름 | 데이터 타입 | 설명 |
| --- | --- | --- |
| `anno_id` | `int` | 각 어노테이션의 고유 식별자. |
| `attribute` | `dict` | 별도 정의되지 않은 추가 속성을 포함하는 딕셔너리. |
| `attribute.equation_language` | `str` | 수식의 언어 정보 (예: "latex"). |
| `attribute.formula_type` | `str` | 수식의 타입 (예: "isolated", "inline", "matrix"). |
| `category_type` | `str` | 객체의 유형 (예: "text_block", "table"). |
| `ignore` | `bool` | 해당 객체를 무시할지 여부. |
| `latex` | `str` | 수식의 내용을 표현하는 LaTeX 문자열. |
| `line_with_spans` | `list` | 각 줄(line)과 단어(span)의 상세 좌표 정보가 포함된 복합 구조. |
| `order` | `int` | 페이지 내에서 읽기 순서를 나타내는 정수. (NoneType도 가능) |
| `poly` | `list` | 객체의 외곽선 다각형 좌표 목록. |

### 특성
- `line_with_spans`를 포함합니다.

### 공통 작성 가이드
1. 텍스트가 포함된 경우, `line_with_spans`를 사용하여 상세한 텍스트 구조를 명시해야 합니다.

---
## 그룹: `table`

**포함되는 카테고리 및 설명:**
- **`table`**: 행과 열의 격자 구조를 가지는 모든 종류의 표 데이터.

### 공통 속성
이 그룹에 포함된 모든 조합은 아래의 키 구조를 가집니다.

| 키 이름 | 데이터 타입 | 설명 |
| --- | --- | --- |
| `anno_id` | `int` | 각 어노테이션의 고유 식별자. |
| `attribute` | `dict` | 별도 정의되지 않은 추가 속성을 포함하는 딕셔너리. |
| `attribute.include_background` | `bool` | 객체 내에 배경 이미지/색상 포함 여부. |
| `attribute.include_equation` | `bool` | 객체 내에 수식 포함 여부. |
| `attribute.include_photo` | `bool` | 객체 내에 사진 포함 여부. |
| `attribute.language` | `str` | 콘텐츠의 주된 언어 (예: "ko", "en"). |
| `attribute.line` | `str` | 선(line)의 종류나 속성을 정의 (예: "solid", "dashed"). |
| `attribute.table_layout` | `str` | 테이블의 레이아웃 방향 (예: "horizontal", "vertical"). |
| `attribute.with_span` | `bool` | 객체가 스팬(span)을 포함하는지 여부. |
| `attribute.with_structured_text` | `bool` | 콘텐츠가 구조화된 텍스트(`line_with_spans`)를 포함하는지 여부. |
| `category_type` | `str` | 객체의 유형 (예: "text_block", "table"). |
| `html` | `str` | 테이블, 리스트 등의 구조와 내용을 표현하는 HTML 코드. |
| `ignore` | `bool` | 해당 객체를 무시할지 여부. |
| `line_with_spans` | `list` | 각 줄(line)과 단어(span)의 상세 좌표 정보가 포함된 복합 구조. |
| `order` | `int` | 페이지 내에서 읽기 순서를 나타내는 정수. (NoneType도 가능) |
| `poly` | `list` | 객체의 외곽선 다각형 좌표 목록. |
| `table_edit_status` | `str` | 테이블 데이터의 검수 상태 (`good`, `partial`, `bad`, `raw`). |

### 특성
- `line_with_spans`를 포함합니다.

### 공통 작성 가이드
1. 텍스트가 포함된 경우, `line_with_spans`를 사용하여 상세한 텍스트 구조를 명시해야 합니다.

---
## 그룹: `table_mask`

**포함되는 카테고리 및 설명:**
- **`table_mask`**: 테이블 위에 겹쳐진 마스크 영역.

### 공통 속성
이 그룹에 포함된 모든 조합은 아래의 키 구조를 가집니다.

| 키 이름 | 데이터 타입 | 설명 |
| --- | --- | --- |
| `anno_id` | `int` | 각 어노테이션의 고유 식별자. |
| `attribute` | `dict` | 별도 정의되지 않은 추가 속성을 포함하는 딕셔너리. |
| `attribute.include_background` | `bool` | 객체 내에 배경 이미지/색상 포함 여부. |
| `attribute.include_equation` | `bool` | 객체 내에 수식 포함 여부. |
| `attribute.include_photo` | `bool` | 객체 내에 사진 포함 여부. |
| `attribute.language` | `str` | 콘텐츠의 주된 언어 (예: "ko", "en"). |
| `attribute.line` | `str` | 선(line)의 종류나 속성을 정의 (예: "solid", "dashed"). |
| `attribute.table_layout` | `str` | 테이블의 레이아웃 방향 (예: "horizontal", "vertical"). |
| `attribute.with_span` | `bool` | 객체가 스팬(span)을 포함하는지 여부. |
| `category_type` | `str` | 객체의 유형 (예: "text_block", "table"). |
| `ignore` | `bool` | 해당 객체를 무시할지 여부. |
| `line_with_spans` | `list` | 각 줄(line)과 단어(span)의 상세 좌표 정보가 포함된 복합 구조. |
| `order` | `int` | 페이지 내에서 읽기 순서를 나타내는 정수. (NoneType도 가능) |
| `poly` | `list` | 객체의 외곽선 다각형 좌표 목록. |

### 특성
- `line_with_spans`를 포함합니다.

### 공통 작성 가이드
1. 텍스트가 포함된 경우, `line_with_spans`를 사용하여 상세한 텍스트 구조를 명시해야 합니다.

---
## 그룹: `footer, header, page_number, reference`

**포함되는 카테고리 및 설명:**
- **`footer`**: 페이지 하단에 반복적으로 나타나는 꼬리글.
- **`header`**: 페이지 상단에 반복적으로 나타나는 머리글.
- **`page_number`**: 페이지 번호.
- **`reference`**: 참고 문헌 항목.

### 공통 속성
이 그룹에 포함된 모든 조합은 아래의 키 구조를 가집니다.

| 키 이름 | 데이터 타입 | 설명 |
| --- | --- | --- |
| `anno_id` | `int` | 각 어노테이션의 고유 식별자. |
| `attribute` | `dict` | 별도 정의되지 않은 추가 속성을 포함하는 딕셔너리. |
| `attribute.text_background` | `str` | 텍스트 배경의 종류/색상. |
| `attribute.text_language` | `str` | 텍스트의 언어. (예: "ko", "en"). |
| `attribute.text_rotate` | `str` | 텍스트의 회전 상태 (예: "0", "90"). |
| `category_type` | `str` | 객체의 유형 (예: "text_block", "table"). |
| `ignore` | `bool` | 해당 객체를 무시할지 여부. |
| `line_with_spans` | `list` | 각 줄(line)과 단어(span)의 상세 좌표 정보가 포함된 복합 구조. |
| `order` | `int` | 페이지 내에서 읽기 순서를 나타내는 정수. (NoneType도 가능) |
| `poly` | `list` | 객체의 외곽선 다각형 좌표 목록. |
| `text` | `str` | 객체의 전체 텍스트 내용. |

### 특성
- `line_with_spans`를 포함합니다.

### 공통 작성 가이드
1. 텍스트가 포함된 경우, `line_with_spans`를 사용하여 상세한 텍스트 구조를 명시해야 합니다.

---
## 그룹: `abandon, figure, text_mask`

**포함되는 카테고리 및 설명:**
- **`abandon`**: 분석에서 제외할 영역 (예: 광고, 노이즈).
- **`figure`**: 이미지, 차트, 다이어그램 등의 시각적 자료.
- **`text_mask`**: 텍스트 위에 겹쳐져 내용을 가리는 마스크 영역.

### 공통 속성
이 그룹에 포함된 모든 조합은 아래의 키 구조를 가집니다.

| 키 이름 | 데이터 타입 | 설명 |
| --- | --- | --- |
| `anno_id` | `int` | 각 어노테이션의 고유 식별자. |
| `attribute` | `dict` | 별도 정의되지 않은 추가 속성을 포함하는 딕셔너리. |
| `category_type` | `str` | 객체의 유형 (예: "text_block", "table"). |
| `ignore` | `bool` | 해당 객체를 무시할지 여부. |
| `line_with_spans` | `list` | 각 줄(line)과 단어(span)의 상세 좌표 정보가 포함된 복합 구조. |
| `order` | `int` | 페이지 내에서 읽기 순서를 나타내는 정수. (NoneType도 가능) |
| `poly` | `list` | 객체의 외곽선 다각형 좌표 목록. |

### 특성
- `line_with_spans`를 포함합니다.

### 공통 작성 가이드
1. 텍스트가 포함된 경우, `line_with_spans`를 사용하여 상세한 텍스트 구조를 명시해야 합니다.

---
## 그룹: `code_txt_caption, equation_caption, equation_explanation`

**포함되는 카테고리 및 설명:**
- **`code_txt_caption`**: 코드 블록에 대한 설명 텍스트.
- **`equation_caption`**: 수식에 대한 설명 텍스트.
- **`equation_explanation`**: 수식에 대한 상세 설명.

### 공통 속성
이 그룹에 포함된 모든 조합은 아래의 키 구조를 가집니다.

| 키 이름 | 데이터 타입 | 설명 |
| --- | --- | --- |
| `anno_id` | `int` | 각 어노테이션의 고유 식별자. |
| `attribute` | `dict` | 별도 정의되지 않은 추가 속성을 포함하는 딕셔너리. |
| `category_type` | `str` | 객체의 유형 (예: "text_block", "table"). |
| `ignore` | `bool` | 해당 객체를 무시할지 여부. |
| `line_with_spans` | `list` | 각 줄(line)과 단어(span)의 상세 좌표 정보가 포함된 복합 구조. |
| `order` | `int` | 페이지 내에서 읽기 순서를 나타내는 정수. (NoneType도 가능) |
| `poly` | `list` | 객체의 외곽선 다각형 좌표 목록. |
| `text` | `str` | 객체의 전체 텍스트 내용. |

### 특성
- `line_with_spans`를 포함합니다.

### 공통 작성 가이드
1. 텍스트가 포함된 경우, `line_with_spans`를 사용하여 상세한 텍스트 구조를 명시해야 합니다.

---
## 그룹: `code_txt, figure_caption, figure_footnote, page_footnote, table_caption, table_footnote, text_block, title`

**포함되는 카테고리 및 설명:**
- **`code_txt`**: 코드 블록 텍스트.
- **`figure_caption`**: `figure`에 대한 설명 텍스트.
- **`figure_footnote`**: 그림에 대한 각주.
- **`page_footnote`**: 페이지 하단에 위치하는 각주.
- **`table_caption`**: `table`에 대한 설명 텍스트.
- **`table_footnote`**: `table`에 대한 각주 텍스트.
- **`text_block`**: 일반적인 본문 단락.
- **`title`**: 문서, 챕터, 섹션 등의 제목을 나타내는 텍스트.

### 공통 속성
이 그룹에 포함된 모든 조합은 아래의 키 구조를 가집니다.

| 키 이름 | 데이터 타입 | 설명 |
| --- | --- | --- |
| `anno_id` | `int` | 각 어노테이션의 고유 식별자. |
| `attribute` | `dict` | 별도 정의되지 않은 추가 속성을 포함하는 딕셔너리. |
| `attribute.text_background` | `str` | 텍스트 배경의 종류/색상. |
| `attribute.text_language` | `str` | 텍스트의 언어. (예: "ko", "en"). |
| `attribute.text_rotate` | `str` | 텍스트의 회전 상태 (예: "0", "90"). |
| `category_type` | `str` | 객체의 유형 (예: "text_block", "table"). |
| `ignore` | `bool` | 해당 객체를 무시할지 여부. |
| `line_with_spans` | `list` | 각 줄(line)과 단어(span)의 상세 좌표 정보가 포함된 복합 구조. |
| `merge_list` | `list` | 셀 병합, 중첩 목록/표 등 복잡한 내부 구조를 표현하기 위한 복합 구조. |
| `order` | `int` | 페이지 내에서 읽기 순서를 나타내는 정수. (NoneType도 가능) |
| `poly` | `list` | 객체의 외곽선 다각형 좌표 목록. |
| `text` | `str` | 객체의 전체 텍스트 내용. |

### 특성
- `merge_list`를 포함합니다.
- `line_with_spans`를 포함합니다.

### 공통 작성 가이드
1. 객체 내에 중첩/그룹화된 요소가 있다면 `merge_list`를 사용하여 표현해야 합니다.
2. 텍스트가 포함된 경우, `line_with_spans`를 사용하여 상세한 텍스트 구조를 명시해야 합니다.

---
