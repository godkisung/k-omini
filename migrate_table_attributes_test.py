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
    

    print(f"🔍 총 {len(json_files)}개의 파일을 검사합니다...")

    for json_file in tqdm(json_files, desc="Processing JSONs"):
        changed = False
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # layout_dets 리스트가 있는지 확인
            if "layout_dets" in data and isinstance(data["layout_dets"], list):
                for item in data["layout_dets"]:
                    # # print(item)
                    # if item.get("category_type") == "figure":
                    #     attribute = item.get("attribute")
                    #     if isinstance(attribute, dict):
                    #         include_elements = attribute.get("contains_elements")
                    #         # print(include_elements)
                    #         if 'text' in include_elements:
                    #             print("text임")
                    #         elif not include_elements:
                    #             print("공백임")
                    #         else:
                    #             print(f"다른 것 있음: {include_elements}")
                    if item.get("category_type") == "table":
                        attribute = item.get("attribute")
                        if isinstance(attribute, dict):
                            current_line = attribute.get("line")
                        if isinstance(current_line, str):
                                line_elements = [current_line]
                        else:
                                line_elements = current_line # 이미 리스트인 경우
                                
                            # 2. 이제 set을 하면 단어 단위로 중복이 제거됩니다
                        if line_elements:
                            distinct_elements = set(line_elements)
                            print(distinct_elements)
                            if "table_wireless_line" in distinct_elements:
                                print("table_wireless_line 있음")
                            elif "table_no_line" in distinct_elements:
                                print("table_no_line 있음")
                            else:
                                print("no line 없음")
                                
                            
            
            # 변경사항이 있을 때만 파일 저장 (원본 포맷 유지 위해 indent 사용)
            if changed:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"\n❌ Error processing {json_file}: {e}")



if __name__ == "__main__":
    # 데이터 폴더 경로 (현재 위치 기준 data 폴더)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    DATA_DIRECTORY = os.path.join(current_dir, "data/Alchera_rework_P1_260317/json_backup")
    
    if os.path.exists(DATA_DIRECTORY):
        migrate_table_line_attributes(DATA_DIRECTORY)
    else:
        print(f"❌ 데이터 폴더를 찾을 수 없습니다: {DATA_DIRECTORY}")
