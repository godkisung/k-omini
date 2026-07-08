import argparse
import json
import os
import shutil
from collections import Counter
from pprint import pprint

def analyze_table_layouts(json_dir, image_dir, output_base_dir):
    layout_counts = Counter()
    examples = {"horizontal": [], "vertical": []}
    
    # Create output directories
    horizontal_dir = os.path.join(output_base_dir, "horizontal")
    vertical_dir = os.path.join(output_base_dir, "vertical")
    os.makedirs(horizontal_dir, exist_ok=True)
    os.makedirs(vertical_dir, exist_ok=True)

    print(f"Scanning JSON directory: {json_dir}")
    print(f"Source image directory: {image_dir}")
    print(f"Output directory: {output_base_dir}")

    json_files = [f for f in os.listdir(json_dir) if f.endswith(".json")]
    total_files = len(json_files)
    print(f"Total JSON files to process: {total_files}")

    for i, filename in enumerate(json_files):
        if (i + 1) % 100 == 0:
            print(f"Processing file {i + 1}/{total_files}...")
            
        filepath = os.path.join(json_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Check for table category
                has_table = False
                table_layout = None
                
                if "layout_dets" in data:
                    for det in data["layout_dets"]:
                        if det.get("category_type") == "table":
                            has_table = True
                            attributes = det.get("attribute", {})
                            table_layout = attributes.get("table_layout")
                            if table_layout:
                                layout_counts[table_layout] += 1
                                
                                # Store examples
                                if len(examples[table_layout]) < 3:
                                    examples[table_layout].append({
                                        "file": filename,
                                        "html": det.get("html", "")[:500] + "..." if len(det.get("html", "")) > 500 else det.get("html", "")
                                    })
                
                # If we found a table with a layout, copy the image
                if has_table and table_layout in ["horizontal", "vertical"]:
                    # Try to find the image
                    # The JSON filename is like 'name.json', image is 'name.jpg' or 'name.png' usually inferred from page_info or filename
                    
                    image_filename = None
                    if "page_info" in data and "image_path" in data["page_info"]:
                         image_filename = data["page_info"]["image_path"]
                    
                    if not image_filename:
                        # Fallback: try replacing .json with .jpg or .png
                        base_name = os.path.splitext(filename)[0]
                        if os.path.exists(os.path.join(image_dir, base_name + ".jpg")):
                            image_filename = base_name + ".jpg"
                        elif os.path.exists(os.path.join(image_dir, base_name + ".png")):
                            image_filename = base_name + ".png"
                    
                    if image_filename:
                        # Some image_path might contain directories, we need just the basename for search if flat directory
                        # But judging by previous ls, image dir is flat.
                        # However page_info image_path might match the specific file in directory.
                        
                        src_image_path = os.path.join(image_dir, os.path.basename(image_filename))
                        if not os.path.exists(src_image_path):
                             # Try without extension match or strict match from json name
                             # Let's try to find it by name matching if path specific fails
                             base_name = os.path.splitext(filename)[0]
                             possible_exts = ['.jpg', '.png', '.jpeg']
                             for ext in possible_exts:
                                 if os.path.exists(os.path.join(image_dir, base_name + ext)):
                                     src_image_path = os.path.join(image_dir, base_name + ext)
                                     break
                        
                        if os.path.exists(src_image_path):
                            target_dir = horizontal_dir if table_layout == "horizontal" else vertical_dir
                            dst_image_path = os.path.join(target_dir, os.path.basename(src_image_path))
                            shutil.copy2(src_image_path, dst_image_path)
                        # else:
                        #     print(f"Warning: Image not found for {filename} (Expected: {image_filename})")

        except Exception as e:
            print(f"Error reading {filename}: {e}")

    print("\n--- Layout Counts ---")
    pprint(layout_counts)

    print(f"\nImages copied to {output_base_dir}/horizontal and {output_base_dir}/vertical")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="table_layout(horizontal/vertical) 속성별로 표가 포함된 문서 통계를 내고 예시 이미지를 분류합니다."
    )
    parser.add_argument("--json_dir", default="data/sample/split_annotations/", help="JSON 어노테이션 디렉토리")
    parser.add_argument("--image_dir", default="data/sample/OmniDocBench_images/", help="원본 이미지 디렉토리")
    parser.add_argument("--output_dir", default="data/sample/table_images/", help="분류된 예시 이미지를 저장할 디렉토리")
    args = parser.parse_args()

    analyze_table_layouts(args.json_dir, args.image_dir, args.output_dir)
