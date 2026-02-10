from .base import BaseConfig
from .k_omnidoc import config as k_omnidoc_config, KOmniDocConfig

# 기본 설정 (현재는 K-Omnidoc)
# 다른 프로젝트로 확장 시, 환경변수나 인자로 교체 가능하도록 설계
current_config: BaseConfig = k_omnidoc_config

def get_config() -> BaseConfig:
    return current_config

# Path Constants (Project Structure - Not Rule Config)
import os
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # src/config/../../ -> root
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "poc_ver2", "json")
IMAGE_DIR = os.path.join(PROJECT_ROOT, "data", "poc_ver2", "img") 
OCR_CACHE_DIR = ".ocr_cache"
OCR_CACHE_FILE = os.path.join(PROJECT_ROOT, OCR_CACHE_DIR, "batch_ocr_results.csv")
