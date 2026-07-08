#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# EasyOCR Recognition Model Fine-tuning (Transfer Learning)
#
# 전략: character set 확장 + Transfer Learning
#   - VGG_FeatureExtractor + BiLSTM×2 + CTC: korean_g2.pth 실제 아키텍처
#     (Transformation 없음, ResNet 아님 — run_finetune.py 상단 docstring 참고)
#   - 기존 korean_g2.pth 가중치를 saved_model로 로드해 이어서 학습(FT)
#
# 사전 조건:
#   conda activate omni (또는 uv 가상환경)
#   EasyOCR 첫 실행으로 ~/.EasyOCR/model/korean_g2.pth 다운로드되어 있어야 함
#
# 주의: easyocr_trainer/trainer/train.py는 자체 CLI가 없는 함수 정의 파일이라
#       `python train.py --flag value ...` 형태로는 아무 인자도 파싱되지 않고
#       조용히 아무 학습도 하지 않은 채 종료된다. 그래서 opt를 파이썬 객체로
#       직접 구성해 train(opt)를 호출하는 run_finetune.py를 통해 실행한다.
# ─────────────────────────────────────────────────────────────────
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TRAINER_DIR="${PROJECT_ROOT}/easyocr_trainer/trainer"

TRAIN_DATA="${PROJECT_ROOT}/data/ocr_training/lmdb/train"
VALID_DATA="${PROJECT_ROOT}/data/ocr_training/lmdb/val"
PRETRAINED_MODEL="$HOME/.EasyOCR/model/korean_g2.pth"

echo "============================================================"
echo "Phase 3: EasyOCR Fine-tuning (Transfer Learning)"
echo "============================================================"

echo "🖥️  GPU 상태:"
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "  nvidia-smi 없음"
echo ""

if [ ! -f "$PRETRAINED_MODEL" ]; then
    echo "📥 korean_g2.pth 다운로드 중 (EasyOCR 초기화)..."
    python -c "
import easyocr, torch
reader = easyocr.Reader(['ko', 'en'], gpu=torch.cuda.is_available(), verbose=False)
print('  ✅ 다운로드 완료')
"
fi
echo "✅ 사전학습 모델: ${PRETRAINED_MODEL}"

if [ ! -d "$TRAIN_DATA" ] || [ ! -d "$VALID_DATA" ]; then
    echo "❌ LMDB 데이터 없음 → build_lmdb.py를 먼저 실행하세요."
    exit 1
fi
echo "📂 Train LMDB: ${TRAIN_DATA}"
echo "📂 Val LMDB:   ${VALID_DATA}"
echo ""

cp "${SCRIPT_DIR}/run_finetune.py" "${TRAINER_DIR}/run_finetune.py"

echo "🚀 Fine-tuning 시작..."
cd "${TRAINER_DIR}"
KOMNI_PROJECT_ROOT="${PROJECT_ROOT}" CUDA_VISIBLE_DEVICES=0,1 python run_finetune.py 2>&1 | tee "${PROJECT_ROOT}/models/finetuned_train.log"

echo ""
echo "✅ Fine-tuning 완료!"
echo "   최고 정확도 모델: ${TRAINER_DIR}/saved_models/ko_finetuned_v1/best_accuracy.pth"
echo "   학습 로그: ${PROJECT_ROOT}/models/finetuned_train.log"
echo ""
echo "다음 단계: src/core/ocr_engine.py에서 fine-tuned 모델을 로드하세요."
echo "   README.md의 Phase 4 섹션 참고"
