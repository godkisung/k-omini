"""Phase 2: LMDB 변환 스크립트.

extract_training_data.py가 생성한 (이미지 경로, 라벨) 텍스트 파일을
EasyOCR trainer가 요구하는 LMDB 포맷으로 변환합니다.

사용법:
    conda activate omni
    python tools/ocr_finetuning/build_lmdb.py \
        --data_dir data/ocr_training/raw \
        --output_dir data/ocr_training/lmdb

출력:
    data/ocr_training/lmdb/
    ├── train/   ← LMDB (EasyOCR trainer 입력)
    └── val/     ← LMDB (EasyOCR trainer 입력)
"""

import argparse
import io
import os
from pathlib import Path

import cv2
import lmdb
import numpy as np
from PIL import Image


def write_lmdb(
    label_file: str,
    image_root: str,
    output_dir: str,
    max_size_gb: float = 10.0,
) -> int:
    """이미지+라벨 목록을 LMDB 데이터베이스로 변환합니다.

    LMDB 키 구조 (EasyOCR trainer 호환):
        image-{idx:09d}  ← JPEG 바이너리
        label-{idx:09d}  ← UTF-8 텍스트
        num-samples      ← 전체 샘플 수

    Args:
        label_file: 라벨 파일 경로 (각 줄: "images/xxxxxxx.jpg\\t텍스트").
        image_root: 이미지 파일의 루트 디렉토리.
        output_dir: LMDB 출력 디렉토리.
        max_size_gb: LMDB 최대 크기 (GB).

    Returns:
        저장된 샘플 수.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    lines = Path(label_file).read_text(encoding="utf-8").strip().splitlines()
    max_map_size = int(max_size_gb * 1024 ** 3)

    env = lmdb.open(
        output_dir,
        map_size=max_map_size,
        metasync=False,
        sync=False,
        meminit=False,
    )

    cache: dict[bytes, bytes] = {}
    n_samples_written = 0
    WRITE_BATCH = 1000  # 배치마다 commit

    for i, line in enumerate(lines):
        parts = line.strip().split("\t", maxsplit=1)
        if len(parts) != 2:
            continue

        rel_img_path, label = parts
        img_path = os.path.join(image_root, rel_img_path)

        if not os.path.exists(img_path):
            continue

        # 이미지를 JPEG 바이트로 읽기
        try:
            img = cv2.imread(img_path)
            if img is None:
                continue
            # BGR → RGB (PIL 저장용)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)

            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=95)
            img_bytes = buf.getvalue()
        except Exception:
            continue

        # LMDB 키 (1-indexed)
        idx = n_samples_written + 1
        img_key = f"image-{idx:09d}".encode()
        label_key = f"label-{idx:09d}".encode()

        cache[img_key] = img_bytes
        cache[label_key] = label.encode("utf-8")
        n_samples_written += 1

        # 배치 commit
        if n_samples_written % WRITE_BATCH == 0:
            with env.begin(write=True) as txn:
                for k, v in cache.items():
                    txn.put(k, v)
            cache = {}
            print(f"  {n_samples_written}/{len(lines)} 처리 중...", end="\r")

    # 나머지 commit
    with env.begin(write=True) as txn:
        for k, v in cache.items():
            txn.put(k, v)
        txn.put(b"num-samples", str(n_samples_written).encode())

    env.close()
    return n_samples_written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="학습 데이터를 LMDB 포맷으로 변환"
    )
    parser.add_argument(
        "--data_dir", default="data/ocr_training/raw",
        help="extract_training_data.py 출력 디렉토리 (기본값: data/ocr_training/raw)",
    )
    parser.add_argument(
        "--output_dir", default="data/ocr_training/lmdb",
        help="LMDB 출력 디렉토리 (기본값: data/ocr_training/lmdb)",
    )
    parser.add_argument(
        "--max_size_gb", type=float, default=10.0,
        help="LMDB 최대 크기 GB (기본값: 10)",
    )
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    output_dir = os.path.abspath(args.output_dir)

    print("\n" + "=" * 60)
    print("Phase 2: LMDB 변환")
    print("=" * 60)

    for split in ("train", "val"):
        label_file = os.path.join(data_dir, f"{split}.txt")
        lmdb_dir = os.path.join(output_dir, split)

        if not os.path.exists(label_file):
            print(f"  ⚠️  {split}.txt 없음, 건너뜀")
            continue

        print(f"\n  [{split}] 변환 중 → {lmdb_dir}")
        count = write_lmdb(
            label_file=label_file,
            image_root=data_dir,
            output_dir=lmdb_dir,
            max_size_gb=args.max_size_gb,
        )
        print(f"  [{split}] ✅ {count}개 샘플 저장 완료")

    print("\n📁 출력 구조:")
    print(f"  {output_dir}/")
    print(f"  ├── train/   ← LMDB")
    print(f"  └── val/     ← LMDB")
    print("\n다음 단계: README.md의 fine-tuning 명령어 참고")
    print("=" * 60)


if __name__ == "__main__":
    main()
