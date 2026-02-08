import os
import glob
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from src import config

@dataclass
class Annotation:
    """단일 어노테이션 데이터를 나타내는 데이터 클래스"""
    anno_id: int
    category_type: str
    poly: List[float]
    order: Optional[int] = None
    text: Optional[str] = None
    latex: Optional[str] = None
    html: Optional[str] = None
    caption: Optional[str] = None
    ignore: bool = False
    attributes: Dict[str, Any] = None
    raw_data: Dict[str, Any] = None  # 원본 JSON 데이터 보존
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Annotation':
        return cls(
            anno_id=data.get("anno_id", -1),
            category_type=data.get("category_type", "unknown"),
            poly=data.get("poly", []),
            order=data.get("order"), # Added order parsing
            text=data.get("text"),
            latex=data.get("latex"),
            html=data.get("html"),
            caption=data.get("caption"),
            ignore=data.get("ignore", False),
            attributes={k: v for k, v in data.items() if k.startswith("attribute.")},
            raw_data=data
        )

@dataclass
class Document:
    """문서 전체 데이터를 나타내는 데이터 클래스"""
    filename: str  # 파일명 (식별자)
    page_info: Dict[str, Any]
    layout_dets: List[Annotation]
    image_path: str
    raw_data: Dict[str, Any]  # 원본 전체 데이터

    @classmethod
    def from_json(cls, json_path: str) -> 'Document':
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON file not found: {json_path}")
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        filename = os.path.basename(json_path)

        # page_info 파싱
        page_info = data.get("page_info", {})
        image_path = page_info.get("image_path", "")
        
        # layout_dets 파싱
        layout_dets = [Annotation.from_dict(ann) for ann in data.get("layout_dets", [])]
        
        return cls(
            filename=filename,
            page_info=page_info,
            layout_dets=layout_dets,
            image_path=image_path,
            raw_data=data
        )

# --- Helper Functions (Previously app_helpers.py) ---

def get_json_files(directory: str = None) -> List[str]:
    """지정된 디렉토리(기본값: config.DATA_DIR)에서 모든 JSON 파일을 가져옵니다."""
    if directory is None:
        directory = config.DATA_DIR
    
    pattern = os.path.join(directory, "**/*.json")
    files = glob.glob(pattern, recursive=True)
    return sorted(files)

def load_document(file_path: str) -> Document:
    """JSON 파일 경로에서 Document 객체를 로드합니다."""
    return Document.from_json(file_path)
