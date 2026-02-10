from typing import List, Dict, Any, Tuple
from src.core.models import Document, Annotation
from src.config.base import BaseConfig

class OutlierDetector:
    def __init__(self, config: BaseConfig):
        self.config = config

    def calculate_bbox_area(self, poly: List) -> Dict[str, float]:
        """폴리곤의 넓이 및 크기 정보 계산 (Generic Helper)"""
        if not poly or len(poly) < 2:
            return {'width': 0, 'height': 0, 'area': 0, 'aspect_ratio': 0}
        
        # Flat list인 경우 nested list로 변환
        if isinstance(poly[0], (int, float)):
            poly = [[poly[i], poly[i+1]] for i in range(0, len(poly), 2)]
        
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        area = width * height
        aspect_ratio = width / height if height > 0 else 0
        
        return {
            'width': width,
            'height': height,
            'area': area,
            'aspect_ratio': aspect_ratio
        }

    def detect_text_length_outliers(self, docs: List[Document], doc_type_filter: str = None) -> List[Dict[str, Any]]:
        """텍스트 길이 이상치 탐지 (Config 기반 규칙 적용)"""
        outliers = []
        for doc in docs:
            # Assuming doc type extraction is needed (project specific helper or generic)
            # For now, let's assume we can determine doc_type or use DEFAULT from config helper
            # But wait, config helper logic needs to be injected too?
            # Let's assume the doc.filename is enough context for now? 
            # Or Config should have a helper method: get_doc_type(filename)
            
            # K-Omnidoc Specific Logic needs to be bridged.
            # BaseConfig doesn't mandate get_doc_type_from_filename. 
            # We can check if config has the method or fallback to strict matching
            if hasattr(self.config, 'get_doc_type_from_filename'):
                doc_type = self.config.get_doc_type_from_filename(doc.filename)
            else:
                doc_type = 'DEFAULT'

            if doc_type_filter and doc_type != doc_type_filter:
                continue
            
            for ann in doc.layout_dets:
                if not ann.text: continue
                
                text_len = len(ann.text)
                cat = ann.category_type
                
                # Rule Lookup
                rule = None
                rules = self.config.TEXT_LENGTH_RULES
                if doc_type in rules and cat in rules[doc_type]:
                    rule = rules[doc_type][cat]
                elif 'DEFAULT' in rules and cat in rules['DEFAULT']:
                    rule = rules['DEFAULT'][cat]
                
                if not rule: continue
                
                min_len, max_len, desc = rule
                if text_len < min_len:
                    outliers.append({
                        'file': doc.filename, 'doc_type': doc_type, 'anno_id': ann.anno_id,
                        'category': cat, 'length': text_len, 'min': min_len, 'max': max_len,
                        'reason': f"Too short (min {min_len})"
                    })
                elif text_len > max_len:
                    outliers.append({
                        'file': doc.filename, 'doc_type': doc_type, 'anno_id': ann.anno_id,
                        'category': cat, 'length': text_len, 'min': min_len, 'max': max_len,
                        'reason': f"Too long (max {max_len})"
                    })
        return outliers

    def detect_bbox_size_outliers(self, docs: List[Document], doc_type_filter: str = None) -> List[Dict[str, Any]]:
        """BBox 크기 이상치 탐지"""
        outliers = []
        for doc in docs:
            if hasattr(self.config, 'get_doc_type_from_filename'):
                doc_type = self.config.get_doc_type_from_filename(doc.filename)
            else:
                doc_type = 'DEFAULT'

            if doc_type_filter and doc_type != doc_type_filter: continue
            
            page_w = doc.page_info.get('width', 0)
            page_h = doc.page_info.get('height', 0)
            page_area = page_w * page_h
            if page_area <= 0: continue

            for ann in doc.layout_dets:
                if not ann.poly: continue
                size_info = self.calculate_bbox_area(ann.poly)
                area_ratio = size_info['area'] / page_area
                aspect = size_info['aspect_ratio']
                cat = ann.category_type
                
                # Rule Lookup
                rule = None
                rules = self.config.BBOX_SIZE_RULES
                if doc_type in rules and cat in rules[doc_type]:
                    rule = rules[doc_type][cat]
                elif 'DEFAULT' in rules and cat in rules['DEFAULT']:
                    rule = rules['DEFAULT'][cat]
                
                if not rule: continue
                
                min_ratio, max_ratio, (min_ar, max_ar) = rule
                
                reasons = []
                if area_ratio < min_ratio: reasons.append(f"Too small (<{min_ratio:.1%})")
                if area_ratio > max_ratio: reasons.append(f"Too large (>{max_ratio:.1%})")
                if aspect < min_ar or aspect > max_ar: reasons.append(f"Odd AspectRatio ({aspect:.2f})")
                
                if reasons:
                    outliers.append({
                        'file': doc.filename, 'doc_type': doc_type, 'anno_id': ann.anno_id,
                        'category': cat, 'area_ratio': area_ratio*100,
                        'reason': ", ".join(reasons)
                    })
        return outliers
