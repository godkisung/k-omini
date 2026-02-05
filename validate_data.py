import os
import glob
import json
from functools import reduce
import re

# --- Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
# The user wants to validate the JSON files in this specific directory
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'sample', 'split_annotations')

# --- Validation Constants ---
BASE_KEYS = ['anno_id', 'category_type', 'ignore', 'order', 'poly']
REQUIRED_KEYS = {
    'text_group': BASE_KEYS + ['text', 'attribute.text_language', 'attribute.text_rotate'],
    'equation_isolated': BASE_KEYS + ['latex', 'attribute.equation_language', 'attribute.formula_type'],
    'table': BASE_KEYS + ['html', 'table_edit_status'],
    'figure': BASE_KEYS + ['attribute.contains_elements', 'sub_regions'],
    'chart': BASE_KEYS + ['html', 'attribute.chart_type', 'attribute.language', 'attribute.chart_level', 'attribute.is_indexed'],
    'mask_group': BASE_KEYS,
}
VALID_PARENT_SON_PAIRS = {
    'Figure': ['figure_caption', 'figure_footnote', 'text_block', 'figure', 'table', 'equation_isolated'],
    'Table': ['table_caption', 'table_footnote', 'text_block', 'figure', 'table', 'equation_isolated'],
    'Equation': ['eq_caption', 'explanation', 'text_block'],
}
SEMANTIC_KEYWORDS = {
    "title": ["references", "appendix", "abstract", "acknowledgements", "bibliography"]
}

# --- Validation Functions ---

def get_prop(obj, path):
    """Safely get a nested property from an object."""
    try:
        return reduce(lambda d, key: d.get(key) if isinstance(d, dict) else None, path.split('.'), obj)
    except TypeError:
        return None

def check_required_keys(ann):
    """Checks if an annotation has all its required keys based on its category."""
    category = ann.get('category_type', '')
    key_group = 'mask_group'
    if category in ['table', 'figure', 'chart', 'equation_isolated']:
        key_group = category
    elif 'text' in category or any(t in category for t in ['title', 'caption', 'footnote', 'header', 'footer', 'reference']):
        key_group = 'text_group'
    
    required = REQUIRED_KEYS.get(key_group, [])
    missing = [key for key in required if get_prop(ann, key) is None]
    if missing:
        yield f"[ERROR] Missing required key(s): {', '.join(missing)}"

def validate_language(ann):
    """Validates if the text content matches the declared language."""
    lang = get_prop(ann, 'attribute.text_language')
    text = ann.get('text')
    if not lang or not text:
        return
    
    has_han = bool(re.search("[一-鿿]", text))
    if 'han' in lang and not has_han:
        yield "[WARNING] Language mismatch: Declared 'Han' but no Han characters found."
    if 'english' in lang and has_han:
        yield "[WARNING] Language mismatch: Declared 'English' but Han characters found."

def validate_parent_son(ann, full_data, layout_dets_map):
    """Validates parent-son relationships for suspicious pairings."""
    ann_id, ann_cat = ann.get('anno_id'), ann.get('category_type')
    if not ann_id or not ann_cat: return

    all_relations = get_prop(full_data, 'extra.relation') or []
    parent_relations = [rel for rel in all_relations if rel.get('source_anno_id') == ann_id and rel.get('relation_type') == 'parent_son']
    
    for rel in parent_relations:
        child_ann = layout_dets_map.get(rel.get('target_anno_id'))
        if child_ann and child_ann.get('category_type') not in VALID_PARENT_SON_PAIRS.get(ann_cat, []):
            yield f"[WARNING] Suspicious relation: '{ann_cat}' is parent to '{child_ann.get('category_type')}'."

def validate_chart(ann):
    """Validates chart-specific attributes."""
    if ann.get('category_type') != 'chart': return
    if get_prop(ann, 'attribute.is_indexed') is None:
        yield "[WARNING] Missing chart-specific attribute 'is_indexed'."

def validate_semantic_mismatch(ann):
    """Checks for semantic mismatches, like a 'title' with 'References' text."""
    category = ann.get('category_type')
    text = ann.get('text', '').strip().lower()
    
    if category in SEMANTIC_KEYWORDS and text in SEMANTIC_KEYWORDS[category]:
        yield f"[WARNING] Possible miscategorization: Category is '{category}' but text is '{ann.get('text', '')}'. Should it be '{text}'?"

def run_validation():
    """Main function to run validation on all JSON files."""
    json_paths = glob.glob(os.path.join(DATA_DIR, '*.json'))
    total_files = len(json_paths)
    files_with_issues = 0
    total_issues = 0

    if total_files == 0:
        print(f"No JSON files found in '{DATA_DIR}'.")
        return

    print(f"--- Starting validation for {total_files} files in '{DATA_DIR}' ---")

    for i, path in enumerate(json_paths):
        filename = os.path.basename(path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"--- ISSUES FOUND in {filename} ---")
            print(f"  - [FATAL] Could not parse JSON file: {e}")
            files_with_issues += 1
            total_issues += 1
            print("-" * (len(filename) + 20) + "\n")
            continue

        file_issues = []
        layout_dets = data.get('layout_dets', [])
        layout_dets_map = {det.get('anno_id'): det for det in layout_dets}

        for det in layout_dets:
            anno_id = det.get('anno_id', 'N/A')
            issues = [
                *check_required_keys(det),
                *validate_language(det),
                *validate_parent_son(det, data, layout_dets_map),
                *validate_chart(det),
                *validate_semantic_mismatch(det),
            ]
            if issues:
                file_issues.append((anno_id, issues))
        
        if file_issues:
            files_with_issues += 1
            print(f"--- ISSUES FOUND in {filename} ---")
            for anno_id, issues in file_issues:
                total_issues += len(issues)
                print(f"  - Annotation ID: {anno_id}")
                for issue in issues:
                    print(f"    - {issue}")
            print("-" * (len(filename) + 20) + "\n")

    print("--- Validation Summary ---")
    print(f"Total files checked: {total_files}")
    print(f"Files with issues: {files_with_issues}")
    print(f"Total issues found: {total_issues}")
    print("--------------------------")

if __name__ == "__main__":
    run_validation()
