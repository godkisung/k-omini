# 어노테이션 라벨링 규칙 (상세 버전)

이 문서는 라벨링 규칙을 그룹화하고, `merge_list`와 같은 복합 구조에 대한 상세 규칙을 포함합니다.

---

## 1. 전체 공통 규칙 (모든 카테고리에 적용)

모든 어노테이션 객체는 `category_type`에 관계없이 다음과 같은 기본 키를 필수로 포함해야 합니다.

- `category_type`: 객체의 유형 (예: 'table', 'title').
- `poly`: 객체의 외곽선 다각형을 정의하는 좌표 목록.
- `ignore`: 해당 객체를 무시할지 여부를 나타내는 boolean 값 (`true`/`false`).
- `order`: 페이지 내에서 읽기 순서를 나타내는 정수.
- `anno_id`: 각 어노테이션의 고유 식별자.

---

## 2. 텍스트 기반 카테고리 그룹

이 그룹은 주된 내용이 텍스트인 카테고리를 포함합니다.

**포함되는 카테고리:** `title`, `text_block`, `figure_caption`, `footer`, `header`, `table_caption`, `table_footnote`, `page_number`

**공통 키:**
- `text`: 객체의 전체 텍스트 내용.
- `line_with_spans`: 각 줄과 단어의 좌표 정보가 포함된 상세 구조.

**공통 Attribute 키:**
- `attribute.text_language`: 텍스트의 언어 (예: 'text_en').
- `attribute.text_background`: 텍스트의 배경 (예: 'white').
- `attribute.text_rotate`: 텍스트의 회전 여부 (예: 'normal').

---

## 3. 테이블 카테고리

**포함되는 카테고리:** `table`

**설명:** 행과 열 구조를 가진 데이터. 내용은 `html` 키에 저장됩니다.

**고유 키:**
- `html`: 테이블의 구조와 내용을 표현하는 HTML 문자열.
- `table_edit_status`: 테이블 데이터의 검수 상태 (`good`, `partial`, `bad`, `raw`).

---

## 4. 기타 고유 카테고리

### `equation_isolated`
**설명:** 독립된 수학 공식 또는 화학식. 내용은 `latex` 키에 저장됩니다.
**고유 키:** `latex`

---

## 5. 단순 영역 카테고리 그룹

이 그룹은 주로 영역의 모양으로만 정의되며, 특별한 속성이 거의 없는 카테고리를 포함합니다.

**포함되는 카테고리:** `figure`, `abandon`, `text_mask`

**공통 키:** 이 카테고리들은 주로 **전체 공통 규칙**에 해당하는 키 외에 다른 특별한 키를 가지지 않습니다.

---

## 6. 복합 구조 상세 규칙 (`merge_list`)

`merge_list`는 글머리 기호(bullet points)나 번호 매기기 목록처럼, 의미적으로는 하나의 그룹이지만 시각적으로는 여러 개의 분리된 텍스트 블록으로 구성된 경우에 사용됩니다.

### 구조
1.  **부모 객체 (Parent Object):**
    -   전체 리스트(목록)를 포함하는 가장 큰 영역을 `poly`로 잡습니다.
    -   `category_type`은 `text_block`으로 지정합니다.
    -   이 부모 객체는 `merge_list` 키를 가집니다.
    -   부모의 `text` 키에는 모든 자식들의 `text` 내용이 합쳐져 들어갑니다.
2.  **자식 객체 (Child Objects):**
    -   `merge_list`는 배열(array)이며, 그 안에는 리스트의 각 항목(item)에 해당하는 자식 객체들이 들어갑니다.
    -   각 자식 객체 또한 완전한 어노테이션 구조를 가집니다 (e.g., `category_type`: 'text_block', `poly`, `text`, `line_with_spans` 등).

### 라벨링 절차
1.  **부모 블록 생성:** 전체 목록(예: 3개의 글머리 기호 목록 전체)을 감싸는 하나의 큰 `text_block`을 생성합니다.
2.  **자식 블록 생성:** 목록의 각 항목(예: 각 글머리 기호)에 대해 개별적인 `text_block`을 각각 생성합니다.
3.  **병합:** 2단계에서 생성한 모든 자식 블록들을 1단계에서 생성한 부모 블록의 `merge_list` 배열 안에 넣어줍니다.

**예시:**
```json
// 부모 객체
{
  "category_type": "text_block",
  "poly": [/* 전체 리스트를 감싸는 좌표 */],
  "text": "- 항목 1 - 항목 2",
  "merge_list": [
    // 자식 객체 1
    {
      "category_type": "text_block",
      "poly": [/* '항목 1'의 좌표 */],
      "text": "- 항목 1",
      "line_with_spans": [... ]
    },
    // 자식 객체 2
    {
      "category_type": "text_block",
      "poly": [/* '항목 2'의 좌표 */],
      "text": "- 항목 2",
      "line_with_spans": [... ]
    }
  ],
  ...
}
```
