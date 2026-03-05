import json
import os
import glob


def split_annotations(json_path, output_dir):
    """
    Splits a single large JSON file (containing a list of annotations)
    into individual JSON files, one for each annotation.
    Each file is named based on its image_path if available, otherwise using a generic name.
    """
    print(f"Loading annotations from {json_path}...")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            annotations = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input JSON file not found at '{json_path}'")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{json_path}'. Is it a valid JSON file?")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: '{output_dir}'")

    print(f"Splitting {len(annotations)} annotations into '{output_dir}'...")

    for i, ann in enumerate(annotations):
        page_info = ann.get("page_info", {})
        # Use image_path for filename, but fall back to a generic name
        image_path = page_info.get("image_path")
        
        if image_path:
            base_name = os.path.basename(image_path)
            file_name_without_ext = os.path.splitext(base_name)[0]
            json_filename = f"{file_name_without_ext}.json"
        else:
            json_filename = f"annotation_{i:05d}.json" # Use 5-digit padding for sorting

        save_path = os.path.join(output_dir, json_filename)

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(ann, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving annotation {i} to '{save_path}': {e}")
            continue

    print(f"Successfully saved {len(annotations)} JSON files to '{output_dir}'.")


if __name__ == "__main__":
    # Example usage if run directly
    # This assumes OmniDocBench.json exists in data/sample/
    # and splits it into data/sample/split_annotations/
    source_file = "data/sample/OmniDocBench.json"
    output_target_dir = "data/sample/split_annotations"
    split_annotations(source_file, output_target_dir)