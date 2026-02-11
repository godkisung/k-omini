# QA Visualizer - K-Omnidoc Benchmark 검수 도구

K-Omnidoc Benchmark 데이터셋의 품질 검증 및 시각화를 위한 Streamlit 기반 검수 도구입니다.

## 📋 주요 기능

### 1. **검수 인터페이스 (Inspect Page)**
- 🔢 **네비게이션**: 페이지/파일 번호 직접 이동, 키보드 단축키 지원
- 🖼️ **시각화**: 이미지 위 폴리곤 오버레이, 클릭하여 선택
- 📝 **콘텐츠 렌더링**: 텍스트, LaTeX 수식, HTML 표/차트 미리보기
- ✅ **실시간 검증**: 필수 키, 좌표 유효성, 부모-자식 관계 등 자동 검증

### 2. **OCR 검증 (OCR)**
  - **EasyOCR**: 빠른 초벌 인식 (CPU/GPU)
- 📊 **유사도 분석**: GT 텍스트와 OCR 결과의 유사도(Levenshtein) 자동 계산
- 🚦 **자동 판정**: 유사도에 따라 색상 코딩 (🟢통과 / 🟡주의 / 🔴오류)

### 3. **배치 처리 (Batch Processing)**
- ⚡ **일괄 OCR**: 전체 데이터셋에 대해 미리 OCR을 수행하 캐싱
- � **결과 저장**: `batch_ocr_results.csv`에 저장하여 검수 시 로딩 없이 즉시 결과 확인

### 4. **통계 분석 (Statistics)**
- 📈 **품질 지표**: 텍스트 길이, 폴리곤 크기 등 분포 시각화
- ⚠️ **이상치 탐지**: 규정된 범위를 벗어나는 비정상 데이터 자동 탐지 리포트

---

## 🛠️ 설치 방법

### 필수 요구사항
- Python 3.8 ~ 3.11
- CUDA 지원 GPU 권장

### 설치
```bash
# 1. 의존성 설치
pip install -r requirements.txt

---

## � 실행 방법

v2.0부터는 새로운 엔트리 포인트를 사용합니다.

```bash
streamlit run streamlit_app_v2.py
```

### 페이지 안내
1.  **Inspect Page**: 메인 검수 화면
2.  **Batch OCR**: 대량 데이터 일괄 처리 화면
3.  **Statistics**: 데이터셋 통계 및 이상치 분석 화면

---

## 📁 프로젝트 구조 (Refactored)

지저분했던 기존 구조(`qa_visualizer/`)를 폐기하고, 역할별로 명확히 분리된 `src/` 아키텍처를 도입했습니다.

```
.
├── src/                   # 핵심 로직 (Core Logic)
│   ├── config.py          # 설정 관리
│   ├── data_engine.py     # 데이터 로딩 및 모델 (Document, Annotation)
│   ├── analysis_engine.py # 분석 엔진 (OCR, Validation, Statistics)
│   └── render_engine.py   # 렌더링 엔진 (Image Drawing)
├── pages/                 # Streamlit 페이지
│   ├── inspect_page.py    
│   ├── batch_ocr.py       
│   └── statistics_page.py 
├── streamlit_app_v2.py    # 메인 실행 파일 (Entry Point)
├── requirements.txt       # 의존성 목록
└── README.md              # 이 문서
```

---

## ⚙️ 설정 (Configuration)

`src/config.py`에서 주요 설정을 변경할 수 있습니다.

*   `DATA_DIR`: 데이터셋 경로
*   `IMAGE_DIR`: 이미지 경로
*   `OCR_ENABLED`: OCR 기능 활성화 여부
*   `OCR_SIMILARITY_THRESHOLD`: 검증 통과 기준 유사도 (기본 0.9)

---