from PIL import Image, ImageDraw
from .config import CATEGORY_COLORS, HIGHLIGHT_COLOR, ERROR_COLOR, WARNING_COLOR


def get_poly_center(poly):
    """Calculate the geometric center of a polygon."""
    if not poly or len(poly) < 2:
        return None
    x_coords, y_coords = poly[0::2], poly[1::2]
    center_x = sum(x_coords) / len(x_coords)
    center_y = sum(y_coords) / len(y_coords)
    return (center_x, center_y)


def draw_annotations_on_image(
    image, layout_dets, highlight_id=None, relations=[], all_dets=[], error_ids=None, warning_ids=None
):
    """Draw annotations and relationships on a given image."""
    draw = ImageDraw.Draw(image, "RGBA")
    dets_map = {det.get("anno_id"): det for det in all_dets}
    
    error_ids = set(error_ids) if error_ids else set()
    warning_ids = set(warning_ids) if warning_ids else set()

    # Draw polygons
    for det in layout_dets:
        poly = det.get("poly")
        if not poly:
            continue
        
        anno_id = det.get("anno_id")
        is_selected = anno_id == highlight_id
        
        # 기본 색상
        color = CATEGORY_COLORS.get(det.get("category_type"), CATEGORY_COLORS["default"])
        
        # 오류/경고 색상 적용
        if anno_id in error_ids:
            color = ERROR_COLOR
        elif anno_id in warning_ids:
            color = WARNING_COLOR
            
        if is_selected:
            color = HIGHLIGHT_COLOR
        
        width = 5 if is_selected else 3

        # Ensure poly is a list of tuples
        p = list(map(tuple, zip(poly[0::2], poly[1::2])))
        draw.polygon(p, outline=color, width=width)

    # Draw relation lines if an item is highlighted
    if highlight_id is not None and relations:
        involved_relations = [
            rel
            for rel in relations
            if highlight_id in (rel.get("source_anno_id"), rel.get("target_anno_id"))
        ]

        for rel in involved_relations:
            source_det = dets_map.get(rel.get("source_anno_id"))
            target_det = dets_map.get(rel.get("target_anno_id"))

            if source_det and target_det:
                start_point = get_poly_center(source_det.get("poly"))
                end_point = get_poly_center(target_det.get("poly"))

                if start_point and end_point:
                    rel_color = (
                        "orange"
                        if rel.get("relation_type") == "parent_son"
                        else "deepskyblue"
                    )
                    draw.line([start_point, end_point], fill=rel_color, width=4)

                    # Draw a circle at the target end
                    ex, ey = end_point
                    draw.ellipse(
                        (ex - 8, ey - 8, ex + 8, ey + 8),
                        fill=rel_color,
                        outline="black",
                    )

    return image
