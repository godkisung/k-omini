import os

# --- Path Constants ---
# 프로젝트 루트 디렉토리 (qa_visualizer의 부모 디렉토리)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "sample", "split_annotations")
IMAGE_DIR = os.path.join(PROJECT_ROOT, "data", "sample", "OmniDocBench_images")

# --- UI Constants ---
CATEGORY_COLORS = {
    "title": "#FF6347",
    "text_block": "#4169E1",
    "figure": "#2E8B57",
    "table": "#FFA500",
    "list": "#9370DB",
    "header": "#FF00FF",
    "footer": "#00FFFF",
    "figure_caption": "#A52A2A",
    "table_caption": "#A52A2A",
    "equation_isolated": "#008080",
    "default": "#343a40",
}
HIGHLIGHT_COLOR = "#00FF7F"
ERROR_COLOR = "#FF0000"
WARNING_COLOR = "#FFD700"

# --- Validation Constants ---
COMMON_REQUIRED_KEYS = ["anno_id", "category_type", "ignore", "poly"]
UNORDERED_CATEGORIES = ["header", "page_number", "abandon", "footer", "page_footnote", "need_mask"]

REQUIRED_KEYS = {
    "text_group": COMMON_REQUIRED_KEYS
    + ["text", "attribute.text_language", "attribute.text_rotate"],
    "equation_isolated": COMMON_REQUIRED_KEYS
    + ["latex", "attribute.equation_language", "attribute.formula_type"],
    "table": COMMON_REQUIRED_KEYS
    + [
        "html",
        "table_edit_status",
        "attribute.line",
        "attribute.table_layout",
        "attribute.language",
    ],
    "figure": COMMON_REQUIRED_KEYS + ["attribute.contains_elements", "sub_regions"],
    "chart": COMMON_REQUIRED_KEYS
    + [
        "html",
        "attribute.chart_type",
        "attribute.language",
        "attribute.chart_level",
        "attribute.is_indexed",
    ],
    "mask_group": COMMON_REQUIRED_KEYS,
}
VALID_PARENT_SON_PAIRS = {
    "Figure": [
        "figure_caption",
        "figure_footnote",
        "text_block",
        "figure",
        "table",
        "equation_isolated",
    ],
    "Table": [
        "table_caption",
        "table_footnote",
        "text_block",
        "figure",
        "table",
        "equation_isolated",
    ],
    "Equation": ["eq_caption", "explanation", "text_block"],
}

# --- OCR 설정 ---
OCR_ENABLED = True  # OCR 기능 활성화 여부
OCR_SIMILARITY_THRESHOLD = 0.9  # 텍스트 유사도 임계값 (90%)
OCR_CACHE_DIR = ".ocr_cache"  # OCR 결과 캐시 디렉토리
TABLE_STRUCTURE_TOLERANCE = 1  # 표 행/열 개수 허용 오차
