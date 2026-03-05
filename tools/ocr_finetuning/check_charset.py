"""Phase 0: 문자셋 분석 스크립트.

모든 JSON 어노테이션의 텍스트를 스캔하여 실제 사용 문자를 추출하고,
EasyOCR korean_g2 모델의 기존 character set과 비교합니다.

사용법:
    conda activate omni
    python tools/ocr_finetuning/check_charset.py \
        --json_dir data/Alchera_delivery_P1_260227/json

출력:
    - 전체 고유 문자 수
    - 카테고리별 문자 사용 현황
    - EasyOCR character set 대비 누락 문자 목록
    - fine-tuning 전략 권고
"""

import argparse
import glob
import json
import os
import unicodedata
from collections import Counter
from pathlib import Path

# ── 텍스트 어노테이션 대상 카테고리 ────────────────────────────────────────────
TEXT_CATEGORIES = {
    "text_block", "title", "list", "list_item",
    "header", "footer", "page_number", "figure_caption",
    "table_caption", "page_footnote",
}

# ── EasyOCR korean_g2 character set 구성 ───────────────────────────────────────
# EasyOCR 한글 모델의 공식 character set:
#   숫자, 영문 대소문자, 일반 특수문자, 한글 완성형(가~힣)
# 실제 파일: ~/.EasyOCR/model/korean_g2.pth 로드 시 내부 config에서 확인 가능
# 여기서는 EasyOCR 소스코드 기준으로 알려진 character set을 재현합니다.
def _build_easyocr_korean_charset() -> set[str]:
    """EasyOCR korean_g2 모델의 기본 character set을 반환합니다."""
    chars: list[str] = []

    # 1. 숫자
    chars += list("0123456789")

    # 2. 영문 소문자
    chars += list("abcdefghijklmnopqrstuvwxyz")

    # 3. 영문 대문자
    chars += list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    # 4. 특수문자 (EasyOCR 한글 모델 기본 포함)
    special = (
        "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ "
        "\u00b7\u2019\u201c\u201d\u2018\u2022\u2026\u2013\u2014"  # 자주 쓰이는 유니코드
        "\u00b0\u00b1\u00d7\u00f7"  # ° ± × ÷
    )
    chars += list(special)

    # 5. 한글 완성형 (가~힣: U+AC00 ~ U+D7A3, 총 11,172자)
    for code in range(0xAC00, 0xD7A4):
        chars.append(chr(code))

    return set(chars)


EASYOCR_KO_CHARSET: set[str] = _build_easyocr_korean_charset()


# ── 핵심 분석 함수 ──────────────────────────────────────────────────────────────

def collect_chars_from_jsons(json_dir: str) -> tuple[Counter, Counter, Counter]:
    """JSON 디렉토리에서 문자 빈도를 수집합니다.

    Args:
        json_dir: JSON 파일이 있는 디렉토리 경로.

    Returns:
        (char_counter, category_counter, missing_counter)
        - char_counter: 전체 문자 빈도
        - category_counter: 카테고리별 어노테이션 수
        - missing_counter: EasyOCR charset에 없는 문자 빈도
    """
    json_files = glob.glob(os.path.join(json_dir, "**/*.json"), recursive=True)
    if not json_files:
        json_files = glob.glob(os.path.join(json_dir, "*.json"))

    char_counter: Counter = Counter()
    category_counter: Counter = Counter()
    missing_counter: Counter = Counter()
    skipped_empty = 0
    total_annotations = 0

    print(f"\n📂 JSON 파일 수: {len(json_files)}개")
    print("🔍 문자 수집 중...\n")

    for json_path in json_files:
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        for ann in data.get("layout_dets", []):
            cat = ann.get("category_type", "")
            if cat not in TEXT_CATEGORIES:
                continue

            text = ann.get("text", "") or ""
            text = text.strip()
            total_annotations += 1
            category_counter[cat] += 1

            if not text:
                skipped_empty += 1
                continue

            for ch in text:
                char_counter[ch] += 1
                if ch not in EASYOCR_KO_CHARSET:
                    missing_counter[ch] += 1

    print(f"  텍스트 어노테이션 총계: {total_annotations}개")
    print(f"  텍스트 비어있어 제외: {skipped_empty}개")
    print(f"  유효 어노테이션: {total_annotations - skipped_empty}개\n")

    return char_counter, category_counter, missing_counter


def _unicode_info(ch: str) -> str:
    """문자의 유니코드 정보 문자열을 반환합니다."""
    try:
        name = unicodedata.name(ch, "UNKNOWN")
    except ValueError:
        name = "UNKNOWN"
    return f"U+{ord(ch):04X} ({name})"


def print_report(
    char_counter: Counter,
    category_counter: Counter,
    missing_counter: Counter,
) -> None:
    """분석 결과 리포트를 출력합니다."""

    sep = "=" * 60

    # ── 전체 통계 ──────────────────────────────────────────────────────
    print(sep)
    print("📊 문자셋 분석 결과")
    print(sep)
    print(f"  고유 문자 수        : {len(char_counter):,}자")
    print(f"  전체 문자 출현 횟수 : {sum(char_counter.values()):,}회")
    print(f"  EasyOCR charset 포함: {len(EASYOCR_KO_CHARSET):,}자")
    print(f"  ⚠️  누락 문자 수    : {len(missing_counter):,}자")

    # ── 카테고리별 어노테이션 수 ───────────────────────────────────────
    print(f"\n{'─'*40}")
    print("📁 카테고리별 어노테이션 수")
    print(f"{'─'*40}")
    for cat, cnt in sorted(category_counter.items(), key=lambda x: -x[1]):
        print(f"  {cat:<25} {cnt:>6}개")

    # ── 상위 50 누락 문자 ──────────────────────────────────────────────
    print(f"\n{'─'*40}")
    print("❌ EasyOCR character set에 없는 문자 (상위 50개)")
    print(f"{'─'*40}")

    if not missing_counter:
        print("  ✅ 누락 문자 없음!")
    else:
        print(f"  {'문자':<6} {'빈도':>8}   유니코드 정보")
        print(f"  {'─'*4}   {'─'*6}   {'─'*30}")
        for ch, cnt in missing_counter.most_common(50):
            info = _unicode_info(ch)
            print(f"  {repr(ch):<6} {cnt:>8}회   {info}")

    # ── 전략 권고 ──────────────────────────────────────────────────────
    print(f"\n{'─'*40}")
    print("🎯 fine-tuning 전략 권고")
    print(f"{'─'*40}")

    if not missing_counter:
        print("""  ✅ 모든 문자가 EasyOCR 기존 charset에 포함됩니다.
  → 기존 korean_g2.pth에서 바로 fine-tuning 가능합니다.
  → Phase 1: extract_training_data.py 실행으로 진행하세요.\n""")
    else:
        significant = [(ch, cnt) for ch, cnt in missing_counter.most_common()
                       if cnt >= 5]
        rare = [(ch, cnt) for ch, cnt in missing_counter.most_common()
                if cnt < 5]

        print(f"  ⚠️  {len(missing_counter)}개의 누락 문자가 발견됐습니다.")

        if significant:
            chars_str = "".join(ch for ch, _ in significant)
            print(f"\n  【5회 이상 출현하는 중요 누락 문자 {len(significant)}개】")
            print(f"  {chars_str}")
            print("""
  → character set 확장이 필요합니다.
  → EasyOCR trainer의 character 파일에 위 문자를 수동으로 추가하세요.
  → output layer 크기가 변경되어 transfer learning 방식으로 fine-tuning합니다:
     (영향 없는 CNN/BiLSTM 레이어는 frozen, CTC head만 재초기화)""")

        if rare:
            print(f"\n  【5회 미만 출현 희귀 문자 {len(rare)}개】")
            print("  → 학습 데이터 부족으로 인식률 개선 어려움. 무시하거나 전처리 정리 권장.")

    # ── 학습 데이터용 charset 파일 제안 ───────────────────────────────
    print(f"\n{'─'*40}")
    print("💾 학습용 character set (tools/ocr_finetuning/charset.txt 저장 권장)")
    print(f"{'─'*40}")

    # 기존 EasyOCR charset + 누락 문자 (5회 이상) 합집합
    extended = set(EASYOCR_KO_CHARSET)
    for ch, cnt in missing_counter.items():
        if cnt >= 5:
            extended.add(ch)

    charset_str = "".join(sorted(extended, key=lambda c: ord(c)))
    print(f"  총 {len(extended)}자 (기존 {len(EASYOCR_KO_CHARSET)} + 추가 {len(extended) - len(EASYOCR_KO_CHARSET)})\n")

    # charset.txt 저장
    charset_output = Path(__file__).parent / "charset.txt"
    charset_output.write_text(charset_str, encoding="utf-8")
    print(f"  ✅ charset.txt 저장 완료: {charset_output}")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EasyOCR fine-tuning을 위한 문자셋 분석 스크립트"
    )
    parser.add_argument(
        "--json_dir",
        type=str,
        default="data/Alchera_delivery_P1_260227/json",
        help="JSON 파일 디렉토리 (기본값: data/Alchera_delivery_P1_260227/json)",
    )
    args = parser.parse_args()

    json_dir = os.path.abspath(args.json_dir)
    if not os.path.isdir(json_dir):
        print(f"❌ 디렉토리를 찾을 수 없습니다: {json_dir}")
        return

    char_counter, category_counter, missing_counter = collect_chars_from_jsons(json_dir)

    if not char_counter:
        print("❌ 텍스트 어노테이션을 찾을 수 없습니다. json_dir 경로를 확인하세요.")
        return

    print_report(char_counter, category_counter, missing_counter)


if __name__ == "__main__":
    main()
