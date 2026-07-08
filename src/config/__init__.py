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
DATA = os.path.join(PROJECT_ROOT, "data")

# 기본값 (get_batch_dirs를 아직 쓰지 않는 페이지를 위한 하위 호환 fallback)
_DEFAULT_BATCH = "Alchera_delivery_P6_260605"
DATA_DIR = os.path.join(PROJECT_ROOT, "data", _DEFAULT_BATCH, "json")
IMAGE_DIR = os.path.join(PROJECT_ROOT, "data", _DEFAULT_BATCH, "img")
OCR_CACHE_DIR = ".ocr_cache"
OCR_CACHE_FILE = os.path.join(PROJECT_ROOT, OCR_CACHE_DIR, "batch_ocr_results.csv")


def get_delivery_batches() -> list[str]:
    """data/2.result 또는 sample/01_sample 하위의 납품 배치 폴더 목록을 반환합니다.

    'Alchera_delivery_*' 패턴의 폴더를 인식합니다.

    Returns:
        배치 폴더명 목록 (basename). 최신 납품 순 내림차순 정렬.
    """
    patterns = [
        os.path.join(DATA_ROOT, "Alchera_delivery_*"),
        os.path.join(DATA_ROOT, "2.result", "Alchera_delivery_*"),
        os.path.join(DATA_ROOT, "Alchera_rework_*"),
        os.path.join(DATA_ROOT, "Alchera_final_*"),
        os.path.join(PROJECT_ROOT, "sample", "01_sample", "Alchera_delivery_*"),
        os.path.join(PROJECT_ROOT, "sample", "01_sample", "Alchera_rework_*"),
    ]
    matches = []
    for p in patterns:
        matches.extend([d for d in glob.glob(p) if os.path.isdir(d)])
    return sorted([os.path.basename(d) for d in matches], reverse=True)


def get_batch_dirs(batch_name: str) -> tuple[str, str]:
    """배치명으로 json/img 디렉토리 경로를 반환합니다.
    
    sample/01_sample 또는 data/2.result 경로에서 찾습니다.

    Args:
        batch_name: 납품 배치 폴더명 (예: 'Alchera_delivery_P1_260227').

    Returns:
        (json_dir, img_dir) 절대 경로 튜플.
    """
    # sample/01_sample에서 먼저 찾기
    sample_base = os.path.join(PROJECT_ROOT, "sample", "01_sample", batch_name)
    if os.path.exists(sample_base):
        json_dir = os.path.join(sample_base, "json")
        img_dir = os.path.join(sample_base, "img")
        if not os.path.exists(img_dir) and any(f.lower().endswith(('.jpg', '.png', '.jpeg')) for f in os.listdir(sample_base) if os.path.isfile(os.path.join(sample_base, f))):
            img_dir = sample_base
        return json_dir, img_dir
    
    # 없으면 data/ 또는 data/2.result에서 찾기
    for base_dir in [DATA, os.path.join(DATA, "2.result")]:
        data_base = os.path.join(base_dir, batch_name)
        if os.path.exists(data_base):
            json_dir = os.path.join(data_base, "json")
            img_dir = os.path.join(data_base, "img")
            if not os.path.exists(img_dir) and any(f.lower().endswith(('.jpg', '.png', '.jpeg')) for f in os.listdir(data_base) if os.path.isfile(os.path.join(data_base, f))):
                img_dir = data_base
            return json_dir, img_dir
    
    # 기본값 반환 (폴더가 없더라도 경로 구조 유지)
    data_base = os.path.join(DATA, batch_name)
    return os.path.join(data_base, "json"), os.path.join(data_base, "img")

