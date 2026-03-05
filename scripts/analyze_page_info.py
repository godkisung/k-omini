import json
import os
import glob
from collections import defaultdict, Counter
import random
import shutil

# --- Configuration ---
SOURCE_JSON_DIR = "data"
SOURCE_IMAGE_DIR = "visualizations/visualized_samples"
SAMPLE_ISSUE_DIR = "reports/sample_issue"  # Directory to save samples
# Set to True to copy sample files for each special_issue. Set to False to disable.
COPY_SAMPLES = True
# --- End Configuration ---


# Fields to exclude from the distribution analysis
EXCLUDED_PAGE_INFO_FIELDS = ["image_path", "page_no", "height", "width"]


def analyze_page_info_distribution():
    """
    Analyzes the 'page_info' field across all JSON files, reports the distribution of values,
    and optionally copies a sample of 5 JSONs and their corresponding images for each
    'special_issue' type into a dedicated folder.
    """
    if not os.path.exists(SOURCE_JSON_DIR):
        print(f"Error: Source JSON directory '{SOURCE_JSON_DIR}' not found.")
        return

    if COPY_SAMPLES and not os.path.exists(SOURCE_IMAGE_DIR):
        print(
            f"Error: Source image directory '{SOURCE_IMAGE_DIR}' not found. Cannot copy image samples."
        )
        return

    json_files = glob.glob(os.path.join(SOURCE_JSON_DIR, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{SOURCE_JSON_DIR}'.")
        return

    print(f"Analyzing 'page_info' in {len(json_files)} JSON files...")

    # Structure: field_name -> value -> [filename1, filename2, ...]
    page_info_value_to_filenames = defaultdict(lambda: defaultdict(list))
    all_image_filenames = set(os.listdir(SOURCE_IMAGE_DIR)) if COPY_SAMPLES else set()

    if COPY_SAMPLES:
        if os.path.exists(SAMPLE_ISSUE_DIR):
            shutil.rmtree(SAMPLE_ISSUE_DIR)
            print(f"Removed existing sample directory: '{SAMPLE_ISSUE_DIR}'")
        os.makedirs(SAMPLE_ISSUE_DIR)
        print(f"Created sample directory: '{SAMPLE_ISSUE_DIR}'")

    for i, json_path in enumerate(json_files):
        json_filename = os.path.basename(json_path)
        if (i + 1) % 1000 == 0:
            print(f"  ... processed {i + 1}/{len(json_files)} files")

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            page_info = data.get("page_info")
            if not isinstance(page_info, dict):
                continue

            for key, value in page_info.items():
                if key in EXCLUDED_PAGE_INFO_FIELDS:
                    continue

                if key == "page_attribute" and isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        field_name = f"page_info.page_attribute.{sub_key}"
                        if sub_key == "special_issue" and isinstance(sub_value, list):
                            for item in sub_value:
                                page_info_value_to_filenames[field_name][
                                    str(item)
                                ].append(json_filename)
                        else:
                            page_info_value_to_filenames[field_name][
                                str(sub_value)
                            ].append(json_filename)
                else:
                    field_name = f"page_info.{key}"
                    page_info_value_to_filenames[field_name][str(value)].append(
                        json_filename
                    )

        except json.JSONDecodeError:
            print(f"Warning: Skipping invalid JSON file: {json_filename}")
        except Exception as e:
            print(f"An error occurred with {json_filename}: {e}")

    print("\n--- 'page_info' Value Distribution Report ---")
    if not page_info_value_to_filenames:
        print("No 'page_info' data was found or processed.")
        return

    for field, value_filenames_map in sorted(page_info_value_to_filenames.items()):
        print(f"\nField: `{field}`")
        print(f"  Total unique values: {len(value_filenames_map)}")

        distribution_counts = Counter(
            {value: len(filenames) for value, filenames in value_filenames_map.items()}
        )

        for value, count in distribution_counts.most_common():
            sample_filenames = random.choices(
                value_filenames_map[value], k=min(5, count)
            )
            print(
                f"    - `{value}`: {count} times (Random Samples: `{sample_filenames}`)"
            )

            # --- Copy Samples Logic ---
            if COPY_SAMPLES and field == "page_info.page_attribute.special_issue":
                issue_dir = os.path.join(SAMPLE_ISSUE_DIR, value)
                os.makedirs(issue_dir, exist_ok=True)

                print(
                    f"      -> Copying {len(sample_filenames)} samples to '{issue_dir}'..."
                )
                for sample_filename in sample_filenames:
                    # Copy JSON
                    source_json_path = os.path.join(SOURCE_JSON_DIR, sample_filename)
                    if os.path.exists(source_json_path):
                        shutil.copy(source_json_path, issue_dir)

                    # Copy corresponding image
                    base_filename_no_ext = os.path.splitext(sample_filename)[0]
                    found_image = False
                    for ext in [".jpg", ".png", ".jpeg"]:
                        expected_image_name = f"vis_{base_filename_no_ext}{ext}"
                        if expected_image_name in all_image_filenames:
                            source_image_path = os.path.join(
                                SOURCE_IMAGE_DIR, expected_image_name
                            )
                            if os.path.exists(source_image_path):
                                shutil.copy(source_image_path, issue_dir)
                                found_image = True
                                break
                    if not found_image:
                        print(
                            f"        - Warning: Image for '{sample_filename}' not found."
                        )


if __name__ == "__main__":
    analyze_page_info_distribution()
