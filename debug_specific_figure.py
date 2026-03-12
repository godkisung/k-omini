import json
from shapely.geometry import Polygon

file_path = "data/Alchera_delivery_P2_260306/json/MG00016_00435_07_매뉴얼,가이드_교육가이드_(중등 교사용) KERIS와 시작하는 인공지능 교육 직무연수_0.json"
try:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    print(f"Error loading file: {e}")
    # try without /json/
    file_path = "data/Alchera_delivery_P2_260306/MG00016_00435_07_매뉴얼,가이드_교육가이드_(중등 교사용) KERIS와 시작하는 인공지능 교육 직무연수_0.json"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

fig = next((a for a in data['layout_dets'] if a['anno_id'] == 22), None)
txt = next((a for a in data['layout_dets'] if a['anno_id'] == 23), None)

print(f"Figure (ID: 22): {fig['poly'] if fig else 'Not Found'}")
print(f"Text (ID: 23): {txt['poly'] if txt else 'Not Found'}")

if fig and txt:
    p_pts = [(fig['poly'][i], fig['poly'][i+1]) for i in range(0, len(fig['poly']), 2)]
    c_pts = [(txt['poly'][i], txt['poly'][i+1]) for i in range(0, len(txt['poly']), 2)]
    
    parent_poly = Polygon(p_pts)
    child_poly = Polygon(c_pts)
    
    print(f"Parent Area: {parent_poly.area}")
    print(f"Child Area: {child_poly.area}")
    
    parent_buffered = parent_poly.buffer(20.0)
    inter = parent_buffered.intersection(child_poly)
    
    print(f"Intersection w/ buffer: {inter.area}")
    print(f"IoA w/ buffer: {inter.area / child_poly.area * 100:.2f}%")
    
    inter_no_buf = parent_poly.intersection(child_poly)
    print(f"Intersection NO buffer: {inter_no_buf.area}")
    print(f"IoA NO buffer: {inter_no_buf.area / child_poly.area * 100:.2f}%")
