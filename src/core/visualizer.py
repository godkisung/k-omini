import numpy as np
import math
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any, Tuple, Optional
from src.core.models import Annotation
from src.config.base import BaseConfig

def draw_arrow(draw, start, end, color="magenta", width=5):
    """Draws an arrow from start to end points."""
    # Draw the line
    draw.line([start, end], fill=color, width=width)

    # Calculate arrow head
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    angle = math.atan2(dy, dx)
    arrow_len = 20

    # Arrow head points
    angle1 = angle + math.pi * 0.85
    angle2 = angle - math.pi * 0.85

    x1 = end[0] + arrow_len * math.cos(angle1)
    y1 = end[1] + arrow_len * math.sin(angle1)
    x2 = end[0] + arrow_len * math.cos(angle2)
    y2 = end[1] + arrow_len * math.sin(angle2)

    draw.polygon([end, (x1, y1), (x2, y2)], fill=color)

def get_poly_center(poly: List[float]) -> Optional[Tuple[float, float]]:
    if not poly or len(poly) < 2:
        return None
    xs = poly[0::2]
    ys = poly[1::2]
    return (sum(xs) / len(xs), sum(ys) / len(ys))

def draw_annotations_on_image(
    image: Image.Image,
    annotations: List[Annotation],
    config: BaseConfig,
    highlight_indices: List[int] = None,
    width: int = 4,
    relations: List[Dict[str, Any]] = None,
    show_all_relations: bool = False,
    selected_anno_id: Optional[str] = None
) -> Image.Image:
    """
    이미지 위에 어노테이션 박스와 관계 화살표를 그립니다.
    """
    draw_img = image.copy()
    draw = ImageDraw.Draw(draw_img)
    
    try:
        font_names = ["arial.ttf", "FreeSans.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf", "NanumGothic.ttf"]
        font = None
        for fn in font_names:
            try:
                font = ImageFont.truetype(fn, 36)
                break
            except IOError:
                continue
        if font is None:
            font = ImageFont.load_default()
    except IOError:
        font = ImageFont.load_default()

    # 1. Map ID to Center for relation drawing
    id_to_center = {}

    for idx, ann in enumerate(annotations):
        category = ann.category_type
        poly = ann.poly
        
        if not poly or len(poly) < 2:
            continue
            
        # Center Calculation
        center = get_poly_center(poly)
        if ann.anno_id is not None and center:
            id_to_center[ann.anno_id] = center

        # Color
        color = config.get_color(category)
        current_width = width
        
        # Highlight
        is_highlighted = highlight_indices and idx in highlight_indices
        if is_highlighted:
            color = "#00FF7F" # SpringGreen for highlight
            current_width = width + 4
            
        # Draw Polygon
        points = [(poly[i], poly[i+1]) for i in range(0, len(poly), 2)]
        if len(points) >= 2:
            draw.polygon(points, outline=color, width=current_width)
            
            # Draw Index/Label (ID & Order)
            text_pos = points[0]
            label = f"ID:{ann.anno_id}" if ann.anno_id is not None else f"idx:{idx}"
            if ann.order is not None:
                label += f" [Ord:{ann.order}]"
            
            # 텍스트 배경을 그려 가독성 향상 (선택 사항이지만 추천)
            try:
                t_bbox = draw.textbbox((text_pos[0], text_pos[1]-40), label, font=font)
                draw.rectangle(t_bbox, fill="black")
                draw.text((text_pos[0], text_pos[1]-40), label, fill="white", font=font)
            except AttributeError:
                draw.text((text_pos[0], text_pos[1]-40), label, fill=color, font=font)

    # 2. Draw Relations
    if relations:
        for rel in relations:
            source_id = rel.get("source_anno_id")
            target_id = rel.get("target_anno_id")
            rel_type = rel.get("relation_type", "")
            
            # Logic: Draw if show_all is True OR if selected_anno_id matches source or target
            should_draw = show_all_relations
            if not should_draw and selected_anno_id:
                # Assuming anno_id is string or int, handle comparison carefully
                # In JSON it's usually string or int. Let's convert to string for safety if needed
                # But ID map keys are as they come from Annotation.
                if str(source_id) == str(selected_anno_id) or str(target_id) == str(selected_anno_id):
                    should_draw = True
            
            if should_draw and source_id in id_to_center and target_id in id_to_center:
                start_pt = id_to_center[source_id]
                end_pt = id_to_center[target_id]
                
                # Draw Arrow
                arrow_color = "magenta"
                draw_arrow(draw, start_pt, end_pt, color=arrow_color, width=4)
                
                # Draw Label (midpoint)
                mid_x = (start_pt[0] + end_pt[0]) / 2
                mid_y = (start_pt[1] + end_pt[1]) / 2
                
                # Simple text background
                try:
                    bbox = draw.textbbox((mid_x, mid_y), rel_type, font=font)
                    draw.rectangle(bbox, fill="magenta")
                    draw.text((mid_x, mid_y), rel_type, fill="white", font=font)
                except AttributeError:
                    # Fallback
                    draw.text((mid_x, mid_y), rel_type, fill="white", font=font)

    return draw_img
