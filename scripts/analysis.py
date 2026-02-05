import json
import os
import glob
from collections import defaultdict, Counter
import pandas as pd
import random
import shutil
import re
import numpy as np

from scripts.utils import is_empty_value, build_key_type_map, find_nested_key

# Define constants for report paths (can be overridden by function arguments)
DEFAULT_REPORT_MD_FILE = "reports/category_analysis_report.md"
DEFAULT_REPORT_XLSX_FILE = "reports/category_analysis_report.xlsx"
DEFAULT_REPORT_CSV_FILE = "reports/category_analysis.csv"

# Fields to exclude from the page_info distribution analysis
EXCLUDED_PAGE_INFO_FIELDS = ["image_path", "page_no", "height", "width"]


def _add_nested_keys_info(data_dict, prefix, keys_info_store, filename):
    """Recursively adds keys and their emptiness status from a nested dictionary."""
    if not isinstance(data_dict, dict):
        return

    for key, value in data_dict.items():
        full_key = f"{prefix}{key}"

        # Update keys_info_store
        keys_info_store[full_key]["encountered"] += 1
        if is_empty_value(value):
            keys_info_store[full_key]["empty_count"] += 1
        if (
            keys_info_store[full_key]["sample_filename"] is None
        ):  # Record first seen file
            keys_info_store[full_key]["sample_filename"] = filename

        # Recurse into dictionaries
        if isinstance(value, dict):
            _add_nested_keys_info(value, f"{full_key}.", keys_info_store, filename)


def _analyze_block(block, location, category_data, json_filename):
    """
    Recursively analyzes a block to extract structural information about its category_type.
    """
    if not isinstance(block, dict):
        return

    category_type = block.get("category_type")
    if category_type:
        info = category_data[category_type][location]
        info["count"] += 1  # Increment count for this (category_type, location)

        if len(info["sample_files"]) < 5:
            info["sample_files"].add(json_filename)

        # Record all keys present at this level, and handle nested dicts.
        for key, value in block.items():
            # Update keys_info for top-level keys
            keys_info = info["keys_info"][key]
            keys_info["encountered"] += 1
            if is_empty_value(value):
                keys_info["empty_count"] += 1
            if keys_info["sample_filename"] is None:
                keys_info["sample_filename"] = json_filename

            # Recurse into dictionaries for nested keys
            if isinstance(value, dict):
                _add_nested_keys_info(
                    value, f"{key}.", info["keys_info"], json_filename
                )

            # Check for non-empty merge_list and line_with_spans
            if key == "merge_list" and isinstance(value, list) and value:  # Non-empty list
                info["has_merge_list_non_empty"] = True
            if key == "line_with_spans" and isinstance(value, list) and value:  # Non-empty list
                info["has_line_with_spans_non_empty"] = True

    # Recurse into merge_list (if it's a non-empty list)
    if "merge_list" in block and isinstance(block["merge_list"], list) and block["merge_list"]:
        for sub_block in block["merge_list"]:
            _analyze_block(sub_block, "merge_list", category_data, json_filename)

    # Recurse into line_with_spans (if it's a non-empty list)
    if "line_with_spans" in block and isinstance(block["line_with_spans"], list) and block["line_with_spans"]:
        for span_block in block["line_with_spans"]:
            _analyze_block(span_block, "line_with_spans", category_data, json_filename)


def analyze_categories_func(
    source_json_dir="data",
    output_formats=["md", "xlsx"],
    report_md_file=DEFAULT_REPORT_MD_FILE,
    report_xlsx_file=DEFAULT_REPORT_XLSX_FILE,
    report_csv_file=DEFAULT_REPORT_CSV_FILE,
):
    """
    Analyzes all JSON annotation files to map category_types to their
    structural properties, and generates reports in specified formats (Markdown, Excel, CSV).
    """
    if not os.path.exists(source_json_dir):
        print(f"Error: Source JSON directory '{source_json_dir}' not found.")
        return

    json_files = glob.glob(os.path.join(source_json_dir, "*.json"))

    if not json_files:
        print(f"No JSON files found in '{source_json_dir}'.")
        return

    print(f"Analyzing {len(json_files)} files...")

    category_data = defaultdict(
        lambda: defaultdict(
            lambda: {
                "count": 0,
                "keys_info": defaultdict(
                    lambda: {
                        "encountered": 0,
                        "empty_count": 0,
                        "sample_filename": None,
                    }
                ),
                "has_merge_list_non_empty": False,
                "has_line_with_spans_non_empty": False,
                "sample_files": set(),
                "remarks": set(),
            }
        )
    )

    for i, json_path in enumerate(json_files):
        json_filename = os.path.basename(json_path)
        if (i + 1) % 1000 == 0:
            print(f"  ... processed {i + 1} files")

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            layout_dets = data.get("layout_dets", [])
            if not isinstance(layout_dets, list):
                continue

            for block in layout_dets:
                _analyze_block(block, "block", category_data, json_filename)

        except json.JSONDecodeError:
            print(f"Warning: Skipping invalid JSON file: {json_filename}")
        except Exception as e:
            print(f"An error occurred with {json_filename}: {e}")

    print(f"\n--- Analysis Complete ---")
    print(f"Post-processing keys and preparing reports...")

    final_category_data = defaultdict(
        lambda: defaultdict(
            lambda: {
                "count": 0,
                "associated_keys": {},
                "has_merge_list_non_empty": False,
                "has_line_with_spans_non_empty": False,
                "sample_files": set(),
                "remarks": set(),
            }
        )
    )

    for category, locations in category_data.items():
        for location, info in locations.items():
            final_info = final_category_data[category][location]
            final_info["count"] = info["count"]
            final_info["has_merge_list_non_empty"] = info["has_merge_list_non_empty"]
            final_info["has_line_with_spans_non_empty"] = info[
                "has_line_with_spans_non_empty"
            ]
            final_info["sample_files"] = info["sample_files"]

            for key, key_stats in info["keys_info"].items():
                if info["count"] > 0:
                    if key_stats["encountered"] == info["count"]:
                        final_info["associated_keys"][key] = key_stats[
                            "sample_filename"
                        ]
                        if key_stats["empty_count"] == info["count"]:
                            final_info["remarks"].add(
                                f"키 `{key}`는 항상 존재했지만, 모든 샘플에서 항상 비어있었습니다."
                            )
                    elif key_stats["encountered"] > 0:
                        final_info["remarks"].add(
                            f"키 `{key}`는 {info['count']}개 블록 중 {key_stats['encountered']}개에서만 발견되었습니다 (항상 존재하지 않음)."
                        )

    # Ensure reports directory exists
    os.makedirs("reports", exist_ok=True)

    # --- Generate Markdown Report ---
    if "md" in output_formats:
        print(f"Generating markdown report at '{report_md_file}'...")
        with open(report_md_file, "w", encoding="utf-8") as f:
            total_categories = len(final_category_data.keys())
            f.write(f"# Category Analysis Report\n\n")
            f.write(f"Found **{total_categories}** unique category types in total.\n\n")
            sorted_categories = sorted(final_category_data.keys())
            for category in sorted_categories:
                f.write(f"\n---\n\n")
                f.write(f"## Category: `{category}`\n\n")
                sorted_locations = sorted(final_category_data[category].keys())
                for location in sorted_locations:
                    info = final_category_data[category][location]
                    f.write(f"### Found in: `{location}`\n\n")
                    f.write(f"- **Count:** {info['count']}\n")
                    f.write(
                        f"- **Contains `merge_list` (non-empty):** {'Yes' if info['has_merge_list_non_empty'] else 'No'}\n"
                    )
                    f.write(
                        f"- **Contains `line_with_spans` (non-empty):** {'Yes' if info['has_line_with_spans_non_empty'] else 'No'}\n"
                    )
                    f.write(f"- **Sample Files:**\n")
                    if not info["sample_files"]:
                        f.write("  - (No samples found)\n")
                    else:
                        for sample in sorted(list(info["sample_files"])):
                            f.write(f"  - `{sample}`\n")
                    f.write(f"- **Associated Keys (always present):**\n")
                    if not info["associated_keys"]:
                        f.write(f"  - (항상 존재하는 키가 없거나 발견되지 않음)\n")
                    else:
                        sorted_keys = sorted(info["associated_keys"].keys())
                        for key in sorted_keys:
                            f.write(
                                f"  - **`{key}`** (sample from: `{info['associated_keys'][key]}`)\n"
                            )
                    f.write("\n")
                    if info["remarks"]:
                        f.write(f"- **Remarks:**\n")
                        for remark in sorted(list(info["remarks"])):
                            f.write(f"  - {remark}\n")
                        f.write("\n")

    # --- Prepare data for Excel and CSV ---
    excel_data = []
    key_types_data = []
    MAX_CELL_LENGTH = 32000  # Safe character limit for Excel cells

    # Build the comprehensive key type map using utils.build_key_type_map
    # Note: source_json_dir is expected to be a directory, so pass it as a list for build_key_type_map
    key_type_map = build_key_type_map([source_json_dir])

    # From the map, create sets to easily check for the presence of specific keys.
    has_merge_list = {
        (cat, ctx)
        for (cat, ctx, key), types in key_type_map.items()
        if "merge_list" in key
    } # Modified to check if 'merge_list' is part of the key path
    has_line_with_spans = {
        (cat, ctx)
        for (cat, ctx, key), types in key_type_map.items()
        if "line_with_spans" in key
    } # Modified to check if 'line_with_spans' is part of the key path


    for category, locations in final_category_data.items():
        for location, info in locations.items():
            associated_keys_list = sorted(list(info["associated_keys"].keys()))
            remarks_str = "; ".join(sorted(list(info["remarks"])))
            if len(remarks_str) > MAX_CELL_LENGTH:
                remarks_str = remarks_str[:MAX_CELL_LENGTH] + "... [TRUNCATED]"

            # RECALCULATE based on our full scan (from key_type_map)
            contains_merge_list_flag = "No"
            for (cat, ctx) in has_merge_list:
                if cat == category and ctx == location:
                    contains_merge_list_flag = "Yes"
                    break

            contains_line_with_spans_flag = "No"
            for (cat, ctx) in has_line_with_spans:
                if cat == category and ctx == location:
                    contains_line_with_spans_flag = "Yes"
                    break

            excel_data.append(
                {
                    "Category Name": category,
                    "Found In": location,
                    "Count": info["count"],
                    "Contains merge_list (non-empty)": contains_merge_list_flag,
                    "Contains line_with_spans (non-empty)": contains_line_with_spans_flag,
                    "Associated Keys (always present)": ", ".join(associated_keys_list),
                    "Number of Associated Keys": len(associated_keys_list),
                    "Remarks": remarks_str,
                }
            )

    for (cat, ctx, key), types in sorted(key_type_map.items()):
        key_types_data.append(
            {
                "Category Name": cat,
                "Found In": ctx,
                "Associated Key": key,
                "Data Types": ", ".join(sorted(list(types))),
            }
        )

    # --- Generate Excel Report ---
    if "xlsx" in output_formats:
        print(f"Generating Excel report at '{report_xlsx_file}'...")
        if os.path.exists(report_xlsx_file):
            os.remove(report_xlsx_file)
            print(f"Removed old report file: '{report_xlsx_file}'")

        if excel_data:
            df = pd.DataFrame(excel_data)
            df.sort_values(by=["Category Name", "Found In"], inplace=True)
            key_types_df = pd.DataFrame(key_types_data)

            try:
                with pd.ExcelWriter(report_xlsx_file, engine="openpyxl") as writer:
                    df.to_excel(writer, sheet_name="Category Report", index=False)
                    key_types_df.to_excel(writer, sheet_name="Associated Key Types", index=False)
                print(f"Successfully generated Excel report: '{report_xlsx_file}'")
            except Exception as e:
                print(f"Error writing to Excel file: {e}")
                print(
                    "Please ensure you have 'openpyxl' installed (`pip install openpyxl`)."
                )
        else:
            print("No data to write to Excel report.")

    # --- Generate CSV Report ---
    if "csv" in output_formats:
        print(f"Generating CSV report at '{report_csv_file}'...")
        if excel_data:
            # Re-use the DataFrame prepared for Excel for CSV generation
            df_csv = pd.DataFrame(excel_data)
            # For CSV, we need to flatten the "Associated Keys" and "Remarks" for proper CSV structure
            # associated_keys_list and remarks_str are already prepared in excel_data
            df_csv.rename(columns={
                "Associated Keys (always present)": "Associated Keys",
                "Contains merge_list (non-empty)": "Contains merge_list",
                "Contains line_with_spans (non-empty)": "Contains line_with_spans",
            }, inplace=True)

            try:
                df_csv.to_csv(report_csv_file, index=False, encoding="utf-8")
                print(f"Successfully generated CSV report: '{report_csv_file}'")
            except Exception as e:
                print(f"Error writing to CSV file: {e}")
        else:
            print("No data to write to CSV report.")

    print("Done.")


def analyze_key_distributions_func(
    source_json_dir="data",
    target_root_field="layout_dets",  # Can be 'layout_dets' or 'extra'
    target_key_paths=None,  # List of lists, e.g., [['attribute', 'include_equation']]
    category_type_filter=None,  # Only for layout_dets, e.g., 'table_mask'
):
    """
    Analyzes the distribution of values for specified keys within JSON files.
    Can target 'layout_dets' or 'extra' root fields, and filter by category_type.
    """
    if not os.path.exists(source_json_dir):
        print(f"Error: Source JSON directory '{source_json_dir}' not found.")
        return

    json_files = glob.glob(os.path.join(source_json_dir, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{source_json_dir}'.")
        return

    print(
        f"Searching for keys in '{target_root_field}' across {len(json_files)} JSON files..."
    )
    if target_root_field == "layout_dets" and category_type_filter:
        print(f"  Filtering by category_type='{category_type_filter}'")
    print()

    all_keys_distributions = defaultdict(lambda: defaultdict(list)) # {key_path_str: {value: [filename1, filename2]}}

    for i, json_path in enumerate(json_files):
        json_filename = os.path.basename(json_path)
        if (i + 1) % 1000 == 0:
            print(f"  ... processed {i + 1}/{len(json_files)} files")

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if target_root_field == "layout_dets":
                blocks = data.get("layout_dets", [])
                if isinstance(blocks, list):
                    for block in blocks:
                        if isinstance(block, dict):
                            block_category_type = block.get("category_type")
                            if category_type_filter and block_category_type != category_type_filter:
                                continue

                            # If target_key_paths is empty, it means we want the category_type itself (default behavior)
                            if not target_key_paths:
                                key_path_str = "category_type"
                                found_value = block_category_type
                                if found_value is not None:
                                    all_keys_distributions[key_path_str][str(found_value)].append(json_filename)
                            else:
                                for target_key_path in target_key_paths:
                                    key_path_str = ".".join(target_key_path)
                                    found_value = find_nested_key(block, target_key_path)
                                    if found_value is not None:
                                        # Handle list values (like 'relation') by iterating through them
                                        if isinstance(found_value, list):
                                            if not found_value: # Empty list
                                                all_keys_distributions[key_path_str]["[]"].append(json_filename)
                                            else:
                                                for item in found_value:
                                                    all_keys_distributions[key_path_str][str(item)].append(json_filename)
                                        else: # For non-list values
                                            if isinstance(found_value, dict): # Convert dict to string for counting
                                                found_value = str(found_value)
                                            all_keys_distributions[key_path_str][str(found_value)].append(json_filename)

            elif target_root_field == "extra":
                search_root = data.get("extra")
                if isinstance(search_root, dict):
                    # If target_key_paths is empty, it means we want to analyze the top-level keys of 'extra'
                    if not target_key_paths:
                        for key, value in search_root.items():
                            key_path_str = key
                            all_keys_distributions[key_path_str][str(value)].append(json_filename)
                    else:
                        for target_key_path in target_key_paths:
                            key_path_str = ".".join(target_key_path)
                            found_values = find_nested_key(search_root, target_key_path)

                            if found_values is not None:
                                if isinstance(found_values, list):
                                    for val in found_values:
                                        all_keys_distributions[key_path_str][str(val)].append(json_filename)
                                else:
                                    all_keys_distributions[key_path_str][str(found_values)].append(json_filename)

        except json.JSONDecodeError:
            print(f"Warning: Skipping invalid JSON file: {json_filename}")
        except Exception as e:
            print(f"An error occurred with {json_filename}: {e}")

    print(f"\n--- Search Complete: Value Distribution Report ---")
    if all_keys_distributions:
        for key_path_str, values_map in sorted(all_keys_distributions.items()):
            print(f"\nKey: `{key_path_str}`")
            print(f"  Total unique values: {len(values_map)}")
            print("  Value distribution:")

            sorted_values_with_counts = sorted(
                [(value, filenames) for value, filenames in values_map.items()],
                key=lambda x: len(x[1]),
                reverse=True,
            )

            for value, filenames in sorted_values_with_counts:
                count = len(filenames)
                sample_filename = random.choice(filenames)
                print(
                    f"    - '{value}': {count} times (Example file: {sample_filename})"
                )
    else:
        print(f"  No target keys found for the specified criteria.")


def _get_bounding_box(poly):
    """Gets the min/max x/y coordinates (bounding box) from a polygon."""
    # Assuming poly is a flat list [x1, y1, x2, y2, ...]
    if not poly or not isinstance(poly, list) or len(poly) % 2 != 0:
        return [0, 0, 0, 0] # Return empty/invalid bbox

    x_coords = poly[0::2]
    y_coords = poly[1::2]
    
    if not x_coords or not y_coords:
        return [0, 0, 0, 0]

    return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]


def _get_page_number_from_filename(filename):
    """Extracts page number from filenames like '..._page_XXX.json'"""
    match = re.search(r"_page_(\d+)\.json$", filename)
    return int(match.group(1)) if match else None


def analyze_relations_func(
    source_json_dir="data",
    relation_types=["parent_son", "truncated"],
    output_detail="summary",  # 'summary' or 'examples'
    max_examples_per_type=10,
):
    """
    Analyzes 'parent_son' and 'truncated' relations in JSON files.
    Can output a summary of relation patterns or detailed examples.
    """
    if not os.path.exists(source_json_dir):
        print(f"Error: Source JSON directory '{source_json_dir}' not found.")
        return

    json_files = glob.glob(os.path.join(source_json_dir, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{source_json_dir}'.")
        return

    print(f"Analyzing {len(json_files)} files for relations: {relation_types}...\n")

    parent_son_patterns = defaultdict(lambda: {"count": 0, "files": []})
    truncated_patterns = defaultdict(lambda: {"count": 0, "files": []})
    
    # For 'truncate' specific analysis
    truncated_category_pairs_counts = Counter()
    total_truncated_relations = 0

    files_with_examples = defaultdict(lambda: defaultdict(list)) # {relation_type: {filename: [relation_details]}}

    for i, json_path in enumerate(json_files):
        filename = os.path.basename(json_path)
        if (i + 1) % 1000 == 0:
            print(f"  ... processed {i + 1} files")

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            layout_dets = data.get("layout_dets", [])
            relations = data.get("extra", {}).get("relation", [])

            if not layout_dets or not relations:
                continue

            anno_id_to_block_map = {
                block.get("anno_id"): block for block in layout_dets
            }

            for rel in relations:
                rel_type = rel.get("relation_type")
                if rel_type not in relation_types:
                    continue

                source_anno_id = rel.get("source_anno_id")
                target_anno_id = rel.get("target_anno_id")

                block1 = anno_id_to_block_map.get(source_anno_id)
                block2 = anno_id_to_block_map.get(target_anno_id)

                if block1 is None or block2 is None:
                    continue

                cat1 = block1.get("category_type", "N/A")
                cat2 = block2.get("category_type", "N/A")

                pattern = (cat1, cat2)

                if rel_type == "parent_son":
                    parent_son_patterns[pattern]["count"] += 1
                    if filename not in parent_son_patterns[pattern]["files"]:
                        parent_son_patterns[pattern]["files"].append(filename)
                elif rel_type == "truncated":
                    truncated_patterns[pattern]["count"] += 1
                    if filename not in truncated_patterns[pattern]["files"]:
                        truncated_patterns[pattern]["files"].append(filename)
                    
                    truncated_category_pairs_counts[pattern] += 1
                    total_truncated_relations += 1

                if output_detail == "examples":
                    files_with_examples[rel_type][filename].append(
                        {
                            "relation": rel,
                            "block1": block1,
                            "block2": block2,
                            "cat1": cat1,
                            "cat2": cat2,
                        }
                    )

        except Exception as e:
            print(f"Error processing file {filename}: {e}")

    # --- Output Results ---
    if output_detail == "summary":
        print(f"\n{'='*20} Summary for: parent_son {'='*20}")
        if not parent_son_patterns:
            print("No 'parent_son' relations found.")
        else:
            print(
                f"Found {len(parent_son_patterns)} unique (Parent, Son) category patterns:"
            )
            sorted_ps_patterns = sorted(
                parent_son_patterns.items(), key=lambda item: item[1]["count"], reverse=True
            )
            for (p_cat, s_cat), data in sorted_ps_patterns:
                example_file = data["files"][0] if data["files"] else "N/A"
                print(
                    f"  - ('{p_cat}', '{s_cat}'): {data['count']} times (e.g., in '{example_file}')"
                )

        print(f"\n{'='*20} Summary for: truncated {'='*20}")
        if not truncated_patterns:
            print("No 'truncated' relations found.")
        else:
            print(
                f"Found {len(truncated_patterns)} unique (Block1, Block2) category patterns:"
            )
            sorted_tr_patterns = sorted(
                truncated_patterns.items(), key=lambda item: item[1]["count"], reverse=True
            )
            for (b1_cat, b2_cat), data in sorted_tr_patterns:
                example_file = data["files"][0] if data["files"] else "N/A"
                print(
                    f"  - ('{b1_cat}', '{b2_cat}'): {data['count']} times (e.g., in '{example_file}')"
                )
        
        # Specific Truncated Relations Summary
        print(f"\n{'='*20} Specific Truncated Relations Summary {'='*20}")
        if not truncated_category_pairs_counts:
            print("No 'truncated' relations found.")
        else:
            print(f"Total 'truncated' relations found: {total_truncated_relations}")
            print(f"Unique (Block1, Block2) category patterns found: {len(truncated_category_pairs_counts)}\n")
            for pattern, count in truncated_category_pairs_counts.most_common():
                print(f"  - {pattern}: {count} times")


    elif output_detail == "examples":
        for rel_type in relation_types:
            print(f"\n{'='*20} Examples for: {rel_type} {'='*20}")
            files_to_process = list(files_with_examples[rel_type].keys())[:max_examples_per_type]

            if not files_to_process:
                print("No examples found.")
                continue

            for file_idx, filename in enumerate(files_to_process):
                print(
                    f"\n--- Example {file_idx+1}/{len(files_to_process)} from File: {filename} ---"
                )
                relations_in_file = files_with_examples[rel_type][filename]

                for rel_details in relations_in_file:
                    rel = rel_details["relation"]
                    block1 = rel_details["block1"]
                    block2 = rel_details["block2"]
                    cat1 = rel_details["cat1"]
                    cat2 = rel_details["cat2"]

                    text1_preview = block1.get("text", "").replace("\n", " ")[:100] + ("..." if len(block1.get("text", "")) > 100 else "")
                    text2_preview = block2.get("text", "").replace("\n", " ")[:100] + ("..." if len(block2.get("text", "")) > 100 else "")

                    bbox1 = _get_bounding_box(block1.get("poly"))
                    bbox2 = _get_bounding_box(block2.get("poly"))

                    print(
                        f"\n  Relation: anno_id {rel.get('source_anno_id')} -> anno_id {rel.get('target_anno_id')}"
                    )
                    print(
                        f"    Block 1 (Source): '{cat1}' | BBox: [{bbox1[0]:.0f}, {bbox1[1]:.0f}, {bbox1[2]:.0f}, {bbox1[3]:.0f}]"
                    )
                    print(f'      - Text: "{text1_preview}"')
                    print(
                        f"    Block 2 (Target): '{cat2}' | BBox: [{bbox2[0]:.0f}, {bbox2[1]:.0f}, {bbox2[2]:.0f}, {bbox2[3]:.0f}]"
                    )
                    print(f'      - Text: "{text2_preview}"')

                    if rel_type == "parent_son":
                        contains = (
                            bbox1[0] <= bbox2[0]
                            and bbox1[1] <= bbox2[1]
                            and bbox1[2] >= bbox2[2]
                            and bbox1[3] >= bbox2[3]
                        )
                        center1 = ((bbox1[0] + bbox1[2]) / 2, (bbox1[1] + bbox1[3]) / 2)
                        center2 = ((bbox2[0] + bbox2[2]) / 2, (bbox2[1] + bbox2[3]) / 2)
                        dist = np.linalg.norm(np.array(center1) - np.array(center2))
                        print(
                            f"    -> Analysis: BBox1 contains BBox2: {contains}. Distance between centers: {dist:.2f}"
                        )

                    if rel_type == "truncated":
                        page1 = _get_page_number_from_filename(filename)
                        print(
                            f"    -> Analysis: Text appears to be sequential. Occurs on page {page1 if page1 else 'N/A'}."
                        )
    print("\nRelation analysis complete.")


def analyze_page_info_func(
    source_json_dir="data",
    copy_samples=False,
    sample_issue_dir="reports/sample_issue",
    source_image_dir="visualizations/visualized_samples",
    num_samples_to_copy=5,
):
    """
    Analyzes the 'page_info' field across all JSON files, reports the distribution of values,
    and optionally copies a sample of JSONs and their corresponding images for each
    'special_issue' type into a dedicated folder.
    """
    if not os.path.exists(source_json_dir):
        print(f"Error: Source JSON directory '{source_json_dir}' not found.")
        return

    if copy_samples and not os.path.exists(source_image_dir):
        print(
            f"Error: Source image directory '{source_image_dir}' not found. Cannot copy image samples."
        )
        return

    json_files = glob.glob(os.path.join(source_json_dir, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{source_json_dir}'.")
        return

    print(f"Analyzing 'page_info' in {len(json_files)} JSON files...")

    # Structure: field_name -> value -> [filename1, filename2, ...]
    page_info_value_to_filenames = defaultdict(lambda: defaultdict(list))
    all_image_filenames = set(os.listdir(source_image_dir)) if copy_samples else set()

    if copy_samples:
        if os.path.exists(sample_issue_dir):
            shutil.rmtree(sample_issue_dir)
            print(f"Removed existing sample directory: '{sample_issue_dir}'")
        os.makedirs(sample_issue_dir)
        print(f"Created sample directory: '{sample_issue_dir}'")

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
                value_filenames_map[value], k=min(num_samples_to_copy, count)
            )
            print(
                f"    - `{value}`: {count} times (Random Samples: `{sample_filenames}`)"
            )

            # --- Copy Samples Logic ---
            if copy_samples and field == "page_info.page_attribute.special_issue":
                issue_dir = os.path.join(sample_issue_dir, value)
                os.makedirs(issue_dir, exist_ok=True)

                print(
                    f"      -> Copying {len(sample_filenames)} samples to '{issue_dir}'..."
                )
                for sample_filename in sample_filenames:
                    # Copy JSON
                    source_json_path = os.path.join(source_json_dir, sample_filename)
                    if os.path.exists(source_json_path):
                        shutil.copy(source_json_path, issue_dir)

                    # Copy corresponding image
                    base_filename_no_ext = os.path.splitext(sample_filename)[0]
                    found_image = False
                    for ext in [".jpg", ".png", ".jpeg"]:
                        expected_image_name = f"vis_{base_filename_no_ext}{ext}"
                        if expected_image_name in all_image_filenames:
                            source_image_path = os.path.join(
                                source_image_dir, expected_image_name
                            )
                            if os.path.exists(source_image_path):
                                shutil.copy(source_image_path, issue_dir)
                                found_image = True
                                break
                    if not found_image:
                        print(
                            f"        - Warning: Image for '{sample_filename}' not found."
                        )


def analyze_merge_list_sources_func(
    source_json_dir="data",
):
    """
    Analyzes all JSON files in the source directories to find which data_sources
    use the 'merge_list' key.
    """
    if not os.path.exists(source_json_dir):
        print(f"Error: Source JSON directory '{source_json_dir}' not found.")
        return

    json_files = glob.glob(os.path.join(source_json_dir, "*.json"))
    if not json_files:
        print(f"No JSON files found in '{source_json_dir}'.")
        return

    print(f"Analyzing {len(json_files)} files to check for 'merge_list' usage...\n")

    data_source_counts = Counter()

    for i, json_path in enumerate(json_files):
        if (i + 1) % 1000 == 0:
            print(f"  ... processed {i + 1} files")
        
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check in layout_dets
            if "layout_dets" in data and isinstance(data["layout_dets"], list):
                for anno in data["layout_dets"]:
                    if isinstance(anno, dict):
                        if "merge_list" in anno and anno["merge_list"]:
                            data_source = (
                                data.get("page_info", {})
                                .get("page_attribute", {})
                                .get("data_source")
                            )
                            if data_source:
                                data_source_counts[data_source] += 1
                                break # Found merge_list, move to next file
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
            # Ignore files that are malformed or don't have the expected structure
            continue

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
    print("\nMerge list source analysis complete.")


if __name__ == "__main__":
    # Example usage if run directly (for testing purposes)
    # This will run the category analysis and generate all reports
    # analyze_categories_func(source_json_dir="data", output_formats=["md", "xlsx", "csv"])

    # Example for analyze_key_distributions_func
    # analyze_key_distributions_func(
    #     source_json_dir="data/sample/split_annotations",
    #     target_root_field="extra",
    #     target_key_paths=[["relation", "relation_type"]]
    # )

    # analyze_key_distributions_func(
    #     source_json_dir="data/sample/split_annotations",
    #     target_root_field="layout_dets",
    #     target_key_paths=[
    #         ["attribute", "with_span"],
    #         ["attribute", "table_layout"],
    #         ["attribute", "line"],
    #         ["attribute", "language"],
    #         ["attribute", "include_background"],
    #         ["attribute", "include_photo"],
    #         ["attribute", "include_equation"],
    #     ],
    #     category_type_filter="table_mask",
    # )

    # Example for analyze_relations_func - summary
    # analyze_relations_func(
    #     source_json_dir="data/sample/split_annotations",
    #     relation_types=["parent_son", "truncated"],
    #     output_detail="summary"
    # )

    # Example for analyze_relations_func - examples
    # analyze_relations_func(
    #     source_json_dir="data/sample/split_annotations",
    #     relation_types=["parent_son"],
    #     output_detail="examples",
    #     max_examples_per_type=3
    # )

    # Example for analyze_page_info_func
    # analyze_page_info_func(
    #     source_json_dir="data/sample/split_annotations",
    #     copy_samples=False,
    #     # sample_issue_dir="reports/sample_issue", # Default value is fine
    #     # source_image_dir="visualizations/visualized_samples", # Default value is fine
    #     num_samples_to_copy=2,
    # )

    # Example for analyze_merge_list_sources_func
    analyze_merge_list_sources_func(
        source_json_dir="data/sample/split_annotations",
    )
