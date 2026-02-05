import os
import json
from collections import Counter
import concurrent.futures


def check_for_merge_list(annotation_list):
    """Recursively checks for a non-empty merge_list in a list of annotations."""
    for anno in annotation_list:
        if isinstance(anno, dict):
            if "merge_list" in anno and anno["merge_list"]:
                return True
            # Recursively check in other potential nested lists if needed,
            # but for now, merge_list is the main one.
    return False


def process_file(file_path):
    """
    Processes a single JSON file to check for merge_lists and return the data_source if found.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check in layout_dets
        if "layout_dets" in data and isinstance(data["layout_dets"], list):
            if check_for_merge_list(data["layout_dets"]):
                data_source = (
                    data.get("page_info", {})
                    .get("page_attribute", {})
                    .get("data_source")
                )
                if data_source:
                    return data_source
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
        # Ignore files that are malformed or don't have the expected structure
        return None
    return None


def analyze_sources(source_dirs):
    """
    Analyzes all JSON files in the source directories to find which data_sources
    use the 'merge_list' key.
    """
    all_files = []
    for source_dir in source_dirs:
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith(".json"):
                    all_files.append(os.path.join(root, file))

    print(f"Found {len(all_files)} total JSON files to analyze...")

    data_source_counts = Counter()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Map the process_file function to all file paths
        results = executor.map(process_file, all_files)

        # Process results as they complete
        for data_source in results:
            if data_source:
                data_source_counts[data_source] += 1

    print("\n--- Merge_list 사용 현황 분석 결과 ---")
    if not data_source_counts:
        print("분석된 파일에서 'merge_list'를 사용하는 문서를 찾지 못했습니다.")
        return

    total_files_with_merges = sum(data_source_counts.values())
    print(f"총 {total_files_with_merges}개의 파일에서 'merge_list'가 사용되었습니다.\n")

    # Sort by count descending
    sorted_counts = data_source_counts.most_common()

    print("문서 종류별 'merge_list' 사용 빈도:")
    for source, count in sorted_counts:
        percentage = (count / total_files_with_merges) * 100
        print(f"- {source}: {count}개 파일 ({percentage:.1f}%)")


if __name__ == "__main__":
    SOURCE_DIRS = ["data"]
    analyze_sources(SOURCE_DIRS)
