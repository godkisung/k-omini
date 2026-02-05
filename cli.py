import argparse
import os
import sys

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from scripts.analysis import analyze_categories_func, analyze_key_distributions_func, analyze_relations_func
from scripts.data_utils import split_annotations

def main():
    parser = argparse.ArgumentParser(description="K-Omnidoc Benchmark CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- Analyze Subcommand ---
    analyze_parser = subparsers.add_parser("analyze", help="Analyze K-Omnidoc data")
    analyze_subparsers = analyze_parser.add_subparsers(dest="analyze_subcommand", help="Analysis subcommands")

    # Analyze Categories
    categories_parser = analyze_subparsers.add_parser(
        "categories", help="Analyze category types and their structural properties"
    )
    categories_parser.add_argument(
        "--source-json-dir",
        type=str,
        default="data",
        help="Directory containing source JSON files (default: data)",
    )
    categories_parser.add_argument(
        "--output-formats",
        nargs="+",
        default=["md", "xlsx"],
        choices=["md", "xlsx", "csv"],
        help="Report output formats (default: md xlsx)",
    )
    categories_parser.add_argument(
        "--report-md-file",
        type=str,
        default="reports/category_analysis_report.md",
        help="Path for the Markdown report file",
    )
    categories_parser.add_argument(
        "--report-xlsx-file",
        type=str,
        default="reports/category_analysis_report.xlsx",
        help="Path for the Excel report file",
    )
    categories_parser.add_argument(
        "--report-csv-file",
        type=str,
        default="reports/category_analysis.csv",
        help="Path for the CSV report file",
    )

    # Analyze Key Distributions
    key_distributions_parser = analyze_subparsers.add_parser(
        "key-distributions", help="Analyze value distributions of specific keys"
    )
    key_distributions_parser.add_argument(
        "--source-json-dir",
        type=str,
        default="data",
        help="Directory containing source JSON files (default: data)",
    )
    key_distributions_parser.add_argument(
        "--target-root-field",
        type=str,
        choices=["layout_dets", "extra"],
        default="layout_dets",
        help="Root field to search within (choices: layout_dets, extra; default: layout_dets)",
    )
    key_distributions_parser.add_argument(
        "--target-key-paths",
        nargs="+",
        action="append",
        metavar="KEY_PATH",
        help=(
            "List of key paths to analyze, e.g., 'attribute.include_equation' "
            "or 'relation.relation_type'. For nested keys, separate with dots. "
            "Can be specified multiple times for multiple paths. "
            "Example: --target-key-paths attribute.include_equation --target-key-paths category_type"
        ),
    )
    key_distributions_parser.add_argument(
        "--category-type-filter",
        type=str,
        help="Optional: Filter by 'category_type' (only applicable for 'layout_dets' target_root_field)",
    )

    # Analyze Relations
    relations_parser = analyze_subparsers.add_parser(
        "relations", help="Analyze relations (parent_son, truncated) within annotations"
    )
    relations_parser.add_argument(
        "--source-json-dir",
        type=str,
        default="data",
        help="Directory containing source JSON files (default: data)",
    )
    relations_parser.add_argument(
        "--relation-types",
        nargs="+",
        default=["parent_son", "truncated"],
        choices=["parent_son", "truncated"],
        help="List of relation types to analyze (default: parent_son truncated)",
    )
    relations_parser.add_argument(
        "--output-detail",
        type=str,
        default="summary",
        choices=["summary", "examples"],
        help="Level of detail for output (choices: summary, examples; default: summary)",
    )
    relations_parser.add_argument(
        "--max-examples-per-type",
        type=int,
        default=10,
        help="Maximum number of examples to show per relation type if output-detail is 'examples' (default: 10)",
    )


    # --- Data Subcommand ---
    data_parser = subparsers.add_parser("data", help="Data utility commands")
    data_subparsers = data_parser.add_subparsers(dest="data_subcommand", help="Data utility subcommands")

    # Data Split JSON
    split_json_parser = data_subparsers.add_parser(
        "split-json", help="Split a large JSON annotation file into individual files"
    )
    split_json_parser.add_argument(
        "--input-json-file",
        type=str,
        required=True,
        help="Path to the input JSON file containing a list of annotations",
    )
    split_json_parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Directory to save the individual JSON files",
    )


    args = parser.parse_args()

    # Pre-process target_key_paths for analyze_key_distributions_func
    # This block needs to be carefully handled as `action='append'` creates a list of lists.
    # We want to flatten it to a list of strings, then split by '.'
    if hasattr(args, "target_key_paths") and args.target_key_paths:
        # Check if target_key_paths is not empty and is a list of lists (from action='append')
        if args.target_key_paths and isinstance(args.target_key_paths[0], list):
            flattened_key_paths = [item for sublist in args.target_key_paths for item in sublist]
            processed_key_paths = [path_str.split('.') for path_str in flattened_key_paths]
            args.target_key_paths = processed_key_paths
        else: # Handle cases where it might be a single string or already flattened
            args.target_key_paths = [path_str.split('.') for path_str in args.target_key_paths]
    else:
        # Default for key-distributions if not specified: analyze category_type in layout_dets
        # Only set default if key-distributions subcommand is actually chosen
        if args.command == "analyze" and args.analyze_subcommand == "key-distributions":
            if args.target_root_field == "layout_dets":
                args.target_key_paths = [["category_type"]]
            elif args.target_root_field == "extra":
                # For 'extra' with no specific key path, treat as asking for top-level keys
                args.target_key_paths = [] 


    if args.command == "analyze":
        if args.analyze_subcommand == "categories":
            print(f"Running category analysis...")
            analyze_categories_func(
                source_json_dir=args.source_json_dir,
                output_formats=args.output_formats,
                report_md_file=args.report_md_file,
                report_xlsx_file=args.report_xlsx_file,
                report_csv_file=args.report_csv_file,
            )
        elif args.analyze_subcommand == "key-distributions":
            print(f"Running key distribution analysis...")
            analyze_key_distributions_func(
                source_json_dir=args.source_json_dir,
                target_root_field=args.target_root_field,
                target_key_paths=args.target_key_paths,
                category_type_filter=args.category_type_filter,
            )
        elif args.analyze_subcommand == "relations":
            print(f"Running relation analysis...")
            analyze_relations_func(
                source_json_dir=args.source_json_dir,
                relation_types=args.relation_types,
                output_detail=args.output_detail,
                max_examples_per_type=args.max_examples_per_type,
            )
        else:
            analyze_parser.print_help()
    elif args.command == "data":
        if args.data_subcommand == "split-json":
            print(f"Splitting JSON file: {args.input_json_file} into {args.output_dir}...")
            split_annotations(
                json_path=args.input_json_file,
                output_dir=args.output_dir,
            )
        else:
            data_parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()