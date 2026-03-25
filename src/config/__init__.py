from .base import BaseConfig
from .k_omnidoc import config as k_omnidoc_config, KOmniDocConfig

# 기본 설정 (현재는 K-Omnidoc)
# 다른 프로젝트로 확장 시, 환경변수나 인자로 교체 가능하도록 설계
current_config: BaseConfig = k_omnidoc_config

def get_config() -> BaseConfig:
    return current_config

# Path Constants (Project Structure - Not Rule Config)
import os
import glob

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # src/config/../../ -> root
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")

# 기본값 (하위 호환성 유지)
DATA_DIR = os.path.join(PROJECT_ROOT, "data",  "2.result" , "Alchera_final_P1_260317", "json")
IMAGE_DIR = os.path.join(PROJECT_ROOT, "data", "2.result" , "Alchera_final_P1_260317", "img")
OCR_CACHE_DIR = ".ocr_cache"
OCR_CACHE_FILE = os.path.join(PROJECT_ROOT, OCR_CACHE_DIR, "batch_ocr_results.csv")


def get_delivery_batches() -> list[str]:
    """data/ 하위의 납품 배치 폴더 목록을 반환합니다.

    'Alchera_delivery_*' 패턴의 폴더를 인식합니다.

    Returns:
        배치 폴더명 목록 (basename). 최신 납품 순 내림차순 정렬.
    """
    patterns = [
        os.path.join(DATA_ROOT, "Alchera_delivery_*"),
        os.path.join(DATA_ROOT, "Alchera_rework_*"),
        os.path.join(DATA_ROOT, "Alchera_final_*"),
    ]
    matches = []
    for p in patterns:
        matches.extend([d for d in glob.glob(p) if os.path.isdir(d)])
    return sorted([os.path.basename(d) for d in matches], reverse=True)


def get_batch_dirs(batch_name: str) -> tuple[str, str]:
    """배치명으로 json/img 디렉토리 경로를 반환합니다.

    Args:
        batch_name: 납품 배치 폴더명 (예: 'Alchera_delivery_P1_260227').

    Returns:
        (json_dir, img_dir) 절대 경로 튜플.
    """
    base = os.path.join(DATA_ROOT, batch_name)
    return os.path.join(base, "json"), os.path.join(base, "img")

