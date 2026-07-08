"""EasyOCR Fine-tuning 런처.

이 스크립트를 `easyocr_trainer/trainer/`로 복사한 뒤 그 안에서 실행합니다:

    cp tools/ocr_finetuning/run_finetune.py easyocr_trainer/trainer/
    cd easyocr_trainer/trainer && python run_finetune.py

## 왜 `python train.py --train_data ...` (CLI 플래그) 방식이 아닌가

`easyocr_trainer/trainer/train.py`(JaidedAI EasyOCR `trainer` 브랜치)는
`train(opt, ...)` 함수만 정의되어 있고 자체 `argparse`/`__main__` 진입점이 없습니다.
`python train.py --train_data ... --Transformation TPS ...` 형태로 실행하면
아무 인자도 파싱되지 않은 채 모듈 임포트만 하고 즉시 종료되어, 에러 없이
"성공"한 것처럼 보이지만 실제로는 학습이 전혀 일어나지 않습니다.
따라서 `opt`를 파이썬 객체로 직접 만들어 `train(opt)`를 호출해야 합니다.

## 왜 Transformation=None, FeatureExtraction=VGG 인가

기본 한국어 모델 `korean_g2.pth`는 EasyOCR 소스(`easyocr/recognition.py`의
`generation2` 분기, `easyocr/model/vgg_model.py`)상 TPS/ResNet이 아니라
**VGG_FeatureExtractor + BiLSTM×2 + CTC**(Transformation 없음, output_channel=256,
hidden_size=256) 구조로 고정되어 있습니다. 다른 구조로 만든 모델에
`korean_g2.pth`를 `--saved_model`로 로드하면 레이어 shape이 맞지 않아
전이학습 가중치가 사실상 무시되거나 로드 자체가 실패합니다.
"""

import os
import torch
import easyocr
import types

DATA_ROOT = os.path.expanduser("~/workspace/07.k_omnidoc_bench/data/ocr_training/lmdb")
PRETRAINED_MODEL = os.path.expanduser("~/.EasyOCR/model/korean_g2.pth")
EXPERIMENT_NAME = "ko_finetuned_v1"

save_dir = f"saved_models/{EXPERIMENT_NAME}"
os.makedirs(save_dir, exist_ok=True)

# 체크포인트의 Prediction(CTC 출력) 레이어 shape에서 실제 num_class를 읽어온다.
# (하드코딩하면 EasyOCR이 charset을 바꿀 때마다 조용히 어긋난다.)
checkpoint = torch.load(PRETRAINED_MODEL, map_location="cpu", weights_only=False)
actual_num_class = checkpoint["module.Prediction.weight"].shape[0]
print(f"✅ 사전학습 가중치 감지: num_class={actual_num_class}")

# CTCLabelConverter는 charset 앞에 '[blank]' 토큰 1개를 추가하므로
# num_class == len(character) + 1 이어야 한다. 길이가 다르면만 보정한다.
reader = easyocr.Reader(["ko", "en"], gpu=False)
character = reader.character
expected_len = actual_num_class - 1
if len(character) != expected_len:
    diff = expected_len - len(character)
    print(f"⚠️ charset 길이 불일치 감지: {len(character)}자 → {expected_len}자로 보정 ({diff:+d})")
    character = character + " " * diff if diff > 0 else character[:expected_len]
print(f"📝 character set: {len(character)}자 (num_class={actual_num_class}와 정합)")

opt = types.SimpleNamespace(
    train_data=f"{DATA_ROOT}/train",
    valid_data=f"{DATA_ROOT}/val",
    select_data="/",
    batch_ratio="1",
    total_data_usage_ratio=1.0,
    batch_max_length=150,

    workers=4,
    batch_size=64,
    num_iter=5000,
    valInterval=100,
    saved_model=PRETRAINED_MODEL,
    FT=True,
    optim="adadelta",
    lr=0.0001,
    beta1=0.9,
    rho=0.95,
    eps=1e-8,
    grad_clip=5,
    amp=True,

    sensitive=True,
    PAD=True,
    data_filtering_off=True,
    contrast_adjust=0.0,

    # korean_g2.pth의 실제 아키텍처 (TPS/ResNet 아님 — 위 docstring 참고)
    Transformation="None",
    FeatureExtraction="VGG",
    SequenceModeling="BiLSTM",
    Prediction="CTC",
    num_fiducial=20,
    input_channel=1,
    output_channel=256,
    hidden_size=256,
    num_class=actual_num_class,

    new_prediction=False,
    freeze_FeatureFxtraction=False,
    freeze_SequenceModeling=False,

    experiment_name=EXPERIMENT_NAME,
    character=character,
    decode="greedy",
    rgb=False,
    imgH=32,
    imgW=800,
    manualSeed=1111,
    show_number=2,
)

from train import train
print(f"🚀 Fine-tuning 시작 (num_class={opt.num_class})...")
train(opt, show_number=2, amp=opt.amp)
