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

---

## 알려진 이슈 / 현재 상태 (Phase 3 미완료)

이 파인튜닝 파이프라인은 Phase 0~2(문자셋 분석, 학습 데이터 추출, LMDB 변환)까지는
동작을 확인했지만, Phase 3(실제 학습)에서 두 가지 문제로 완료하지 못하고 중단했습니다.
재개할 사람을 위해 원인과 현재 수정 상태를 남깁니다.

1. **`train.py`에 CLI 진입점이 없음.** `easyocr_trainer/trainer/train.py`(JaidedAI
   EasyOCR `trainer` 브랜치)는 `train(opt, ...)` 함수만 정의돼 있고 `argparse`나
   `if __name__ == "__main__"`이 없습니다. 초기 버전의 `train.sh`처럼
   `python train.py --train_data ... --Transformation TPS ...` 형태로 실행하면
   인자가 전혀 파싱되지 않고 모듈만 임포트한 뒤 즉시 종료됩니다 — 에러 없이
   "성공"하지만 실제로는 아무 학습도 하지 않습니다.
2. **아키텍처 설정이 `korean_g2.pth`와 맞지 않았음.** 초기 `train.sh`는
   `--Transformation TPS --FeatureExtraction ResNet`을 사용했지만, EasyOCR
   소스(`easyocr/recognition.py`의 `generation2` 분기 → `easyocr/model/vgg_model.py`)
   기준 `korean_g2.pth`의 실제 구조는 **Transformation 없음 + VGG_FeatureExtractor
   + BiLSTM×2 + CTC** (output_channel=256, hidden_size=256)입니다. 다른 구조에
   이 가중치를 `--saved_model`로 로드하면 레이어 shape이 맞지 않아 전이학습이
   제대로 되지 않습니다.

`run_finetune.py`는 위 두 문제를 수정해 `opt`를 파이썬 객체로 직접 구성하고
`train(opt)`를 호출하며, `korean_g2.pth`의 실제 아키텍처(VGG/None)와 실제
`num_class`(체크포인트의 `Prediction` 레이어 shape에서 동적으로 계산, 하드코딩 아님)를
사용하도록 고쳤습니다. `train.sh`는 이 스크립트를 `easyocr_trainer/trainer/`로 복사한
뒤 실행하도록 갱신했습니다.

**다만 이 상태로는 아직 문자셋 확장(charset expansion)은 지원하지 않습니다** —
`new_prediction=False`로 두고 `num_class`를 체크포인트 그대로(1009개, EasyOCR 기본
charset)에 맞췄기 때문입니다. `check_charset.py`가 생성하는 확장 `charset.txt`(누락
문자 추가분)를 실제로 반영하려면 `new_prediction=True` + `num_class`를 확장된
charset 크기로 바꾸는 추가 작업이 필요합니다. 또한 `check_charset.py`가 내부적으로
재현한 EasyOCR 기본 한글 charset은 유니코드 한글 완성형 전체(11,172자)를 가정하고
있어, 실제 `korean_g2.pth`의 charset(1,008자, 실사용 빈도 기준으로 선별된 부분집합)보다
훨씬 넓습니다 — 그래서 "누락 문자" 판정이 실제보다 적게 나올 수 있습니다. 이 부분은
아직 고치지 못한 채로 남겨둡니다.

이 파이프라인으로 실제 학습을 끝까지 돌려서 검증하지는 못했습니다(로컬에 LMDB 데이터가
남아있지 않아 재현 불가) — 위 두 버그를 고친 상태이지, "학습이 잘 된다"는 것까지
확인된 상태는 아닙니다. 이어서 작업할 때는 Phase 1~2로 LMDB를 다시 만든 뒤
`run_finetune.py`가 실제로 loss가 감소하는지부터 확인하세요.
