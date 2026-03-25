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

    def to_dict(self) -> Dict[str, Any]:
        """Annotation 객체의 수정 사항을 raw_data 기반으로 병합하여 Dictionary로 반환합니다."""
        data = self.raw_data.copy() if self.raw_data else {}
        data["anno_id"] = getattr(self, "anno_id", -1)
        data["category_type"] = self.category_type
        data["poly"] = self.poly
        if self.order is not None:
            data["order"] = self.order
        if self.text is not None or "text" in data:
            data["text"] = self.text
        if self.latex is not None or "latex" in data:
            data["latex"] = self.latex
        if self.html is not None or "html" in data:
            data["html"] = self.html
        if self.caption is not None or "caption" in data:
            data["caption"] = self.caption
        data["ignore"] = getattr(self, "ignore", False)
        
        # Attribute 업데이트 로직 (다양한 K-Omnidoc 스키마 케이스 호환)
        if self.attributes:
            if "attribute" in data and isinstance(data["attribute"], dict):
                data["attribute"].update(self.attributes)
            elif "attributes" in data and isinstance(data["attributes"], dict):
                data["attributes"].update(self.attributes)
            else:
                for k, v in self.attributes.items():
                    data[f"attribute.{k}"] = v
                    
        return data

@dataclass
class Document:
    """문서 전체 데이터를 나타내는 데이터 클래스 (Generic)"""
    filename: str  # 파일명 (식별자)
    page_info: Dict[str, Any] # width, height, image_path 등
    layout_dets: List[Annotation]
    image_path: str
    raw_data: Dict[str, Any]  # 원본 전체 데이터
    filepath: Optional[str] = None # JSON 파일의 실제 경로

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
            raw_data=data,
            filepath=json_path
        )
        
    def save(self, save_path: str = None) -> None:
        """수정된 layout_dets 사항을 raw_data에 반영한 뒤 실제 JSON 파일에 덮어씁니다."""
        target_path = save_path or self.filepath
        if not target_path:
            raise ValueError("저장할 경로(filepath)가 지정되지 않았습니다.")
            
        # 1. Annotation들의 변경점을 to_dict() 호출하여 적용
        self.raw_data["layout_dets"] = [ann.to_dict() for ann in self.layout_dets]
        
        # 2. JSON 파일 저장
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(self.raw_data, f, ensure_ascii=False, indent=2)

def get_json_files(directory: str) -> List[str]:
    """지정된 디렉토리에서 모든 JSON 파일을 가져옵니다."""
    pattern = os.path.join(directory, "**/*.json")
    files = glob.glob(pattern, recursive=True)
    return sorted(files)
