from src.analysis.validator import Validator
from src.config import get_config
from src.core.models import Document
from shapely.geometry import Polygon

def run():
    config = get_config()
    validator = Validator(config)
    
    file_path = "data/poc_ver2/json/PB00001_00023_간행물_2020.09.23(수)_2480호.json"
    doc = Document.from_json(file_path)
    
    figures = [ann for ann in doc.layout_dets if ann.category_type == 'figure' and ann.poly[1] > 4000]
    texts = [ann for ann in doc.layout_dets if ann.anno_id in [60, 61, 62]]
    
    for fig in figures:
        print(f"\nFigure ID {fig.anno_id}, Poly: {fig.poly}")
        p_pts = [(fig.poly[i], fig.poly[i+1]) for i in range(0, len(fig.poly), 2)]
        parent_poly = Polygon(p_pts)
        print(f"  Area: {parent_poly.area}")
        parent_buffered = parent_poly.buffer(20.0)
        print(f"  Buffered Area (+20px): {parent_buffered.area}")
        
        for text in texts:
            print(f"  -> Text ID {text.anno_id}, Text: '{text.text}', Poly: {text.poly}")
            c_pts = [(text.poly[i], text.poly[i+1]) for i in range(0, len(text.poly), 2)]
            child_poly = Polygon(c_pts)
            print(f"     Area: {child_poly.area}")
            
            inter = parent_buffered.intersection(child_poly)
            print(f"     Intersection Area: {inter.area}")
            print(f"     IoA: {inter.area / child_poly.area:.2%}")

if __name__ == "__main__":
    run()
