import os
import glob
import json
import argparse

def find_self_references(json_dir: str):
    """
    지정된 디렉토리 내의 모든 JSON 파일을 스캔하여,
    extra.relation 배열 내에서 source_anno_id와 target_anno_id(또는 parent와 son)가
    동일한 '자기 참조(Self-referencing)' 오류를 찾아냅니다.
    """
    print(f"🔍 '{json_dir}' 경로 내의 JSON 파일을 스캔합니다...\n")
    
    json_files = sorted(glob.glob(os.path.join(json_dir, "**/*.json"), recursive=True))
    if not json_files:
        print("❌ JSON 파일을 찾을 수 없습니다.")
        return
        
    error_docs = []
    found_count = 0
    
    for jpath in json_files:
        try:
            with open(jpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
            
        if not isinstance(data, dict):
            continue
            
        extra = data.get("extra", {})
        if not isinstance(extra, dict):
            continue
            
        relations = extra.get("relation", [])
        if not isinstance(relations, list):
            continue
            
        file_errors = []
        for rel in relations:
            # 키가 parent/son 이거나 source_anno_id/target_anno_id 일 수 있음
            parent = rel.get('parent') if 'parent' in rel else rel.get('source_anno_id')
            son = rel.get('son') if 'son' in rel else rel.get('target_anno_id')
            
            if parent is not None and son is not None and parent == son:
                rel_type = rel.get('relation_type', 'unknown')
                file_errors.append((parent, rel_type))
                
        if file_errors:
            error_docs.append((jpath, file_errors))
            found_count += len(file_errors)
            
    print("=" * 60)
    print(f"✅ 총 {len(json_files)}개의 JSON 검사 완료.")
    print(f"🚨 자기 참조 오류가 포함된 파일: {len(error_docs)}개 문서 (총 {found_count}건의 항목)")
    print("=" * 60 + "\n")
    
    for doc_path, errors in error_docs:
        file_name = os.path.basename(doc_path)
        print(f"📄 파일명: {file_name}")
        for anno_id, rel_type in errors:
            print(f"   ↳ [ID: {anno_id}] 자기 자신을 참조하는 관계({rel_type}) 발견")
        print("-" * 40)
        
    print("\n💡 Tip: 발견된 파일명을 Streamlit 앱의 '검색' 창에 입력하고,")
    print("   '⚙️ 필터' 탭에서 '⚠️ 검증 오류만 보기'를 선택하면 빨간 뱃지로 표시됩니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="자기 참조(Self-referencing) 관계 스캔 스크립트")
    parser.add_argument("--json_dir", default="data/Alchera_delivery_P1_260227/json/", help="JSON 파일이 있는 루트 디렉토리 (기본값: data/)")
    args = parser.parse_args()
    
    find_self_references(args.json_dir)
