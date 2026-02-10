import os
import glob
import json
from src.config import get_config, DATA_DIR
from src.core.models import Document
from src.analysis.validator import Validator, Severity

def run_validation():
    """Main function to run validation on all JSON files using the new modular system."""
    
    # Setup
    config = get_config()
    validator = Validator(config)
    
    # Use DATA_DIR from config or override if needed
    # The original script used 'data/sample/split_annotations', let's stick to config.DATA_DIR 
    # or allow arguments. For now, let's use the project standard DATA_DIR but print it.
    target_dir = DATA_DIR
    
    print(f"--- Starting validation using src.analysis.validator ---")
    print(f"Target Directory: {target_dir}")
    
    json_paths = glob.glob(os.path.join(target_dir, '*.json'))
    total_files = len(json_paths)
    files_with_issues = 0
    total_issues = 0

    if total_files == 0:
        print(f"No JSON files found in '{target_dir}'.")
        # Fallback to local 'data' if standard dir is empty? 
        # But for refactoring, we should stick to the standard.
        return

    for i, path in enumerate(json_paths):
        filename = os.path.basename(path)
        try:
            doc = Document.from_json(path)
        except Exception as e:
            print(f"--- ISSUES FOUND in {filename} ---")
            print(f"  - [FATAL] Could not parse JSON file: {e}")
            files_with_issues += 1
            total_issues += 1
            continue

        file_issues = []
        
        for ann in doc.layout_dets:
            results = validator.validate_annotation(ann)
            # Filter for Warning/Error
            meaningful_issues = [r for r in results if r.severity in [Severity.ERROR, Severity.WARNING]]
            
            if meaningful_issues:
                file_issues.append((ann.anno_id, meaningful_issues))
        
        if file_issues:
            files_with_issues += 1
            print(f"--- ISSUES FOUND in {filename} ---")
            for anno_id, issues in file_issues:
                total_issues += len(issues)
                print(f"  - Annotation ID: {anno_id}")
                for issue in issues:
                    print(f"    - [{issue.severity.name}] {issue.message}")
            print("-" * (len(filename) + 20) + "\n")

    print("--- Validation Summary ---")
    print(f"Total files checked: {total_files}")
    print(f"Files with issues: {files_with_issues}")
    print(f"Total issues found: {total_issues}")
    print("--------------------------")

if __name__ == "__main__":
    run_validation()
