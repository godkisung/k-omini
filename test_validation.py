from src.analysis.validator import Validator
from src.config import get_config
from src.core.models import Document
import sys
import json

def run():
    config = get_config()
    validator = Validator(config)
    
    file_path = "data/poc_ver2/json/PB00001_00023_간행물_2020.09.23(수)_2480호.json"
    doc = Document.from_json(file_path)
    
    figures = [ann for ann in doc.layout_dets if ann.category_type == 'figure']
    print(f"Total figures found: {len(figures)}")
    
    # 이투데이 로고가 있는 곳 좌표 근처의 figure 정보 출력
    for fig in figures:
        if fig.poly[1] > 4000: # 이투데이 근처 영역
            print(f"Fig ID {fig.anno_id}, Poly: {fig.poly}")
            
    # 후보 자식 위치들도 출력해보기
    child_candidates = [
        ann for ann in doc.layout_dets 
        if ann.category_type in ['text_block', 'table', 'chart']
    ]
    for child in child_candidates:
        if child.poly and len(child.poly)>1 and child.poly[1] > 4800:
            print(f"Child {child.category_type} ID {child.anno_id}, Poly: {child.poly}")
    
    results = validator.validate_document(doc)
    
    missing_figs = [r for r in results if r.rule_id == "missing_figure_dependency"]
    
    print(f"\nTotal missing_figure_dependency errors: {len(missing_figs)}")
    for r in missing_figs:
        print(r.message)

if __name__ == "__main__":
    run()
