# K-Omnidoc Benchmark 검수 및 중복 탐지 도구 (k-omini)

K-Omnidoc Benchmark 데이터셋의 품질 검증, 시각화 및 고도화된 문서 중복/템플릿 탐지를 위한 통합 도구입니다.

---

## 🚀 주요 기능

### 1. **3-Stage 이미지 유사도 및 중복 탐지 (Core Pipeline)**
단순한 픽셀 비교를 넘어, 딥러닝 기반의 3단계 분석을 통해 문서의 중복과 템플릿 재사용을 탐지합니다.

*   **Stage 1: 전체 이미지 시각적 유사도 (Exact Match)**
    *   **Model**: `Jina-CLIP-v2`
    *   **Logic**: 이미지 전체의 시각적 특징을 768차원 벡터로 추출합니다.
    *   **Purpose**: 동일 이미지 또는 미세한 변화가 있는 완전 중복 문서를 탐지합니다 (Cosine Similarity > 0.98).
*   **Stage 2: 구조적 레이아웃 분석 (Template Match)**
    *   **Model**: `DINOv2` (`dinov2-base`)
    *   **Logic**: 텍스트 내용을 제외하고, 레이아웃 정보(Bounding Box)만을 이용해 '구조 맵'을 렌더링한 후 특징을 추출합니다.
    *   **Purpose**: 텍스트 내용은 다르지만 서식(Template)이 동일한 문서를 그룹화합니다.
*   **Stage 3: 객체 단위 부분 일치 (Region Match)**
    *   **Model**: `Florence-2` (Detection) + `DINOv2` (Embedding)
    *   **Logic**: Florence-2로 표(Table), 서명(Signature), 직인(Stamp) 등을 탐지하고, 각 영역을 크롭하여 개별 임베딩을 생성합니다.
    *   **Purpose**: 문서 내 특정 컴포넌트(예: 동일한 직인 사용)의 재사용을 탐지합니다.

### 2. **검수 인터페이스 (Inspect Page)**
*   🔢 **네비게이션**: 페이지/파일 번호 이동 및 단축키 지원
*   🖼️ **폴리곤 오버레이**: 이미지 위 레이아웃 박스 시각화 및 직접 선택
*   📝 **콘텐츠 렌더링**: LaTeX 수식, HTML 표, 차트 등 복합 데이터 미리보기

### 3. **데이터 엔진 및 통계 (Analysis & Stats)**
*   📊 **유사도 분석**: GT와 OCR 결과 간의 Levenshtein 유사도 자동 계산
*   📈 **통계 리포트**: 텍스트 길이, 데이터 분포, 이상치(Outlier) 탐지

---

## 🛠️ 하드웨어 자동 최적화 (Environment Aware)

프로토타이핑 환경과 실서비스 환경의 하드웨어 차이를 자동으로 감지하여 최적의 성능을 냅니다.

*   **Pascal GPU (GTX 1080 Ti 등)**: FP16 연산 불안정성을 고려하여 **FP32** 강제 할당 및 안정성 우선 모드 작동.
*   **Modern GPU (RTX 5070 Ti, Ada 등)**: 효율 극대화를 위한 **FP16** 고속 연산 및 대용량 배치 처리 지원.
*   **Multi-GPU 지원**: Stage 1(Heavy)과 Stage 2/3(Light) 모델을 서로 다른 GPU에 분산 배치하여 병렬 처리 효율 증대.

---

## 📁 프로젝트 구조

```text
.
├── src/                   # 핵심 로직 (Core Logic)
│   ├── core/              # 엔진 핵심 모듈
│   │   ├── dedup_engine.py    # 3-Stage 중복 탐지 파이프라인
│   │   ├── ocr_engine.py      # OCR 통합 엔진
│   │   ├── models.py          # Annotation/Document 모델
│   │   └── visualizer.py      # 이미지 렌더링 최적화
│   ├── analysis/          # 검증 및 통계
│   │   ├── validator.py       # 데이터 스키마 유효성 검사
│   │   └── outlier_detector.py # 이상치 탐지 엔진
│   ├── sampling/          # 데이터 샘플링 및 캐싱
│   └── config/            # 설정 파일 (config.py)
├── pages/                 # Streamlit UI 페이지 (duplicate_detector.py 추가)
├── streamlit_app_v2.py    # 메인 Entry Point
└── requirements.txt       # 의존성 목록
```

---

## ⚙️ 실행 방법

1.  **의존성 설치**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Vector DB (Milvus) 실행**
    *   중복 탐지 기능을 사용하기 위해서는 Milvus 서버가 필요합니다. (`localhost:19530` 기본값)

3.  **애플리케이션 실행**
    ```bash
    streamlit run streamlit_app_v2.py
    ```

4.  **이미지 중복 탐지 실행 (UI)**
    *   사이드바에서 **`duplicate_detector`** 페이지를 선택합니다.
    *   탐지할 납품 배치를 선택합니다.
    *   실행 단계(Stage 1~3)를 선택한 후 **`🚀 중복 탐지 프로세스 시작`** 버튼을 누릅니다.
    *   분석된 임베딩은 자동으로 Milvus DB에 저장되며, 이후 검색 기능이나 API를 통해 중복 여부를 확인할 수 있습니다.