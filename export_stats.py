import os
import glob
from collections import Counter, defaultdict
import pandas as pd
from src.sampling.sampler import DOC_TYPE_NAMES, get_doc_type

def export_doc_type_ratios_to_excel(output_path: str = "doc_type_statistics.xlsx"):
    """
    data/ 폴더 내 'final'이 포함된 경로의 JSON 파일들을 분석하여 
    문서 타입별 비율을 엑셀로 내보냅니다.
    """
    # 1. 'final'이 포함된 디렉토리 내의 모든 JSON 파일 경로 수집
    search_pattern = os.path.join("data", "**", "*final*", "**", "*.json")
    print(f"[*] 탐색 패턴: {search_pattern}")
    
    file_paths = glob.glob(search_pattern, recursive=True)
    
    if not file_paths:
        print("[!] 첫 번째 패턴으로 파일을 찾지 못해 전체 탐색을 시도합니다...")
        all_json_files = glob.glob(os.path.join("data", "**", "*.json"), recursive=True)
        file_paths = [fp for fp in all_json_files if "final" in fp.lower()]
    
    if not file_paths:
        print("[-] 분석할 JSON 파일을 찾지 못했습니다.")
        return

    print(f"[*] 총 {len(file_paths)}개의 파일을 찾았습니다. 분석 중...")

    # 2. 문서 타입별 분류 및 ETC 파일 수집
    doc_types = []
    etc_files = []
    
    for fp in file_paths:
        code = get_doc_type(fp)
        doc_types.append(code)
        if code == "ETC":
            etc_files.append(fp)

    type_counts = Counter(doc_types)
    total_files = len(file_paths)

    # 3. 통계 데이터 생성
    all_keys = sorted(list(set(list(DOC_TYPE_NAMES.keys()) + list(type_counts.keys()))))
    
    stats_data = []
    for code in all_keys:
        count = type_counts.get(code, 0)
        if count == 0 and code not in DOC_TYPE_NAMES:
            continue
            
        name = DOC_TYPE_NAMES.get(code, "기타(ETC)" if code == "ETC" else "알 수 없음")
        ratio = (count / total_files) * 100 if total_files > 0 else 0
        
        stats_data.append({
            "문서 코드": code,
            "문서 유형": name,
            "파일 개수": count,
            "비율 (%)": round(ratio, 2)
        })

    df_stats = pd.DataFrame(stats_data)
    
    # 합계 행 추가
    summary_data = {"문서 코드": "TOTAL", "문서 유형": "-", "파일 개수": total_files, "비율 (%)": 100.0}
    if len(df_stats) > 0:
        df_main = df_stats.sort_values(by="파일 개수", ascending=False)
        df_stats = pd.concat([df_main, pd.DataFrame([summary_data])], ignore_index=True)

    # 4. ETC 파일 상세 리스트 생성
    df_etc = pd.DataFrame([{"ETC 파일 경로": fp, "파일명": os.path.basename(fp)} for fp in etc_files])

    # 5. 엑셀 저장 (멀티 시트)
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_stats.to_excel(writer, sheet_name="문서유형통계", index=False)
            if not df_etc.empty:
                df_etc.to_excel(writer, sheet_name="ETC파일목록", index=False)
        
        print(f"[+] 성공: 통계 결과가 '{output_path}'에 저장되었습니다.")
        
        # 요약 출력
        print("\n--- 통계 요약 ---")
        print(df_stats.to_string(index=False))
        
        if etc_files:
            print("\n--- ETC 분류 파일 (총 {}건) ---".format(len(etc_files)))
            for i, fp in enumerate(etc_files[:10], 1):
                print(f"{i}. {fp}")
            if len(etc_files) > 10:
                print("...외 {}건 더 있음 (엑셀 'ETC파일목록' 시트 확인)".format(len(etc_files) - 10))
        
    except Exception as e:
        print(f"[!] 엑셀 저장 중 오류 발생: {e}")

if __name__ == "__main__":
    export_doc_type_ratios_to_excel()
