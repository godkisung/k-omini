from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json
import os
import glob

@dataclass
class Annotation:
    """단일 어노테이션 데이터를 나타내는 데이터 클래스 (Generic)"""
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
        """
        Generic Loader:
        - 기본 필드는 직접 할당
        - 나머지 필드 중 'attribute.'로 시작하는 것은 attributes로 분류 (K-Omnidoc convention)
        - 하지만 다른 스키마도 수용 가능하도록 raw_data 보존
        """
        attributes = {k: v for k, v in data.items() if k.startswith("attribute.")}
        
        # Support for nested "attribute" or "attributes" dictionary
        # Support for nested "attribute" or "attributes" dictionary
        # Support for nested "attribute" or "attributes" dictionary
        if "attribute" in data and isinstance(data["attribute"], dict):
            # print(f"DEBUG: Found nested attribute: {data['attribute']}")
            attributes.update(data["attribute"])
        if "attributes" in data and isinstance(data["attributes"], dict):
            attributes.update(data["attributes"])
        
        return cls(
            anno_id=data.get("anno_id", -1),
            category_type=data.get("category_type", "unknown"),
            poly=data.get("poly", []),
            order=data.get("order"),
            text=data.get("text"),
            latex=data.get("latex"),
            html=data.get("html"),
            caption=data.get("caption"),
            ignore=data.get("ignore", False),
            attributes=attributes,
            raw_data=data
        )

@dataclass
class Document:
    """문서 전체 데이터를 나타내는 데이터 클래스 (Generic)"""
    filename: str  # 파일명 (식별자)
    page_info: Dict[str, Any] # width, height, image_path 등
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

        # page_info 파싱 (Generic: 키가 없으면 빈 dict)
        page_info = data.get("page_info", {})
        
        # Image Path Logic (Project specific logic might be needed here, but keeping simple for now)
        image_path = page_info.get("image_path", "")
        
        # layout_dets 파싱
        # 'layout_dets' 키는 LabelMe 등 표준은 아니지만, 이 프로젝트 컨벤션.
        # 다른 포맷 지원 시엔 별도 로더 필요.
        layout_dets = [Annotation.from_dict(ann) for ann in data.get("layout_dets", [])]
        
        return cls(
            filename=filename,
            page_info=page_info,
            layout_dets=layout_dets,
            image_path=image_path,
            raw_data=data
        )

def get_json_files(directory: str) -> List[str]:
    """지정된 디렉토리에서 모든 JSON 파일을 가져옵니다."""
    pattern = os.path.join(directory, "**/*.json")
    files = glob.glob(pattern, recursive=True)
    return sorted(files)
