import os
import sys
from pathlib import Path
import Levenshtein
from tqdm import tqdm

# EasyOCR 라이브러리 (원본 사용)
import easyocr

def calculate_cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate 계산"""
    ref = reference.replace(" ", "")
    hyp = hypothesis.replace(" ", "")
    if len(ref) == 0:
        return 0.0 if len(hyp) == 0 else 1.0
    return Levenshtein.distance(ref, hyp) / len(ref)

def evaluate_baseline():
    raw_dir = Path("~/workspace/07.k_omnidoc_bench/data/ocr_training/raw").expanduser()
    val_file = raw_dir / "val.txt"
    
    if not val_file.exists():
        print(f"오류: 검증 데이터가 없습니다. {val_file}")
        sys.exit(1)
        
    print("🚀 EasyOCR 원본 모델 로딩 중... (korean_g2.pth)")
    reader = easyocr.Reader(['ko', 'en'], gpu=True)
    
    lines = val_file.read_text(encoding="utf-8").strip().splitlines()
    total_cer = 0.0
    valid_count = 0
    
    print(f"📊 총 {len(lines)}개의 검증 이미지 평가 시작...")
    
    # 처음 5개 샘플 상세 출력용
    sample_outputs = []
    
    for i, line in enumerate(tqdm(lines)):
        parts = line.split("\t", maxsplit=1)
        if len(parts) != 2: continue
        
        img_rel_path, gt_text = parts
        img_path = raw_dir / img_rel_path
        
        if not img_path.exists(): continue
        
        # 원본 EasyOCR 추론
        try:
            results = reader.readtext(str(img_path), detail=0)
            pred_text = " ".join(results)
        except Exception as e:
            pred_text = ""
            
        cer = calculate_cer(gt_text, pred_text)
        total_cer += cer
        valid_count += 1
        
        if i < 5:
            sample_outputs.append((gt_text, pred_text, cer))
            
    if valid_count > 0:
        avg_cer = total_cer / valid_count
        print(f"\n✅ 원본 모델 (korean_g2.pth) 평가 결과")
        print(f"   - 평가 건수: {valid_count}건")
        print(f"   - 평균 CER : {avg_cer:.4f} ({avg_cer * 100:.2f}%)")
        print("\n🔍 샘플 5개 결과:")
        for gt, pred, cer in sample_outputs:
            print(f"   [GT] {gt}")
            print(f"   [PR] {pred}")
            print(f"   [CER] {cer:.4f}\n")
    else:
        print("평가 가능한 데이터가 없습니다.")

if __name__ == "__main__":
    evaluate_baseline()
