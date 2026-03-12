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
            
            # Draw Index/Label
            text_pos = points[0]
            label = str(idx)
            if ann.order is not None:
                label += f" ({ann.order})"
            
            draw.text((text_pos[0], text_pos[1]-20), label, fill=color, font=font)

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

def create_plotly_figure(
    image: Image.Image,
    annotations: List[Annotation],
    config: BaseConfig,
    highlight_indices: List[int] = None,
    relations: List[Dict[str, Any]] = None,
    show_all_relations: bool = False,
    selected_anno_id: Optional[str] = None
):
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    # 1. 이미지 배경 추가
    fig.add_layout_image(
        dict(
            source=image,
            xref="x",
            yref="y",
            x=0,
            y=0,
            sizex=image.width,
            sizey=image.height,
            sizing="stretch",
            opacity=1,
            layer="below"
        )
    )
    
    fig.update_layout(
        autosize=True,
        # Set a minimum sufficient height for the bounding box layout to prevent shrinking
        # Streamlit use_container_width manages the width, so we need to set a proper height
        height=800,  # Or calculate based on image aspect ratio -> image.height * (container_width/image.width)
        margin=dict(l=0, r=0, b=0, t=0),
        xaxis=dict(range=[0, image.width], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(
            range=[image.height, 0], 
            showgrid=False, 
            zeroline=False, 
            visible=False,
            scaleanchor="x",
            scaleratio=1
        ),
        plot_bgcolor="white",
    )
    
    shapes = []
    text_xs = []
    text_ys = []
    texts = []
    text_colors = []
    text_sizes = []
    
    id_to_center = {}
    
    # 2. 바운딩 박스 (SVG Shape) 추가
    for idx, ann in enumerate(annotations):
        category = ann.category_type
        poly = ann.poly
        
        if not poly or len(poly) < 2:
            continue
            
        center = get_poly_center(poly)
        if ann.anno_id is not None and center:
            id_to_center[ann.anno_id] = center

        color = config.get_color(category)
        is_highlighted = highlight_indices and idx in highlight_indices
        if is_highlighted:
            color = "#00FF7F" 
            
        # SVG Path 생성
        path = "M " + " L ".join([f"{poly[i]} {poly[i+1]}" for i in range(0, len(poly), 2)]) + " Z"
        
        shapes.append(dict(
            type="path",
            path=path,
            line_color=color,
            line_width=3 if not is_highlighted else 8,
            fillcolor="rgba(0,0,0,0)"
        ))
        
        # 텍스트 라벨 (순서)
        label = str(idx)
        if ann.order is not None:
            label += f" ({ann.order})"
        
        texts.append(label)
        text_xs.append(poly[0])
        text_ys.append(max(0, poly[1] - 15))
        text_colors.append(color)
        text_sizes.append(20 if not is_highlighted else 28)
        
    fig.update_layout(shapes=shapes)
    
    # 3. 텍스트 라벨 추가 (Scatter)
    if texts:
        fig.add_trace(go.Scatter(
            x=text_xs,
            y=text_ys,
            mode="text",
            text=texts,
            textfont=dict(color=text_colors, size=text_sizes, family="Arial Black, sans-serif"),
            hoverinfo="none",
            showlegend=False
        ))
        
    # 4. 관계 화살표 추가 (Annotation)
    if relations:
        draw_annotations = []
        for rel in relations:
            source_id = rel.get("source_anno_id")
            target_id = rel.get("target_anno_id")
            rel_type = rel.get("relation_type", "")
            
            should_draw = show_all_relations
            if not should_draw and selected_anno_id:
                if str(source_id) == str(selected_anno_id) or str(target_id) == str(selected_anno_id):
                    should_draw = True
            
            if should_draw and source_id in id_to_center and target_id in id_to_center:
                start_pt = id_to_center[source_id]
                end_pt = id_to_center[target_id]
                
                draw_annotations.append(go.layout.Annotation(
                    x=end_pt[0],
                    y=end_pt[1],
                    ax=start_pt[0],
                    ay=start_pt[1],
                    xref="x", yref="y",
                    axref="x", ayref="y",
                    showarrow=True,
                    arrowhead=3,
                    arrowsize=2,
                    arrowwidth=3,
                    arrowcolor="magenta",
                    text=rel_type,
                    font=dict(color="white", size=14),
                    bgcolor="magenta",
                    opacity=0.8
                ))
        fig.update_layout(annotations=draw_annotations)
        
    return fig
