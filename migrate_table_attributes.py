import json
import os
from pathlib import Path
from tqdm import tqdm

def migrate_table_line_attributes(data_dir: str):
    """
    data 폴더 내의 JSON 파일들을 순회하며 table.attribute.line 속성값을 변경합니다.
    """
    data_path = Path(data_dir)
    # 데이터 폴더 내의 모든 JSON 파일을 재귀적으로 찾음
    json_files = list(data_path.rglob("*.json"))
    
    # 변경 매핑 정의
    line_mapping = {
        "table_wireless_line": "table_no_line",
        "table_fewer_line": "table_partial_line",
        "table_less_line": "table_partial_line"
    }
    
    stats = {
        "files_checked": 0,
        "files_modified": 0,
        "total_changes": 0
    }

    print(f"🔍 총 {len(json_files)}개의 파일을 검사합니다...")

    for json_file in tqdm(json_files, desc="Processing JSONs"):
        stats["files_checked"] += 1
        changed = False
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # layout_dets 리스트가 있는지 확인
            if "layout_dets" in data and isinstance(data["layout_dets"], list):
                for item in data["layout_dets"]:
                    # category_type이 table인 항목만 처리
                    if item.get("category_type") == "table":
                        attribute = item.get("attribute")
                        if isinstance(attribute, dict):
                            current_line = attribute.get("line")
                            
                            # 매핑 대상인 경우 값 변경
                            if current_line in line_mapping:
                                new_line = line_mapping[current_line]
                                attribute["line"] = new_line
                                stats["total_changes"] += 1
                                changed = True
            
            # 변경사항이 있을 때만 파일 저장 (원본 포맷 유지 위해 indent 사용)
            if changed:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                stats["files_modified"] += 1
                
        except Exception as e:
            print(f"\n❌ Error processing {json_file}: {e}")

    print("\n" + "="*40)
    print("✨ 작업 완료!")
    print(f"📊 검사한 파일 수: {stats['files_checked']}")
    print(f"📊 수정된 파일 수: {stats['files_modified']}")
    print(f"📊 총 변경된 속성 수: {stats['total_changes']}")
    print("="*40)

if __name__ == "__main__":
    # 데이터 폴더 경로 (현재 위치 기준 data 폴더)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    DATA_DIRECTORY = os.path.join(current_dir, "data/Alchera_rework_P1_260317")
    
    if os.path.exists(DATA_DIRECTORY):
        migrate_table_line_attributes(DATA_DIRECTORY)
    else:
        print(f"❌ 데이터 폴더를 찾을 수 없습니다: {DATA_DIRECTORY}")
