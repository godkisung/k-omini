import json
import re
import os
import math
from collections import defaultdict


def is_empty_value(value):
    """Checks if a value is considered 'empty'."""
    if value is None:
        return True
    if isinstance(value, (str, list, dict)):
        return not bool(value)  # Empty string, list, dict
    return False


def find_nested_key(data_dict, key_path):
    """
    Recursively finds a nested key in a dictionary or list.
    Returns the value if found. If a list is encountered along the path,
    it returns a list of all found values from its elements.
    Returns None if not found.
    """
    if not key_path:
        return data_dict

    current_key = key_path[0]
    remaining_path = key_path[1:]

    if isinstance(data_dict, dict):
        if current_key in data_dict:
            return find_nested_key(data_dict[current_key], remaining_path)
    elif isinstance(data_dict, list):
        results = []
        for item in data_dict:
            res = find_nested_key(item, key_path)
            if res is not None:
                if isinstance(res, list):
                    results.extend(res)
                else:
                    results.append(res)
        return results if results else None
    return None


def get_poly_center(poly):
    """
    Calculates the center of a polygon.
    Assuming poly is a flat list [x1, y1, x2, y2, ...] or a list of [x, y] pairs.
    """
    if not poly:
        return None

    # Normalize to list of [x, y] pairs if it's a flat list
    if all(isinstance(p, (int, float)) for p in poly) and len(poly) % 2 == 0:
        parsed_poly = [[poly[i], poly[i+1]] for i in range(0, len(poly), 2)]
    elif all(isinstance(p, (list, tuple)) and len(p) == 2 for p in poly):
        parsed_poly = poly
    else:
        return None # Invalid polygon format

    if not parsed_poly:
        return None

    xs = [p[0] for p in parsed_poly]
    ys = [p[1] for p in parsed_poly]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def draw_arrow(draw, start, end, color="magenta", width=5):
    """Draws an arrow on a PIL ImageDraw object."""
    draw.line([start, end], fill=color, width=width)

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    angle = math.atan2(dy, dx)
    arrow_len = 20

    angle1 = angle + math.pi * 0.85
    angle2 = angle - math.pi * 0.85

    x1 = end[0] + arrow_len * math.cos(angle1)
    y1 = end[1] + arrow_len * math.sin(angle1)
    x2 = end[0] + arrow_len * math.cos(angle2)
    y2 = end[1] + arrow_len * math.sin(angle2)

    draw.polygon([end, (x1, y1), (x2, y2)], fill=color)


def sanitize_for_path(text):
    """Sanitizes a string to be safely used as a directory or filename."""
    return re.sub(r"[^\w\-_\. ]", "_", str(text))


def build_key_type_map(source_dirs):
    """Builds a map of key types by scanning all JSON files."""
    key_type_map = defaultdict(set)

    def _process_annotation_recursive(anno, context, category_type, current_key_path):
        if not isinstance(anno, dict):
            return

        for key, value in anno.items():
            full_key = ".".join(current_key_path + [key])
            # Record the type of the direct key
            dtype = type(value).__name__
            key_type_map[(category_type, context, full_key)].add(dtype)

            # Recurse into dictionaries
            if isinstance(value, dict):
                _process_annotation_recursive(
                    value, context, category_type, current_key_path + [key]
                )
            # Recurse into list items
            elif isinstance(value, list):
                for item in value:
                    item_category_type = (
                        item.get("category_type", category_type)
                        if isinstance(item, dict)
                        else category_type
                    )
                    _process_annotation_recursive(
                        item, key, item_category_type, current_key_path + [key]
                    )

    for source_dir in source_dirs:
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            json_data = json.load(f)

                            if "layout_dets" in json_data and isinstance(
                                json_data["layout_dets"], list
                            ):
                                for anno in json_data["layout_dets"]:
                                    if (
                                        isinstance(anno, dict)
                                        and "category_type" in anno
                                    ):
                                        _process_annotation_recursive(
                                            anno,
                                            "block",
                                            anno["category_type"],
                                            [], # Start with empty path for top-level keys
                                        )

                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Ignore files that can't be parsed
                        continue

    return key_type_map
