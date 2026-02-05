"""
이상치 분석 및 통계 함수

문서 타입별 규칙을 기반으로 텍스트 길이, 폴리곤 크기, 카테고리 분포의
이상치를 탐지합니다.
"""

from typing import List, Dict, Any, Tuple
import statistics
import numpy as np
from qa_visualizer.core import Document
from qa_visualizer.rules import (
    get_text_length_rule,
    get_bbox_size_rule,
    extract_doc_type_from_filename,
)


def calculate_bbox_area(poly: List) -> Dict[str, float]:
    """
    폴리곤의 넓이 및 크기 정보 계산
    
    Args:
        poly: 폴리곤 좌표
              - Nested list: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
              - Flat list: [x1, y1, x2, y2, x3, y3, x4, y4]
    
    Returns:
        {'width': 너비, 'height': 높이, 'area': 넓이, 'aspect_ratio': 가로세로비율}
    """
    if not poly or len(poly) < 2:
        return {'width': 0, 'height': 0, 'area': 0, 'aspect_ratio': 0}
    
    # Flat list인 경우 nested list로 변환
    if isinstance(poly[0], (int, float)):
        # [x1, y1, x2, y2, ...] -> [[x1, y1], [x2, y2], ...]
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


def detect_text_length_outliers(
    docs: List[Document],
    doc_type_filter: str = None
) -> List[Dict[str, Any]]:
    """
    텍스트 길이 이상치 탐지
    
    Args:
        docs: 문서 리스트
        doc_type_filter: 특정 문서 타입만 분석 (None이면 전체)
    
    Returns:
        이상치 목록 [{'file': ..., 'anno_id': ..., 'category': ..., 'length': ..., 'reason': ...}]
    """
    outliers = []
    
    for doc in docs:
        doc_type = extract_doc_type_from_filename(doc.filename)
        
        # 문서 타입 필터 적용
        if doc_type_filter and doc_type != doc_type_filter:
            continue
        
        for ann in doc.layout_dets:
            if not ann.text:
                continue
            
            text_length = len(ann.text)
            category = ann.category_type
            
            # 규칙 가져오기
            rule = get_text_length_rule(doc_type, category)
            if not rule:
                continue
            
            min_len, max_len, description = rule
            
            # 이상치 판정
            if text_length < min_len:
                outliers.append({
                    'file': doc.filename,
                    'doc_type': doc_type,
                    'anno_id': ann.anno_id,
                    'category': category,
                    'order': ann.order,
                    'length': text_length,
                    'min': min_len,
                    'max': max_len,
                    'reason': f'너무 짧음 (최소 {min_len}자)',
                    'text_preview': ann.text[:50] + '...' if len(ann.text) > 50 else ann.text,
                })
            elif text_length > max_len:
                outliers.append({
                    'file': doc.filename,
                    'doc_type': doc_type,
                    'anno_id': ann.anno_id,
                    'category': category,
                    'order': ann.order,
                    'length': text_length,
                    'min': min_len,
                    'max': max_len,
                    'reason': f'너무 김 (최대 {max_len}자)',
                    'text_preview': ann.text[:50] + '...' if len(ann.text) > 50 else ann.text,
                })
    
    return outliers


def detect_bbox_size_outliers(
    docs: List[Document],
    doc_type_filter: str = None
) -> List[Dict[str, Any]]:
    """
    폴리곤 크기 이상치 탐지
    
    Args:
        docs: 문서 리스트
        doc_type_filter: 특정 문서 타입만 분석 (None이면 전체)
    
    Returns:
        이상치 목록
    """
    outliers = []
    
    for doc in docs:
        doc_type = extract_doc_type_from_filename(doc.filename)
        
        # 문서 타입 필터 적용
        if doc_type_filter and doc_type != doc_type_filter:
            continue
        
        page_width = doc.page_info.width
        page_height = doc.page_info.height
        page_area = page_width * page_height
        
        for ann in doc.layout_dets:
            if not ann.poly:
                continue
            
            size_info = calculate_bbox_area(ann.poly)
            area_ratio = size_info['area'] / page_area if page_area > 0 else 0
            aspect_ratio = size_info['aspect_ratio']
            category = ann.category_type
            
            # 규칙 가져오기
            rule = get_bbox_size_rule(doc_type, category)
            if not rule:
                continue
            
            min_ratio, max_ratio, (min_aspect, max_aspect) = rule
            
            # 이상치 판정
            reasons = []
            
            if area_ratio < min_ratio:
                reasons.append(f'너무 작음 (최소 {min_ratio*100:.1f}%)')
            
            if area_ratio > max_ratio:
                reasons.append(f'너무 큼 (최대 {max_ratio*100:.1f}%)')
            
            if aspect_ratio < min_aspect or aspect_ratio > max_aspect:
                reasons.append(f'비율 이상 ({aspect_ratio:.2f}, 정상: {min_aspect}~{max_aspect})')
            
            if reasons:
                outliers.append({
                    'file': doc.filename,
                    'doc_type': doc_type,
                    'anno_id': ann.anno_id,
                    'category': category,
                    'order': ann.order,
                    'width': size_info['width'],
                    'height': size_info['height'],
                    'area': size_info['area'],
                    'area_ratio': area_ratio * 100,  # 퍼센트로 변환
                    'aspect_ratio': aspect_ratio,
                    'min_ratio': min_ratio * 100,
                    'max_ratio': max_ratio * 100,
                    'reason': ', '.join(reasons),
                })
    
    return outliers


def detect_outliers(doc) -> List[Dict[str, Any]]:
    """
    단일 문서의 이상치 탐지 (기존 함수 유지 - 하위 호환성)
    
    Args:
        doc: Document 객체 또는 dict (raw_data)
    
    Returns:
        이상치 목록
    """
    # dict인 경우 기존 로직 사용
    if isinstance(doc, dict):
        return _detect_outliers_from_dict(doc)
    
    # Document 객체인 경우 새로운 로직 사용
    text_outliers = detect_text_length_outliers([doc])
    bbox_outliers = detect_bbox_size_outliers([doc])
    
    return text_outliers + bbox_outliers


def _detect_outliers_from_dict(full_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    dict에서 이상치 탐지 (기존 로직)
    
    Args:
        full_data: 문서 전체 데이터 (dict)
        
    Returns:
        이상치 정보 리스트
    """
    
    outliers = []
    layout_dets = full_data.get("layout_dets", [])
    
    if not layout_dets:
        return outliers
    
    # 폴리곤 크기 통계
    poly_areas = []
    for ann in layout_dets:
        poly = ann.get("poly")
        if poly and len(poly) >= 4:
            # 간단한 바운딩 박스 면적 계산
            size_info = calculate_bbox_area(poly)
            poly_areas.append((ann.get("anno_id"), size_info['area'], size_info['width'], size_info['height']))
    
    if poly_areas:
        areas = [area for _, area, _, _ in poly_areas]
        mean_area = statistics.mean(areas)
        stdev_area = statistics.stdev(areas) if len(areas) > 1 else 0
        
        # 평균에서 3 표준편차 이상 벗어난 것을 이상치로 간주
        if stdev_area > 0:
            for anno_id, area, width, height in poly_areas:
                z_score = abs((area - mean_area) / stdev_area)
                if z_score > 3:
                    outliers.append({
                        "type": "polygon_size",
                        "anno_id": anno_id,
                        "severity": "warning",
                        "message": f"비정상적인 폴리곤 크기: 면적={area:.0f} (평균={mean_area:.0f}, Z-score={z_score:.2f}), 크기={width:.0f}x{height:.0f}",
                    })
    
    # 텍스트 길이 이상치
    text_lengths = []
    for ann in layout_dets:
        text = ann.get("text")
        if text:
            text_lengths.append((ann.get("anno_id"), len(text)))
    
    if text_lengths:
        lengths = [length for _, length in text_lengths]
        mean_length = statistics.mean(lengths)
        stdev_length = statistics.stdev(lengths) if len(lengths) > 1 else 0
        
        if stdev_length > 0:
            for anno_id, length in text_lengths:
                z_score = abs((length - mean_length) / stdev_length)
                if z_score > 3:
                    outliers.append({
                        "type": "text_length",
                        "anno_id": anno_id,
                        "severity": "warning",
                        "message": f"비정상적인 텍스트 길이: {length}자 (평균={mean_length:.0f}자, Z-score={z_score:.2f})",
                    })
    
    # 고립된 어노테이션 (관계가 없는 것)
    relations = full_data.get("extra", {}).get("relation", [])
    if relations:
        connected_ids = set()
        for rel in relations:
            connected_ids.add(rel.get("source_anno_id"))
            connected_ids.add(rel.get("target_anno_id"))
        
        for ann in layout_dets:
            anno_id = ann.get("anno_id")
            category = ann.get("category_type")
            # Figure, Table, Equation은 관계가 있어야 함
            if category in ["Figure", "Table", "Equation"] and anno_id not in connected_ids:
                outliers.append({
                    "type": "isolated_annotation",
                    "anno_id": anno_id,
                    "severity": "info",
                    "message": f"고립된 {category}: 다른 어노테이션과의 관계가 없습니다.",
                })
    
    return outliers


def get_statistics_summary(docs: List[Document], doc_type_filter: str = None) -> Dict[str, Any]:
    """
    통계 요약 정보 생성
    
    Args:
        docs: 문서 리스트
        doc_type_filter: 특정 문서 타입만 분석
    
    Returns:
        통계 요약 딕셔너리
    """
    # 필터링된 문서
    filtered_docs = docs
    if doc_type_filter:
        filtered_docs = [
            doc for doc in docs
            if extract_doc_type_from_filename(doc.filename) == doc_type_filter
        ]
    
    # 기본 통계
    total_files = len(filtered_docs)
    total_annotations = sum(len(doc.layout_dets) for doc in filtered_docs)
    
    # 텍스트 길이 통계
    text_lengths = []
    for doc in filtered_docs:
        for ann in doc.layout_dets:
            if ann.text:
                text_lengths.append(len(ann.text))
    
    # 폴리곤 크기 통계
    bbox_areas = []
    for doc in filtered_docs:
        page_area = doc.page_info.width * doc.page_info.height
        for ann in doc.layout_dets:
            if ann.poly:
                size_info = calculate_bbox_area(ann.poly)
                bbox_areas.append(size_info['area'] / page_area * 100)
    
    # 카테고리 분포
    category_counts = {}
    for doc in filtered_docs:
        for ann in doc.layout_dets:
            category = ann.category_type
            category_counts[category] = category_counts.get(category, 0) + 1
    
    return {
        'total_files': total_files,
        'total_annotations': total_annotations,
        'text_length': {
            'mean': np.mean(text_lengths) if text_lengths else 0,
            'median': np.median(text_lengths) if text_lengths else 0,
            'std': np.std(text_lengths) if text_lengths else 0,
            'min': min(text_lengths) if text_lengths else 0,
            'max': max(text_lengths) if text_lengths else 0,
        },
        'bbox_area': {
            'mean': np.mean(bbox_areas) if bbox_areas else 0,
            'median': np.median(bbox_areas) if bbox_areas else 0,
            'std': np.std(bbox_areas) if bbox_areas else 0,
            'min': min(bbox_areas) if bbox_areas else 0,
            'max': max(bbox_areas) if bbox_areas else 0,
        },
        'category_distribution': category_counts,
    }
