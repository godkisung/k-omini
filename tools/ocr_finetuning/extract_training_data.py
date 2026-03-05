"""Phase 1: OCR 학습 데이터 추출 스크립트.

JSON 어노테이션에서 (이미지 크롭, 텍스트 라벨) 쌍을 추출합니다.
- poly 좌표를 perspective transform으로 정확히 크롭
- train/val 8:2 분리
- --append 옵션으로 기존 데이터에 누적 가능

사용법:
    conda activate omni
    python tools/ocr_finetuning/extract_training_data.py \
        --json_dir data/Alchera_delivery_P1_260227/json \
        --img_dir  data/Alchera_delivery_P1_260227/img \
        --output_dir data/ocr_training/raw

    # 다음 배치 추가 시:
    python tools/ocr_finetuning/extract_training_data.py \
        --json_dir data/Alchera_delivery_P2_XXXXXX/json \
        --img_dir  data/Alchera_delivery_P2_XXXXXX/img \
        --output_dir data/ocr_training/raw \
        --append
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
from PIL import Image

# ── 추출 대상 카테고리 ──────────────────────────────────────────────────────────
TEXT_CATEGORIES = {
    "text_block", "title", "list", "list_item",
    "header", "footer", "page_number", "figure_caption",
    "table_caption", "page_footnote",
}

# ── 이미지 품질 필터 기준 ────────────────────────────────────────────────────────
MIN_WIDTH = 10    # 최소 크롭 너비 (px)
MIN_HEIGHT = 8    # 최소 크롭 높이 (px)
MAX_ASPECT = 50.0 # 최대 가로/세로 비율 (너무 긴 것 제외)
TRAIN_RATIO = 0.8 # 학습 비율 (나머지는 val)


# ── 이미지 처리 함수 ────────────────────────────────────────────────────────────

def order_points(pts: np.ndarray) -> np.ndarray:
    """4개 점을 [좌상, 우상, 우하, 좌하] 순으로 정렬합니다."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # 좌상 (x+y 최소)
    rect[2] = pts[np.argmax(s)]   # 우하 (x+y 최대)
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # 우상 (y-x 최소)
    rect[3] = pts[np.argmax(diff)]  # 좌하 (y-x 최대)
    return rect


def perspective_crop(image: np.ndarray, poly: list[float]) -> np.ndarray | None:
    """Polygon 좌표를 사용해 정확한 perspective transform 크롭을 수행합니다.

    Args:
        image: BGR numpy 배열.
        poly: [x1, y1, x2, y2, ...] 형태의 polygon 좌표.

    Returns:
        크롭된 이미지 numpy 배열, 실패 시 None.
    """
    try:
        pts_raw = np.array(poly, dtype=np.float32).reshape(-1, 2)

        # 4개 미만이면 AABB fallback
        if len(pts_raw) < 4:
            xs, ys = pts_raw[:, 0], pts_raw[:, 1]
            x1, y1 = int(xs.min()), int(ys.min())
            x2, y2 = int(xs.max()), int(ys.max())
            if x2 <= x1 or y2 <= y1:
                return None
            return image[y1:y2, x1:x2].copy()

        # 4개 이상이면 convex hull → 4점으로 근사
        hull = cv2.convexHull(pts_raw.astype(np.int32))
        rect_approx = cv2.approxPolyDP(hull, epsilon=3, closed=True)

        if len(rect_approx) == 4:
            src_pts = order_points(rect_approx.reshape(4, 2))
        else:
            # 4점 근사 실패 시 bounding rect
            x, y, w, h = cv2.boundingRect(pts_raw.astype(np.int32))
            if w <= 0 or h <= 0:
                return None
            return image[y:y+h, x:x+w].copy()

        # 목적지 크기 계산
        (tl, tr, br, bl) = src_pts
        width = int(max(
            np.linalg.norm(br - bl),
            np.linalg.norm(tr - tl),
        ))
        height = int(max(
            np.linalg.norm(tr - br),
            np.linalg.norm(tl - bl),
        ))

        if width <= 0 or height <= 0:
            return None

        dst_pts = np.array([
            [0, 0], [width - 1, 0],
            [width - 1, height - 1], [0, height - 1],
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(image, M, (width, height))
        return warped

    except Exception:
        return None


def is_valid_crop(crop: np.ndarray) -> bool:
    """크롭 이미지의 품질 기준을 만족하는지 확인합니다."""
    if crop is None or crop.size == 0:
        return False
    h, w = crop.shape[:2]
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        return False
    aspect = w / h if h > 0 else float("inf")
    return aspect <= MAX_ASPECT


# ── 메인 추출 함수 ──────────────────────────────────────────────────────────────

def extract_pairs(
    json_dir: str,
    img_dir: str,
    output_dir: str,
    append: bool = False,
) -> tuple[int, int]:
    """JSON 어노테이션에서 (이미지 크롭, 텍스트) 쌍을 추출합니다.

    Args:
        json_dir: JSON 파일 디렉토리.
        img_dir: 이미지 파일 디렉토리.
        output_dir: 출력 루트 디렉토리. {output_dir}/images/, {output_dir}/labels.txt 생성.
        append: True면 기존 labels.txt에 추가. False면 초기화 후 새로 시작.

    Returns:
        (추출 성공 수, 스킵 수) 튜플.
    """
    output_path = Path(output_dir)
    img_output = output_path / "images"
    img_output.mkdir(parents=True, exist_ok=True)

    labels_file = output_path / "labels.txt"
    mode = "a" if append else "w"

    # 기존 이미지 수 (append 시 파일명 충돌 방지)
    existing_count = len(list(img_output.glob("*.jpg"))) if append else 0

    json_files = sorted(glob.glob(os.path.join(json_dir, "*.json")))
    if not json_files:
        json_files = sorted(glob.glob(os.path.join(json_dir, "**/*.json"), recursive=True))

    success_count = 0
    skip_count = 0

    with open(labels_file, mode, encoding="utf-8") as label_f:
        for json_path in json_files:
            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            # 이미지 로드
            img_rel_path = data.get("page_info", {}).get("image_path", "")
            img_path = os.path.join(img_dir, os.path.basename(img_rel_path))
            if not os.path.exists(img_path):
                # img_dir에서 동일 stem으로 시도
                stem = Path(json_path).stem
                candidates = list(Path(img_dir).glob(f"{stem}.*"))
                if candidates:
                    img_path = str(candidates[0])
                else:
                    skip_count += len(data.get("layout_dets", []))
                    continue

            try:
                image_bgr = cv2.imread(img_path)
                if image_bgr is None:
                    skip_count += len(data.get("layout_dets", []))
                    continue
            except Exception:
                continue

            for ann in data.get("layout_dets", []):
                cat = ann.get("category_type", "")
                if cat not in TEXT_CATEGORIES:
                    continue

                text = (ann.get("text", "") or "").strip()
                if not text:
                    skip_count += 1
                    continue

                poly = ann.get("poly", [])
                if not poly:
                    skip_count += 1
                    continue

                crop = perspective_crop(image_bgr, poly)
                if not is_valid_crop(crop):
                    skip_count += 1
                    continue

                # 저장
                idx = existing_count + success_count + 1
                crop_filename = f"{idx:07d}.jpg"
                crop_path = img_output / crop_filename

                # JPEG 저장 (품질 95)
                cv2.imwrite(str(crop_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

                # 라벨 저장: "images/0000001.jpg\t라벨텍스트"
                label_f.write(f"images/{crop_filename}\t{text}\n")
                success_count += 1

    return success_count, skip_count


def split_train_val(output_dir: str, train_ratio: float = TRAIN_RATIO, seed: int = 42) -> None:
    """labels.txt를 train.txt / val.txt로 분리합니다.

    Args:
        output_dir: extract_pairs()의 output_dir.
        train_ratio: 학습 비율.
        seed: 셔플 시드.
    """
    labels_file = Path(output_dir) / "labels.txt"
    if not labels_file.exists():
        print(f"❌ {labels_file}를 찾을 수 없습니다.")
        return

    lines = labels_file.read_text(encoding="utf-8").strip().splitlines()
    random.seed(seed)
    random.shuffle(lines)

    n_train = int(len(lines) * train_ratio)
    train_lines = lines[:n_train]
    val_lines = lines[n_train:]

    (Path(output_dir) / "train.txt").write_text("\n".join(train_lines), encoding="utf-8")
    (Path(output_dir) / "val.txt").write_text("\n".join(val_lines), encoding="utf-8")

    print(f"  → train: {len(train_lines)}쌍, val: {len(val_lines)}쌍")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EasyOCR fine-tuning용 학습 데이터 추출"
    )
    parser.add_argument(
        "--json_dir", required=True,
        help="JSON 파일 디렉토리 경로",
    )
    parser.add_argument(
        "--img_dir", required=True,
        help="이미지 파일 디렉토리 경로",
    )
    parser.add_argument(
        "--output_dir", default="data/ocr_training/raw",
        help="출력 디렉토리 (기본값: data/ocr_training/raw)",
    )
    parser.add_argument(
        "--append", action="store_true",
        help="기존 데이터에 추가 (다음 배치 누적 시 사용)",
    )
    parser.add_argument(
        "--train_ratio", type=float, default=TRAIN_RATIO,
        help=f"학습 비율 (기본값: {TRAIN_RATIO})",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="train/val 분할 시드 (기본값: 42)",
    )
    args = parser.parse_args()

    json_dir = os.path.abspath(args.json_dir)
    img_dir = os.path.abspath(args.img_dir)
    output_dir = os.path.abspath(args.output_dir)

    print("\n" + "=" * 60)
    print("Phase 1: OCR 학습 데이터 추출")
    print("=" * 60)
    print(f"  JSON 디렉토리 : {json_dir}")
    print(f"  이미지 디렉토리: {img_dir}")
    print(f"  출력 디렉토리 : {output_dir}")
    print(f"  누적 모드      : {'YES (append)' if args.append else 'NO (초기화)'}")
    print("=" * 60 + "\n")

    success, skip = extract_pairs(
        json_dir=json_dir,
        img_dir=img_dir,
        output_dir=output_dir,
        append=args.append,
    )

    print(f"✅ 추출 완료: {success}쌍 성공, {skip}개 스킵")

    print("\ntrain / val 분할 중...")
    split_train_val(output_dir, train_ratio=args.train_ratio, seed=args.seed)
    print("✅ 분할 완료")
    print(f"\n📁 출력 구조:")
    print(f"  {output_dir}/")
    print(f"  ├── images/       ← {success}개 크롭 이미지")
    print(f"  ├── labels.txt    ← 전체 라벨")
    print(f"  ├── train.txt     ← 학습 라벨 (~{int(success * args.train_ratio)}개)")
    print(f"  └── val.txt       ← 검증 라벨 (~{success - int(success * args.train_ratio)}개)")
    print("\n다음 단계: python tools/ocr_finetuning/build_lmdb.py")


if __name__ == "__main__":
    main()
