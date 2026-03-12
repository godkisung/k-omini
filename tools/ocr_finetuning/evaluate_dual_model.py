import os
import sys
import torch
import torch.utils.data
from pathlib import Path
import Levenshtein
from tqdm import tqdm
from PIL import Image
import numpy as np
import types

# EasyOCR 프로젝트 내부 모듈 로드 (Inference용)
sys.path.append(os.path.abspath("easyocr_trainer/trainer"))
from model import Model
from utils import CTCLabelConverter

# ── 설정 ────────────────────────────────────────────────────────────────────────

RAW_DIR = Path("~/workspace/07.k_omnidoc_bench/data/ocr_training/raw").expanduser()
VAL_FILE = RAW_DIR / "val.txt"
BEST_MODEL_PATH = "easyocr_trainer/trainer/saved_models/ko_finetuned_v1/best_accuracy.pth"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── 헬퍼 함수 ───────────────────────────────────────────────────────────────────

def calculate_cer(reference: str, hypothesis: str) -> float:
    ref = reference.replace(" ", "")
    hyp = hypothesis.replace(" ", "")
    if not ref: return 0.0 if not hyp else 1.0
    return Levenshtein.distance(ref, hyp) / len(ref)

# ── 메인 평가 로직 ──────────────────────────────────────────────────────────────

def run_dual_evaluation():
    if not VAL_FILE.exists():
        print(f"❌ 검증 데이터가 없습니다: {VAL_FILE}")
        return

    import easyocr
    # 1. Base Model 로드
    print("🚀 EasyOCR 기본 모델(korean_g2) 로딩 중...")
    reader_base = easyocr.Reader(["ko", "en"], gpu=True)
    character_list = reader_base.character
    
    # 2. Fine-tuned Model 로드
    print(f"🚀 파인튜닝 모델 로딩 중: {BEST_MODEL_PATH}")
    
    # [핵심] 가중치를 먼저 열어서 클래스 수를 강제로 맞춤
    state_dict = torch.load(BEST_MODEL_PATH, map_location=device)
    
    # 클래스 수 확인 (1009인지 확인)
    actual_num_class = 1009
    for key in state_dict.keys():
        if "Prediction.bias" in key:
            actual_num_class = state_dict[key].size(0)
            break
    print(f"✅ 가중치 파일에서 감지된 클래스 수: {actual_num_class}")

    opt_ft = types.SimpleNamespace(
        Transformation="None",
        FeatureExtraction="VGG",
        SequenceModeling="BiLSTM",
        Prediction="CTC",
        num_fiducial=20,
        input_channel=1,
        output_channel=256,
        hidden_size=256,
        imgH=32,
        imgW=600,
        num_class=actual_num_class, # 에러 방지를 위해 1009 강제 적용
        batch_max_length=150,
        rgb=False,
        sensitive=True,
        character="".join(character_list)
    )
    
    model_ft = Model(opt_ft)
    model_ft = torch.nn.DataParallel(model_ft).to(device)
    model_ft.load_state_dict(state_dict)
    model_ft.eval()
    
    # Converter 설정
    converter = CTCLabelConverter("".join(character_list))

    # 데이터 로드
    lines = VAL_FILE.read_text(encoding="utf-8").strip().splitlines()
    results = {"base": {"cer": 0.0, "acc": 0}, "ft": {"cer": 0.0, "acc": 0}}
    total_count = 0

    print(f"📊 {len(lines)}개 샘플에 대해 비교 평가 시작...")

    for line in tqdm(lines):
        parts = line.split("\t", maxsplit=1)
        if len(parts) != 2: continue
        img_rel_path, gt_text = parts
        img_path = RAW_DIR / img_rel_path
        if not img_path.exists(): continue

        # 1. Base Model 추론
        res_base = reader_base.readtext(str(img_path), detail=0)
        pred_base = "".join(res_base).replace(" ", "")
        
        # 2. Fine-tuned Model 추론
        img = Image.open(img_path).convert("L")
        w, h = img.size
        ratio = w / float(h)
        resized_w = min(opt_ft.imgW, int(opt_ft.imgH * ratio))
        img_tensor = np.array(img.resize((resized_w, opt_ft.imgH), Image.BICUBIC))
        img_tensor = (img_tensor / 255.0 - 0.5) / 0.5
        
        canvas = np.ones((opt_ft.imgH, opt_ft.imgW), dtype=np.float32)
        canvas[:, :resized_w] = img_tensor
        input_tensor = torch.from_numpy(canvas).unsqueeze(0).unsqueeze(0).to(device)
        
        with torch.no_grad():
            preds = model_ft(input_tensor, None)
            
            # [수정] decode_greedy는 1차원으로 평탄화된 텐서를 기대함
            batch_size = preds.size(0)
            preds_size = torch.IntTensor([preds.size(1)] * batch_size).to(device)
            _, preds_index = preds.max(2)
            
            # 1차원으로 평탄화 (중요: 트레이너의 utils.py 로직 준수)
            preds_index_flattened = preds_index.view(-1)
            
            # 디코딩 실행
            pred_ft_list = converter.decode_greedy(preds_index_flattened, preds_size)
            pred_ft = pred_ft_list[0] if pred_ft_list else ""
            pred_ft = pred_ft.replace(" ", "")

        # CER 계산
        gt_clean = gt_text.replace(" ", "")
        cer_base = calculate_cer(gt_clean, pred_base)
        cer_ft = calculate_cer(gt_clean, pred_ft)

        results["base"]["cer"] += cer_base
        results["ft"]["cer"] += cer_ft
        if pred_base == gt_clean: results["base"]["acc"] += 1
        if pred_ft == gt_clean: results["ft"]["acc"] += 1
        total_count += 1

    # 결과 출력
    print("\n" + "="*50)
    print(f"🏆 모델 성능 비교 결과 (N={total_count})")
    print("="*50)
    print(f"1. 기본 모델 (korean_g2.pth)")
    print(f"   - Accuracy: {results['base']['acc']/(total_count if total_count > 0 else 1)*100:.2f}%")
    print(f"   - 평균 CER: {results['base']['cer']/(total_count if total_count > 0 else 1)*100:.2f}%")
    print("-" * 30)
    print(f"2. 파인튜닝 모델 (ko_finetuned_v1)")
    print(f"   - Accuracy: {results['ft']['acc']/(total_count if total_count > 0 else 1)*100:.2f}%")
    print(f"   - 평균 CER: {results['ft']['cer']/(total_count if total_count > 0 else 1)*100:.2f}%")
    print("="*50)

if __name__ == "__main__":
    run_dual_evaluation()
