from src.analysis.validator import Validator
from src.config import get_config
from src.core.models import Document, Annotation
import sys
import copy

def run():
    config = get_config()
    validator = Validator(config)
    
    file_path = "data/poc_ver2/json/PB00001_00023_간행물_2020.09.23(수)_2480호.json"
    doc = Document.from_json(file_path)
    
    # 가상의 종속이 누락된 text_block 만들기 (기존 figure 내부 좌표로 수정)
    # Fig ID 59: [135.7, 4850.8, 2473.5, 4850.8, 2473.5, 5397.1, 135.7, 5397.1]
    
    fake_child = copy.deepcopy(doc.layout_dets[0])
    fake_child.anno_id = 999
    fake_child.category_type = 'text_block'
    # Figure 내부에 위치하도록 좌상단(200, 4900) ~ 우하단(500, 5000)
    fake_child.poly = [200.0, 4900.0, 500.0, 4900.0, 500.0, 5000.0, 200.0, 5000.0]
    fake_child.text = "가짜 포함 텍스트"
    
    doc.layout_dets.append(fake_child)
    
    results = validator.validate_document(doc)
    
    missing_figs = [r for r in results if r.rule_id == "missing_figure_dependency"]
    
    print(f"\nTotal missing_figure_dependency errors: {len(missing_figs)}")
    for r in missing_figs:
        print(f"Error: {r.message}")
        print(f"Details: {r.details}")

if __name__ == "__main__":
    run()
