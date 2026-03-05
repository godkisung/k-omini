import json
import os
from PIL import Image, ImageDraw, ImageFont
import math
import sys  # Import sys for command-line arguments
from PIL import ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True


def draw_arrow(draw, start, end, color="magenta", width=5):
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


def get_poly_center(poly):
    if not poly or len(poly) < 2:
        return None
    # Assuming poly is [x1, y1, x2, y2, ...]
    xs = poly[0::2]
    ys = poly[1::2]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def draw_annotations(
    json_data, image_dir, output_dir, relation_output_dir="visualized_relations"
):
    """
    Draws annotations on images based on JSON data.
    json_data can be a single annotation dict or a list of annotation dicts.
    """
    # Ensure json_data is a list of annotations for consistent processing
    if not isinstance(json_data, list):
        json_data = [json_data]

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if not os.path.exists(relation_output_dir):
        os.makedirs(relation_output_dir)

    # Define colors for known categories
    colors = {
        "title": "red",
        "text_block": "blue",
        "figure": "green",
        "table": "orange",
        "list": "purple",
        "header": "magenta",
        "footer": "cyan",
        "caption": "brown",
    }
    default_color = "yellow"

    # --- FONT MODIFICATION ---
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except IOError:
        print("DejaVuSans.ttf not found. Using default PIL font.")
        font = ImageFont.load_default()
    # --- END FONT MODIFICATION ---

    processed_count = 0
    relation_count = 0

    for ann in json_data:  # Iterate through the list of annotations
        page_info = ann.get("page_info", {})
        image_filename = page_info.get("image_path")

        if not image_filename:
            continue

        full_image_path = os.path.join(image_dir, image_filename)

        if not os.path.exists(full_image_path):
            full_image_path = os.path.join(image_dir, os.path.basename(image_filename))
            if not os.path.exists(full_image_path):
                print(f"Image not found: {full_image_path}")
                continue

        try:
            image = Image.open(full_image_path).convert("RGB")
            draw = ImageDraw.Draw(image)

            layout_dets = ann.get("layout_dets", [])
            id_to_center = {}

            for det in layout_dets:
                poly = det.get("poly")
                category = det.get("category_type", "unknown")
                anno_id = det.get("anno_id")

                if poly:
                    center = get_poly_center(poly)
                    if anno_id is not None and center:
                        id_to_center[anno_id] = center

                    color = colors.get(category, default_color)
                    draw.polygon(poly, outline=color, width=3)

                    if len(poly) >= 2:
                        x, y = poly[0], poly[1]
                        label = f"{category}"
                        if det.get("order") is not None:
                            label += f" ({det['order']})"

                        try:
                            bbox = draw.textbbox((x, y), label, font=font)
                            draw.rectangle(bbox, fill=color)
                            draw.text((x, y), label, fill="white", font=font)
                        except AttributeError:
                            # Fallback for older Pillow versions
                            # For older Pillow, draw.textsize also needs font
                            w, h = draw.textsize(
                                label, font=font
                            )  # Ensure font is passed here
                            draw.rectangle((x, y, x + w, y + h), fill=color)
                            draw.text((x, y), label, fill="white", font=font)

            relations = ann.get("extra", {}).get("relation", [])
            has_relations = False

            for rel in relations:
                source_id = rel.get("source_anno_id")
                target_id = rel.get("target_anno_id")
                rel_type = rel.get("relation_type", "")

                if source_id in id_to_center and target_id in id_to_center:
                    has_relations = True
                    start_pt = id_to_center[source_id]
                    end_pt = id_to_center[target_id]

                    draw_arrow(draw, start_pt, end_pt, color="magenta", width=4)

                    mid_x = (start_pt[0] + end_pt[0]) / 2
                    mid_y = (start_pt[1] + end_pt[1]) / 2
                    try:
                        bbox = draw.textbbox((mid_x, mid_y), rel_type, font=font)
                        draw.rectangle(bbox, fill="magenta")
                        draw.text((mid_x, mid_y), rel_type, fill="white", font=font)
                    except:
                        pass

            save_path = os.path.join(
                output_dir, f"vis_{os.path.basename(image_filename)}"
            )
            image.save(save_path)
            processed_count += 1

            if has_relations:
                rel_save_path = os.path.join(
                    relation_output_dir, f"vis_rel_{os.path.basename(image_filename)}"
                )
                image.save(rel_save_path)
                relation_count += 1

            if processed_count % 10 == 0:
                print(f"Processed {processed_count} images...")

        except Exception as e:
            print(f"Error processing {full_image_path}: {e}")

    print(f"Done. Total processed: {processed_count}.")
    print(f"Images with relations saved to '{relation_output_dir}': {relation_count}")
    print(f"Done. Visualized {processed_count} images in '{output_dir}'.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        # Single-file test mode
        json_file_path = sys.argv[1]
        source_image_dir = (
            "data/OmniDocBench_images"  # This is where the original images are
        )
        temp_output_dir = "temp_vis_output"

        print(f"Running in single-file test mode on: {json_file_path}")

        # Load the single annotation file
        with open(json_file_path, "r", encoding="utf-8") as f:
            single_annotation_data = json.load(f)

        # The draw_annotations function now expects json_data to be a list,
        # so we pass the loaded single_annotation_data directly (it will be wrapped inside the function)
        draw_annotations(single_annotation_data, source_image_dir, temp_output_dir)

    else:
        # Default behavior: process the main OmniDocBench.json
        print("Running in default mode on data/OmniDocBench.json")
        # For default mode, the main OmniDocBench.json itself contains a list of annotations
        draw_annotations(
            json.load(open("data/OmniDocBench.json", "r", encoding="utf-8")),
            "data/OmniDocBench_images",
            "visualizations/visualized_samples",
        )
