import json
import os
import glob
import shutil

SOURCE_JSON_DIR = "data"
SOURCE_IMAGE_DIR = "visualizations/visualized_samples"
TARGET_DIR = "data/analysis_samples"

# RELATION_TYPES_TO_FIND = {"parent_son", "truncated"}
RELATION_TYPES_TO_FIND = {"layout_dets", "category_type", "table"}

def find_and_copy_relation_samples():
    """
    Finds JSON files containing specific relation_types and copies them
    along with their corresponding images to a new directory.
    This version uses explicit string concatenation for filename construction.
    """
    if not os.path.exists(SOURCE_JSON_DIR):
        print(f"Error: Source JSON directory '{SOURCE_JSON_DIR}' not found.")
        return
    if not os.path.exists(SOURCE_IMAGE_DIR):
        print(f"Error: Source image directory '{SOURCE_IMAGE_DIR}' not found.")
        return

    os.makedirs(TARGET_DIR, exist_ok=True)
    print(f"Target directory '{TARGET_DIR}' created or already exists.")

    # --- Step 1: Get a set of all available image filenames for fast lookup ---
    all_image_filenames_raw = os.listdir(SOURCE_IMAGE_DIR)
    all_image_filenames = set(all_image_filenames_raw)

    # Debug print: First 10 image filenames found in 'visualized_samples'
    # print(f"\n--- DEBUG: First 10 image filenames found in '{SOURCE_IMAGE_DIR}' ---")
    # for i, fname in enumerate(sorted(list(all_image_filenames))):
    #     if i >= 10: break
    #     print(f"  Raw image filename {i}: '{fname}' (length: {len(fname)})")
    # print("------------------------------------------------------------------\n")

    json_files = glob.glob(os.path.join(SOURCE_JSON_DIR, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{SOURCE_JSON_DIR}'.")
        return

    print(
        f"Analyzing {len(json_files)} JSON files to find relations: {RELATION_TYPES_TO_FIND}..."
    )

    # --- Step 2: First, identify all JSONs that need to be copied ---
    jsons_to_copy = []
    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            extra_data = data.get("extra")
            if not isinstance(extra_data, dict):
                continue

            relations = extra_data.get("relation")
            if not isinstance(relations, list):
                continue

            for relation in relations:
                if (
                    isinstance(relation, dict)
                    and relation.get("relation_type") in RELATION_TYPES_TO_FIND
                ):
                    jsons_to_copy.append(json_path)
                    break  # Found a match, no need to check other relations in this file
        except Exception as e:
            print(f"An error occurred while reading {os.path.basename(json_path)}: {e}")

    # --- Step 3: Now, copy the identified JSONs and their matching images ---
    print(
        f"Found {len(jsons_to_copy)} JSON files with specified relations. Now copying files..."
    )
    copied_json_count = 0
    copied_image_count = 0
    missing_image_details = []

    for json_path in jsons_to_copy:
        json_filename = os.path.basename(json_path)
        base_filename_no_ext = os.path.splitext(json_filename)[0]

        # 1. Copy the JSON file
        try:
            shutil.copy(json_path, os.path.join(TARGET_DIR, json_filename))
            copied_json_count += 1
        except Exception as e:
            print(f"Error copying JSON '{json_filename}': {e}")
            continue  # Skip image copy if JSON copy failed

        # 2. Try to find and copy the corresponding image using the pre-built set
        found_image_for_json = False
        potential_extensions = [".jpg", ".png", ".jpeg"]
        for ext in potential_extensions:
            # Changed to explicit string concatenation
            expected_image_name = "vis_" + base_filename_no_ext + ext

            # --- DEBUG PRINT (now commented out for cleaner output, re-enable if needed) ---
            # print(f"  DEBUG: For JSON '{json_filename}' (length: {len(json_filename)}), expecting image: '{expected_image_name}' (length: {len(expected_image_name)})")
            # print(f"  DEBUG: Is '{expected_image_name}' in all_image_filenames? {expected_image_name in all_image_filenames}")
            # if expected_image_name not in all_image_filenames:
            #     for actual_img_name in all_image_filenames:
            #         if base_filename_no_ext in actual_img_name and "vis_" in actual_img_name:
            #             print(f"  DEBUG: Close match found in image dir: '{actual_img_name}' (length: {len(actual_img_name)})")
            #             print(f"  DEBUG: Expected for compare: '{expected_image_name}' (length: {len(expected_image_name)})")
            #             min_len = min(len(expected_image_name), len(actual_img_name))
            #             diff_found = False
            #             for i in range(min_len):
            #                 if expected_image_name[i] != actual_img_name[i]:
            #                     print(f"    Diff at index {i}: Expected char '{expected_image_name[i]}' (ASCII {ord(expected_image_name[i])}) vs Actual char '{actual_img_name[i]}' (ASCII {ord(actual_img_name[i])})")
            #                     diff_found = True
            #             if len(expected_image_name) != len(actual_img_name):
            #                 print(f"    Length difference: Expected {len(expected_image_name)} vs Actual {len(actual_img_name)}")
            #             elif not diff_found:
            #                 print(f"    No character diff found, but 'in' check failed. This is unexpected.")
            #             break
            # --- END DEBUG PRINT ---

            if expected_image_name in all_image_filenames:
                source_image_path = os.path.join(SOURCE_IMAGE_DIR, expected_image_name)
                try:
                    shutil.copy(
                        source_image_path, os.path.join(TARGET_DIR, expected_image_name)
                    )
                    copied_image_count += 1
                    found_image_for_json = True
                    break  # Image found and copied, move to next JSON
                except Exception as e:
                    print(f"Error copying image '{expected_image_name}': {e}")
                    found_image_for_json = True  # Treat as found but failed to copy

        if not found_image_for_json:
            missing_image_details.append(json_filename)
            print(
                f"Warning: JSON '{json_filename}' was copied, but no corresponding image was found in the image directory."
            )

    print(f"\nProcess complete.")
    print(f"  - Copied {copied_json_count} JSON files.")
    print(f"  - Found and copied {copied_image_count} image files.")
    if missing_image_details:
        print(
            f"  - Note: Images for {len(missing_image_details)} JSON files were not found."
        )
        # print(f"    Missing images for: {', '.join(missing_image_details[:5])}..." # Print first few for brevity


if __name__ == "__main__":
    find_and_copy_relation_samples()
