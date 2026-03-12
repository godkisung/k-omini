"""Phase 1: OCR 학습 데이터 추출 스크립트 (디버깅 모드)

실행 명령어:
    python tools/ocr_finetuning/extract_training_data.py \
        --json_dir data/Alchera_delivery_P1_260227/json \
        --img_dir  data/Alchera_delivery_P1_260227/img \
        --output_dir data/ocr_training/raw
"""

import argparse
import glob
import json
import math
import os
import random
import shutil
from pathlib import Path

import cv2
import numpy as np

# ── 추출 대상 카테고리 (Single-line 성격이 강한 것 위주) ─────────────────────────
TEXT_CATEGORIES = {
    "title", "header", "footer", "page_number", "figure_caption",
    "table_caption", "page_footnote", "list_item"
}

# ── 이미지 품질 필터 기준 ────────────────────────────────────────────────────────
MIN_WIDTH = 5
MIN_HEIGHT = 5
MIN_ASPECT = 2.5   # [완화] 4.0 -> 2.5 (한 줄 텍스트가 조금 짧아도 허용)
MAX_TEXT_LEN = 200 # 최대 텍스트 길이
TRAIN_RATIO = 0.8 # 학습 비율 (나머지는 val)


# ── 이미지 처리 함수 ────────────────────────────────────────────────────────────

def order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def perspective_crop(image: np.ndarray, poly: list[float]) -> np.ndarray | None:
    try:
        pts_raw = np.array(poly, dtype=np.float32).reshape(-1, 2)
        if len(pts_raw) < 4:
            xs, ys = pts_raw[:, 0], pts_raw[:, 1]
            x1, y1 = int(xs.min()), int(ys.min())
            x2, y2 = int(xs.max()), int(ys.max())
            if x2 <= x1 or y2 <= y1: return None
            return image[y1:y2, x1:x2].copy()

        hull = cv2.convexHull(pts_raw.astype(np.int32))
        rect_approx = cv2.approxPolyDP(hull, epsilon=3, closed=True)

        if len(rect_approx) == 4:
            src_pts = order_points(rect_approx.reshape(4, 2))
        else:
            x, y, w, h = cv2.boundingRect(pts_raw.astype(np.int32))
            if w <= 0 or h <= 0: return None
            return image[y:y+h, x:x+w].copy()

        (tl, tr, br, bl) = src_pts
        width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
        height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))

        if width <= 0 or height <= 0: return None
        dst_pts = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(image, M, (width, height))
        return warped
    except Exception:
        return None


def is_valid_crop(crop, text, cat):
    if crop is None or crop.size == 0:
        return False, "CROP_EMPTY"
    h, w = crop.shape[:2]
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        return False, f"SIZE_TOO_SMALL({w}x{h})"
        
    aspect = w / h if h > 0 else 0
    if aspect < MIN_ASPECT:
        return False, f"ASPECT_TOO_SMALL({aspect:.2f})"
        
    if "\n" in text or "\r" in text:
        return False, "MULTILINE_TEXT"
    
    if len(text) > MAX_TEXT_LEN:
        return False, f"TEXT_TOO_LONG({len(text)})"
        
    return True, "OK"


# ── 메인 추출 함수 ──────────────────────────────────────────────────────────────

def extract_pairs(json_dir, img_dir, output_dir, append=False):
    output_path = Path(output_dir)
    img_output = output_path / "images"
    img_output.mkdir(parents=True, exist_ok=True)

    labels_file = output_path / "labels.txt"
    mode = "a" if append else "w"

    existing_count = len(list(img_output.glob("*.jpg"))) if append else 0
    json_files = sorted(glob.glob(os.path.join(json_dir, "**/*.json"), recursive=True))

    success_count = 0
    skip_count = 0
    
    # 디버깅 통계
    skip_stats = {}

    with open(labels_file, mode, encoding="utf-8") as label_f:
        for i, json_path in enumerate(json_files):
            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
            except: continue

            img_rel_path = data.get("page_info", {}).get("image_path", "")
            img_path = os.path.join(img_dir, os.path.basename(img_rel_path))
            
            if not os.path.exists(img_path):
                skip_count += len(data.get("layout_dets", []))
                skip_stats["IMG_NOT_FOUND"] = skip_stats.get("IMG_NOT_FOUND", 0) + 1
                continue

            image_bgr = cv2.imread(img_path)
            if image_bgr is None:
                skip_count += len(data.get("layout_dets", []))
                skip_stats["IMG_LOAD_FAILED"] = skip_stats.get("IMG_LOAD_FAILED", 0) + 1
                continue

            for ann in data.get("layout_dets", []):
                cat = ann.get("category_type", "")
                if cat not in TEXT_CATEGORIES:
                    skip_stats[f"CAT_EXCLUDED({cat})"] = skip_stats.get(f"CAT_EXCLUDED({cat})", 0) + 1
                    continue

                text = (ann.get("text", "") or "").replace("\n", " ").replace("\r", " ").strip()
                if not text:
                    skip_stats["TEXT_EMPTY"] = skip_stats.get("TEXT_EMPTY", 0) + 1
                    skip_count += 1
                    continue

                poly = ann.get("poly", [])
                crop = perspective_crop(image_bgr, poly)
                
                valid, reason = is_valid_crop(crop, text, cat)
                if not valid:
                    skip_stats[reason] = skip_stats.get(reason, 0) + 1
                    skip_count += 1
                    continue

                idx = existing_count + success_count + 1
                crop_filename = f"{idx:07d}.jpg"
                cv2.imwrite(str(img_output / crop_filename), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
                label_f.write(f"images/{crop_filename}\t{text}\n")
                success_count += 1
            
            # 중간 보고 (10개 파일마다)
            if (i+1) % 50 == 0:
                print(f"  ... {i+1}개 파일 처리 중... (성공: {success_count})")

    print("\n[Skip 상세 통계]")
    for k, v in sorted(skip_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {k}: {v}")

    return success_count, skip_count


def split_train_val(output_dir, train_ratio=TRAIN_RATIO, seed=42):
    labels_file = Path(output_dir) / "labels.txt"
    if not labels_file.exists(): return
    lines = labels_file.read_text(encoding="utf-8").strip().splitlines()
    if not lines: return
    random.seed(seed); random.shuffle(lines)
    n_train = int(len(lines) * train_ratio)
    (Path(output_dir) / "train.txt").write_text("\n".join(lines[:n_train]), encoding="utf-8")
    (Path(output_dir) / "val.txt").write_text("\n".join(lines[n_train:]), encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_dir", required=True)
    parser.add_argument("--img_dir", required=True)
    parser.add_argument("--output_dir", default="data/ocr_training/raw")
    args = parser.parse_args()
    
    success, skip = extract_pairs(args.json_dir, args.img_dir, args.output_dir)
    print(f"\n✅ 최종 결과: {success}쌍 성공, {skip}개 스킵")
    split_train_val(args.output_dir)
