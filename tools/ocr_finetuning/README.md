# EasyOCR Fine-tuning 가이드

K-Omnidoc 어노테이션 데이터로 EasyOCR 한글 인식 모델을 fine-tuning합니다.

## 사전 조건

```bash
conda activate omni

# EasyOCR trainer 클론 (프로젝트 루트에서)
git clone -b trainer https://github.com/JaidedAI/EasyOCR easyocr_trainer

# LMDB 라이브러리 설치 (아직 없다면)
pip install lmdb
```

---

## 실행 순서

### Phase 0 — 문자셋 분석 (필수 선행)

```bash
python tools/ocr_finetuning/check_charset.py \
    --json_dir data/Alchera_delivery_P1_260227/json
```

- `charset.txt` 자동 생성
- EasyOCR charset에 없는 문자 보고 → **전략 결정**

### Phase 1 — 학습 데이터 추출

```bash
python tools/ocr_finetuning/extract_training_data.py \
    --json_dir data/Alchera_delivery_P1_260227/json \
    --img_dir  data/Alchera_delivery_P1_260227/img \
    --output_dir data/ocr_training/raw
```

출력:
```
data/ocr_training/raw/
├── images/       ← 크롭 이미지 (~7,000개)
├── labels.txt
├── train.txt
└── val.txt
```

### Phase 2 — LMDB 변환

```bash
python tools/ocr_finetuning/build_lmdb.py \
    --data_dir   data/ocr_training/raw \
    --output_dir data/ocr_training/lmdb
```

### Phase 3 — Fine-tuning 실행

```bash
bash tools/ocr_finetuning/train.sh
```

학습 로그는 `models/finetuned/ko_finetuned_v1/` 에 저장됩니다.

### Phase 4 — 모델 적용

`src/core/ocr_engine.py`의 `get_ocr_engine()`을 수정합니다:

```python
FINETUNED_MODEL = "models/finetuned/ko_finetuned_v1/best_accuracy.pth"

reader = easyocr.Reader(
    ['ko', 'en'],
    gpu=use_gpu,
    model_storage_directory='models/finetuned/',
    user_network_directory='easyocr_trainer/easyocr/model',
    recog_network='ko_finetuned_v1',
)
```

---

## 다음 납품 배치 누적 시

```bash
# 기존 데이터에 새 배치 추가 (--append)
python tools/ocr_finetuning/extract_training_data.py \
    --json_dir data/Alchera_delivery_P2_XXXXXX/json \
    --img_dir  data/Alchera_delivery_P2_XXXXXX/img \
    --output_dir data/ocr_training/raw \
    --append

# LMDB 재변환 (전체)
python tools/ocr_finetuning/build_lmdb.py \
    --data_dir   data/ocr_training/raw \
    --output_dir data/ocr_training/lmdb

# 이전 fine-tuned 모델에서 이어서 학습
# train.sh의 PRETRAINED_MODEL을 best_accuracy.pth로 변경 후 실행
bash tools/ocr_finetuning/train.sh
```

---

## 성능 측정 (CER 비교)

| 모델 | val CER | ⦁ 인식률 |
|------|---------|---------|
| korean_g2.pth (기존) | TBD | TBD |
| ko_finetuned_v1 (fine-tuned) | TBD | TBD |

> CER(Character Error Rate) = 편집거리 / 정답 길이. 낮을수록 좋습니다.

---

## 주의사항

- `charset.txt`에 없는 문자는 인식 불가 — Phase 0 결과 확인 필수
- 학습 중 GPU 메모리 부족 시 `BATCH_SIZE`를 64로 낮추세요 (train.sh)
- 학습 완료 후 반드시 val CER로 기존 모델과 비교 후 교체하세요
