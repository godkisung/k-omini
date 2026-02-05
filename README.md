# QA Visualizer - K-Omnidoc Benchmark 검수 도구

K-Omnidoc Benchmark 데이터셋의 품질 검증 및 시각화를 위한 Streamlit 기반 검수 도구입니다.

## 📋 주요 기능

### 1. **Streamlit 검수 인터페이스** ⭐ 신규
- 🔢 **페이지 번호 직접 이동**: 원하는 페이지로 즉시 점프
- 🤖 **PaddleOCR 자동 검증**: 텍스트 오타 자동 감지
  - 유사도 (%) 표시
  - Edit Distance (편집 거리) 표시
  - 어노테이션 vs OCR 텍스트 전체 비교
- 🖼️ 이미지 위 어노테이션 시각화
- ✅ 실시간 검증 결과 확인
- 🔎 파일 검색 및 필터링

### 2. **데이터 검증**
- ✅ 필수 키 존재 여부 검증
- ✅ 언어 일관성 검증 (한국어/영어/혼합)
- ✅ 부모-자식 관계 논리 검증
- ✅ 차트 속성 검증
- ✅ 참조 무결성 검증
- ✅ 폴리곤 좌표 유효성 검증
- ✅ Order 중복 검증
- ✅ 텍스트 길이 이상치 검증
- ✅ 회전 각도 유효성 검증

### 3. **시각화**
- 📊 어노테이션 시각화 (폴리곤 오버레이)
- 🔗 관계 시각화 (parent-son, truncated)
- 🎨 카테고리별 색상 구분
- 🖱️ 클릭 가능한 어노테이션 선택

### 4. **통계 분석**
- 📈 데이터셋 전체 통계
- 🔍 이상치 탐지
- 📊 카테고리/언어 분포 분석

##  설치 방법

### 필수 요구사항
- Python 3.8 이상
- conda 또는 pip

### 의존성 설치

```bash
# conda 환경 사용 (권장)
conda run -n base pip install -r requirements.txt

# 또는 pip 직접 사용
pip install -r requirements.txt
```

### PaddleOCR 설치 (선택사항)

OCR 자동 검증 기능을 사용하려면 PaddleOCR을 설치하세요:

```bash
conda run -n base pip install paddlepaddle paddleocr
```

## 📖 사용법

### 1. Streamlit 검수 도구 (권장)

대화형 웹 인터페이스를 실행합니다:

```bash
streamlit run streamlit_app.py
```

웹 브라우저가 자동으로 열리며, 다음 기능을 사용할 수 있습니다:

#### 주요 기능:

**� 파일 탐색**
- 검색어로 파일 필터링
- 페이지 번호 직접 입력하여 이동
- 이전/다음 파일 버튼

**🔍 검수**
- 어노테이션 선택 및 상세 정보 확인
- 텍스트, LaTeX, HTML 테이블 렌더링
- 속성 및 검증 결과 확인

**🤖 OCR 자동 검증** (PaddleOCR 설치 시)
- 각 텍스트 박스별 자동 검증
- 유사도 및 Edit Distance 표시
- 어노테이션 텍스트 vs OCR 추출 텍스트 비교

**⚙️ 필터**
- 카테고리별 필터링
- 검증 오류만 보기

### 2. CLI 기반 검증

전체 데이터셋을 검증하고 오류 리포트를 출력합니다:

```bash
python validate_data.py 
```

### 3. Python 코드에서 사용

```python
from qa_visualizer.core import Document
from qa_visualizer.validation import run_full_doc_validation
from qa_visualizer.analytics import generate_dataset_statistics

# 문서 로드
doc = Document.from_json("path/to/annotation.json")

# 검증 실행
results = run_full_doc_validation(doc.raw_data)
for result in results:
    print(f"[{result.severity.name}] {result.message}")

# 데이터셋 통계
stats = generate_dataset_statistics("path/to/data_dir")
print(f"총 파일 수: {stats['총_파일_수']}")
```

## 🧪 테스트

프로젝트는 pytest를 사용한 포괄적인 테스트 스위트를 포함합니다:

```bash
# 모든 테스트 실행
conda run -n base pytest tests/ -v

# 특정 테스트 파일만 실행
conda run -n base pytest tests/test_validation.py -v

# 커버리지 리포트 생성
conda run -n base pytest tests/ --cov=qa_visualizer --cov-report=html
```

## 📁 프로젝트 구조

```
.
├── qa_visualizer/          # 메인 패키지
│   ├── __init__.py
│   ├── config.py          # 설정 상수 (OCR 설정 포함)
│   ├── core.py            # 핵심 데이터 모델
│   ├── drawing.py         # 시각화 함수
│   ├── validation.py      # 검증 로직 (OCR 검증 포함)
│   ├── analytics.py       # 통계 분석
│   └── ocr_utils.py       # PaddleOCR 유틸리티 (신규)
├── pages/                 # Streamlit 페이지
│   └── inspect_page.py    # 검수 페이지 (OCR 검증 UI 포함)
├── tests/                 # 테스트 코드
├── streamlit_app.py       # Streamlit 웹 UI
├── validate_data.py       # CLI 검증 스크립트
├── requirements.txt       # 의존성 목록
├── pytest.ini             # pytest 설정
└── README.md              # 이 파일
```

## 🔍 OCR 자동 검증 상세

### 작동 원리

1. **텍스트 추출**: PaddleOCR로 어노테이션 영역에서 실제 텍스트 추출
2. **유사도 계산**: 레벤슈타인 거리 기반 유사도 계산
3. **결과 표시**: 
   - ✅ 유사도 90% 이상: 검증 통과
   - ⚠️ 유사도 70~90%: 경고
   - 🔴 유사도 70% 미만: 오류

### 표시 정보

- **유사도**: 0~100% (높을수록 일치)
- **Edit Distance**: 편집 거리 (낮을수록 유사)
- **어노테이션 텍스트**: 작업자가 입력한 텍스트
- **OCR 추출 텍스트**: 실제 이미지에서 추출한 텍스트
- **텍스트 길이**: 각 텍스트의 문자 수

### 설정 커스터마이징

`qa_visualizer/config.py`에서 OCR 설정을 변경할 수 있습니다:

```python
# OCR 설정
OCR_ENABLED = True  # OCR 기능 활성화 여부
OCR_SIMILARITY_THRESHOLD = 0.9  # 텍스트 유사도 임계값 (90%)
```

## 🎯 검수 워크플로우

1. **파일 선택**: 사이드바에서 파일 검색 또는 페이지 번호로 이동
2. **어노테이션 검수**: 이미지에서 어노테이션 클릭 또는 화살표 버튼으로 이동
3. **내용 확인**: 텍스트, LaTeX, HTML 테이블 확인
4. **OCR 검증**: 자동으로 표시되는 OCR 검증 결과 확인
5. **검증 결과**: 하단 "검증 결과" 섹션에서 모든 검증 규칙 확인

## � 개발 참고 사항

### Streamlit 검수 도구: "첫 페이지 튕김" 이슈

검수 도구 사용 시 버튼 클릭 후 첫 페이지로 리다이렉트되는 현상의 기술적 원인:

1. **버튼 클릭**: 사용자가 "다음 어노테이션" 또는 "파일 이동" 버튼 클릭
2. **전체 재실행**: Streamlit 특성상 스크립트가 최상단부터 다시 실행
3. **검색어 유실**: 재실행 순간 사이드바의 `search_query`가 빈 값으로 인식되는 타이밍 이슈
4. **목록 변경**: 검색어가 사라지면서 `filtered_files`가 전체 목록으로 변경
5. **인덱스 꼬임**: 현재의 `file_index`가 새로 바뀐 목록 범위를 벗어나 0번으로 강제 초기화

**해결책**: 검색어(`last_search_query`)와 인덱스를 `st.session_state`에 고정하여 재실행 시에도 필터 목록 유지

## 🤝 기여 방법

1. 이 저장소를 포크합니다
2. 새 기능 브랜치를 생성합니다 (`git checkout -b feature/amazing-feature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/amazing-feature`)
5. Merge Request를 생성합니다

### 개발 가이드라인

- 모든 새 기능에는 테스트를 작성해주세요
- PEP 8 코딩 스타일을 따라주세요
- Type hints를 사용해주세요
- Docstring을 작성해주세요 (Google 스타일)

## 📝 라이선스

이 프로젝트는 K-Omnidoc Benchmark 프로젝트의 일부입니다.

## 📧 문의

문제가 발생하거나 제안사항이 있으시면 이슈를 등록해주세요.

---

**버전:** 1.0.0  
**최종 업데이트:** 2026-02-05  
**주요 변경사항:** 
- ✨ 페이지 번호 직접 이동 기능 추가
- ✨ PaddleOCR 기반 텍스트 자동 검증 추가
- ✨ Edit Distance 점수 표시
- ✨ 전체 텍스트 비교 기능
- 🐛 Streamlit 세션 상태 관리 개선
