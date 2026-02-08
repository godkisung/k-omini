import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any, Tuple
from src import config

def draw_annotations_on_image(
    image: Image.Image,
    annotations: List[Any], # List[Annotation]
    highlight_indices: List[int] = None,
    color_map: Dict[str, str] = config.CATEGORY_COLORS,
    default_color: str = config.CATEGORY_COLORS["default"],
    width: int = 3
) -> Image.Image:
    """
    이미지 위에 어노테이션 박스를 그립니다.
    
    Args:
        image: PIL Image 객체
        annotations: Annotation 객체 리스트
        highlight_indices: 강조할 어노테이션 인덱스 리스트
        color_map: 카테고리별 색상 매핑
    
    Returns:
        박스가 그려진 이미지 (복사본)
    """
    draw_img = image.copy()
    draw = ImageDraw.Draw(draw_img)
    
    # 폰트 로드 시도 (없으면 기본값)
    try:
        font = ImageFont.truetype("arial.ttf", 20) # 시스템 폰트
    except IOError:
        font = ImageFont.load_default()

    for idx, ann in enumerate(annotations):
        category = ann.category_type
        poly = ann.poly
        
        if not poly or len(poly) < 2:
            continue
            
        # 색상 결정
        color = color_map.get(category, default_color)
        current_width = width
        
        # 하이라이트 처리
        if highlight_indices and idx in highlight_indices:
            color = config.HIGHLIGHT_COLOR
            current_width = width + 3
            
        # Polygon 그리기
        # [x1, y1, x2, y2, ...] -> [(x1,y1), (x2,y2), ...]
        points = [(poly[i], poly[i+1]) for i in range(0, len(poly), 2)]
        if len(points) >= 2:
            draw.polygon(points, outline=color, width=current_width)
            
            # 인덱스 표시 (좌상단)
            text_pos = points[0]
            draw.text((text_pos[0], text_pos[1]-15), str(idx), fill=color, font=font)

    return draw_img

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """HEX 색상 코드를 RGB 튜플로 변환합니다."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
