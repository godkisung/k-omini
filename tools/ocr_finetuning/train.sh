#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# EasyOCR Recognition Model Fine-tuning (Transfer Learning)
#
# 전략: character set 확장 + Transfer Learning
#   - CNN(ResNet) + BiLSTM: 기존 korean_g2.pth 가중치 로드
#   - CTC Prediction head: 재초기화 (새 character set 크기에 맞게)
#   - freeze_FeatureFxtraction: CNN frozen → BiLSTM + CTC만 학습
#
# 사전 조건:
#   conda activate omni
#   EasyOCR 첫 실행으로 ~/.EasyOCR/model/korean_g2.pth 다운로드되어 있어야 함
# ─────────────────────────────────────────────────────────────────
set -eu

# ── 경로 설정 ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TRAINER_DIR="${PROJECT_ROOT}/easyocr_trainer/trainer"
CHARSET_FILE="${SCRIPT_DIR}/charset.txt"

TRAIN_DATA="${PROJECT_ROOT}/data/ocr_training/lmdb/train"
VALID_DATA="${PROJECT_ROOT}/data/ocr_training/lmdb/val"

# EasyOCR 사전학습 모델 경로 (첫 번째 실행 시 자동 다운로드됨)
PRETRAINED_MODEL="$HOME/.EasyOCR/model/korean_g2.pth"

EXPERIMENT_NAME="ko_finetuned_v1"
BATCH_SIZE=128         # 64 per GPU × 2 (메모리 부족 시 64로 낮추기)
NUM_WORKERS=8
NUM_ITER=50000         # 약 4,400샘플 × 11 epoch 분량
VALID_INTERVAL=1000
LR=1.0                 # Adadelta 기본값

echo "============================================================"
echo "Phase 3: EasyOCR Fine-tuning (Transfer Learning)"
echo "============================================================"

# ── GPU 상태 확인 ─────────────────────────────────────────────────
echo "🖥️  GPU 상태:"
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  nvidia-smi 없음"
echo ""

# ── charset.txt 확인 ─────────────────────────────────────────────
if [ ! -f "$CHARSET_FILE" ]; then
    echo "❌ charset.txt 없음 → check_charset.py를 먼저 실행하세요."
    exit 1
fi
CHAR_COUNT=$(wc -c < "$CHARSET_FILE")
echo "📝 character set: ${CHAR_COUNT}자 (${CHARSET_FILE})"

# ── 사전학습 모델 확인 ────────────────────────────────────────────
if [ ! -f "$PRETRAINED_MODEL" ]; then
    echo "📥 korean_g2.pth 다운로드 중 (EasyOCR 초기화)..."
    python -c "
import easyocr, torch
reader = easyocr.Reader(['ko', 'en'], gpu=torch.cuda.is_available(), verbose=False)
print('  ✅ 다운로드 완료')
"
fi
echo "✅ 사전학습 모델: ${PRETRAINED_MODEL}"

# ── LMDB 데이터 확인 ─────────────────────────────────────────────
if [ ! -d "$TRAIN_DATA" ] || [ ! -d "$VALID_DATA" ]; then
    echo "❌ LMDB 데이터 없음 → build_lmdb.py를 먼저 실행하세요."
    exit 1
fi
echo "📂 Train LMDB: ${TRAIN_DATA}"
echo "📂 Val LMDB:   ${VALID_DATA}"
echo ""

# ── saved_models 폴더 생성 ────────────────────────────────────────
# train.py가 ./saved_models/ 에 저장하므로 trainer/ 폴더에서 실행해야 함
mkdir -p "${TRAINER_DIR}/saved_models/${EXPERIMENT_NAME}"

# ── Fine-tuning 실행 ──────────────────────────────────────────────
echo "🚀 Fine-tuning 시작..."
echo "   실험명: ${EXPERIMENT_NAME}"
echo "   배치크기: ${BATCH_SIZE} (GPU 0,1 각 ${BATCH_SIZE})"
echo "   iterations: ${NUM_ITER}"
echo ""

cd "${TRAINER_DIR}"

CUDA_VISIBLE_DEVICES=0,1 python train.py \
    --train_data          "${TRAIN_DATA}"       \
    --valid_data          "${VALID_DATA}"       \
    --saved_model         "${PRETRAINED_MODEL}" \
    --experiment_name     "${EXPERIMENT_NAME}"  \
    --character           "$(cat "${CHARSET_FILE}")" \
    --batch_size          "${BATCH_SIZE}"       \
    --workers             "${NUM_WORKERS}"      \
    --num_iter            "${NUM_ITER}"         \
    --valInterval         "${VALID_INTERVAL}"   \
    --lr                  "${LR}"              \
    --Transformation      TPS                  \
    --FeatureExtraction   ResNet               \
    --SequenceModeling    BiLSTM              \
    --Prediction          CTC                 \
    --FT                                       \
    --new_prediction                           \
    --freeze_FeatureFxtraction                 \
    --data_filtering_off                       \
    --sensitive                                \
    --amp                                      2>&1 | tee "${PROJECT_ROOT}/models/finetuned_train.log"

echo ""
echo "✅ Fine-tuning 완료!"
echo "   최고 정확도 모델: ${TRAINER_DIR}/saved_models/${EXPERIMENT_NAME}/best_accuracy.pth"
echo "   학습 로그: ${PROJECT_ROOT}/models/finetuned_train.log"
echo ""
echo "다음 단계: src/core/ocr_engine.py에서 fine-tuned 모델을 로드하세요."
echo "   README.md의 Phase 4 섹션 참고"
