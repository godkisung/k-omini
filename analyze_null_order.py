import json
from collections import defaultdict

def analyze_null_order(file_path):
    """
    Analyzes a JSON file to find the distribution of layout objects
    where the 'order' key is null.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file was not found at '{file_path}'")
        return
    except json.JSONDecodeError:
        print(f"Error: The file at '{file_path}' is not a valid JSON file.")
        return
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return

    # The top-level JSON structure might be an object or a list of objects.
    # We'll normalize it to a list to handle both cases.
    if isinstance(data, dict):
        docs_to_process = [data]
    elif isinstance(data, list):
        docs_to_process = data
    else:
        print(f"Error: Expected JSON root to be an object or a list, but got {type(data).__name__}.")
        return

    null_order_blocks = []
    for doc in docs_to_process:
        layout_dets = doc.get("layout_dets", [])
        for det in layout_dets:
            # Check for missing 'order' key or if the value is explicitly null
            if det.get('order') is None:
                null_order_blocks.append(det)

    total_null_count = len(null_order_blocks)
    
    print(f"Total annotations with 'order: null': {total_null_count}")

    if total_null_count > 0:
        distribution = defaultdict(int)
        for block in null_order_blocks:
            category = block.get('category_type', 'N/A')
            distribution[category] += 1
        
        print("\nDistribution by Category Type:")
        # Sort by count descending for better readability
        sorted_distribution = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
        for category, count in sorted_distribution:
            print(f"- {category}: {count}")

if __name__ == "__main__":
    # The user specified this path relative to the 'data' directory
    # but let's assume it's relative to the project root for the script
    analyze_null_order("data/sample/OmniDocBench.json")
