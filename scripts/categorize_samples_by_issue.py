import json
import os
import glob
from collections import defaultdict

SOURCE_JSON_DIR = "data"
SOURCE_IMAGE_DIR = "visualizations/visualized_samples"
TARGET_BASE_DIR = "visualizations/visualized_samples_categorized"


def categorize_samples():
    """
    Categorizes JSON files and their corresponding images into subdirectories
    based on the 'special_issue' attribute in page_info.
    It uses symbolic links to avoid data duplication.
    """
    if not os.path.exists(SOURCE_JSON_DIR):
        print(f"Error: Source JSON directory '{SOURCE_JSON_DIR}' not found.")
        return
    if not os.path.exists(SOURCE_IMAGE_DIR):
        print(f"Error: Source image directory '{SOURCE_IMAGE_DIR}' not found.")
        return

    os.makedirs(TARGET_BASE_DIR, exist_ok=True)
    print(f"Base target directory '{TARGET_BASE_DIR}' created or already exists.")

    json_files = glob.glob(os.path.join(SOURCE_JSON_DIR, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{SOURCE_JSON_DIR}'.")
        return

    print(f"Analyzing {len(json_files)} files to categorize them by 'special_issue'...")

    linked_files_count = defaultdict(int)
    all_image_filenames = set(os.listdir(SOURCE_IMAGE_DIR))

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            special_issues = (
                data.get("page_info", {})
                .get("page_attribute", {})
                .get("special_issue", [])
            )

            if not isinstance(special_issues, list):
                special_issues = [str(special_issues)]  # Handle non-list cases

            if not special_issues:
                special_issues = ["None"]  # If empty, categorize as 'None'

            json_filename = os.path.basename(json_path)
            base_filename_no_ext = os.path.splitext(json_filename)[0]

            # Find the corresponding image file
            image_filename_to_link = None
            for ext in [".jpg", ".png", ".jpeg"]:
                expected_image_name = f"vis_{base_filename_no_ext}{ext}"
                if expected_image_name in all_image_filenames:
                    image_filename_to_link = expected_image_name
                    break

            # Create links in the appropriate category subdirectories
            for issue in special_issues:
                issue_dir = os.path.join(TARGET_BASE_DIR, issue)
                os.makedirs(issue_dir, exist_ok=True)

                # Get absolute paths for symlinking
                abs_json_path = os.path.abspath(json_path)

                # Create symlink for JSON
                link_json_path = os.path.join(issue_dir, json_filename)
                if not os.path.exists(link_json_path):
                    os.symlink(abs_json_path, link_json_path)
                    linked_files_count[issue] += 1

                # Create symlink for Image if it exists
                if image_filename_to_link:
                    abs_image_path = os.path.abspath(
                        os.path.join(SOURCE_IMAGE_DIR, image_filename_to_link)
                    )
                    link_image_path = os.path.join(issue_dir, image_filename_to_link)
                    if not os.path.exists(link_image_path):
                        os.symlink(abs_image_path, link_image_path)

        except Exception as e:
            print(f"Could not process file {json_filename}: {e}")

    print("\n--- Categorization Complete ---")
    for issue, count in linked_files_count.items():
        print(f"  - Linked {count} JSON files to category: '{issue}'")


if __name__ == "__main__":
    categorize_samples()
