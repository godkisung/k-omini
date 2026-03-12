import os
import glob
import json
import argparse
from pathlib import Path

def find_empty_texts(json_dir: str):
    """
    지정된 디렉토리 내의 모든 JSON 파일을 스캔하여,
    텍스트가 필수인 항목(text_block, title 등)의 text 값이 ""(빈 칸)인 데이터를 찾아냅니다.
    """
    print(f"🔍 '{json_dir}' 경로 내의 JSON 파일을 스캔합니다...\n")
    
    json_files = sorted(glob.glob(os.path.join(json_dir, "**/*.json"), recursive=True))
    if not json_files:
        print("❌ JSON 파일을 찾을 수 없습니다.")
        return
        
    empty_docs = []
    
    # 텍스트가 필수적으로 존재해야 하는 카테고리 목록
    text_required_cats = {
        "text_block", "title", "header", "footer", 
        "list_item", "table_caption", "figure_caption", "page_footnote"
    }
    
    found_count = 0
    for jpath in json_files:
        try:
            with open(jpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # print(data)
        except Exception:
            continue
            
        # JSON의 최상단이 딕셔너리가 아닌 경우(예: 배열로만 된 파일) 건너뛰기
        if not isinstance(data, dict):
            continue
            
        empty_annos = []
        for ann in data.get("layout_dets", []):
            cat = ann.get("category_type", "")
            # 추출 대상 카테고리인지 확인
            if cat in text_required_cats:
                text = ann.get("text")
                # text가 None이 아니면서 빈 문자열(공백 제외)인 경우 탐지
                if text is not None and str(text).strip() == "":
                    
                    ignore_status = ann.get("ignore", False)
                    empty_annos.append((ann.get("anno_id"), cat, ignore_status))
                    
        if empty_annos:
            empty_docs.append((jpath, empty_annos))
            found_count += len(empty_annos)
            
    print("=" * 60)
    print(f"✅ 총 {len(json_files)}개의 JSON 검사 완료.")
    print(f"🚨 빈 텍스트(text=\"\")가 포함된 파일: {len(empty_docs)}개 문서 (총 {found_count}건의 항목)")
    print("=" * 60 + "\n")
    
    # 결과 출력
    for doc_path, annos in empty_docs:
        file_name = os.path.basename(doc_path)
        print(f"📄 파일명: {file_name}")
        for anno_id, cat, is_ignore in annos:
            ignore_flag = "[IGNORE=True]" if is_ignore else ""
            print(f"   ↳ [ID: {anno_id}] 카테고리: {cat:<15} {ignore_flag}")
        print("-" * 40)
        
    print("\n💡 Tip: 발견된 파일명을 Streamlit 앱(검수 페이지)의 '검색' 창에 입력하고,")
    print("   '⚙️ 필터' 탭에서 '⚠️ 검증 오류만 보기'를 체크하면 시각적으로 쉽게 확인할 수 있습니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="빈 텍스트(text='') 어노테이션 스캔 스크립트")
    parser.add_argument("--json_dir", default="data/Alchera_delivery_P1_260227/json/", help="JSON 파일이 있는 루트 디렉토리 (기본값: data/)")
    args = parser.parse_args()
    
    find_empty_texts(args.json_dir)
