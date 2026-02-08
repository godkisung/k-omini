from __future__ import annotations
import json
import os
from typing import List, Dict, Any, Optional


class Annotation:
    """A class to represent a single annotation object."""

    def __init__(self, ann_data: Dict[str, Any]):
        self.data = ann_data

    @property
    def anno_id(self) -> Optional[str]:
        return self.data.get("anno_id")

    @property
    def category_type(self) -> Optional[str]:
        return self.data.get("category_type")

    @property
    def order(self) -> int:
        val = self.data.get("order")
        return val if val is not None else float("inf")

    @property
    def poly(self) -> Optional[List[float]]:
        return self.data.get("poly")

    @property
    def text(self) -> Optional[str]:
        return self.data.get("text")

    @property
    def html(self) -> Optional[str]:
        return self.data.get("html")

    @property
    def latex(self) -> Optional[str]:
        return self.data.get("latex")

    @property
    def attributes(self) -> Dict[str, Any]:
        return self.data.get("attribute", {})

    def is_inside(self, x: float, y: float) -> bool:
        """Check if a point (x, y) is inside the annotation's polygon using the ray-casting algorithm."""
        if not self.poly:
            return False

        num_vertices = len(self.poly) // 2
        vertices = list(zip(self.poly[0::2], self.poly[1::2]))

        intersections = 0
        for i in range(num_vertices):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % num_vertices]

            # Ensure p1.y <= p2.y
            if p1[1] > p2[1]:
                p1, p2 = p2, p1

            # The horizontal ray does not intersect with the edge
            if y > p2[1] or y < p1[1] or x > max(p1[0], p2[0]):
                continue

            # The horizontal ray intersects with a vertical edge
            if p1[0] == p2[0]:
                intersections += 1
                continue

            # Calculate the x-intersection of the line
            x_intersection = (y - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1]) + p1[0]
            if x_intersection < x:
                intersections += 1

        return intersections % 2 == 1

    def __getattr__(self, name: str) -> Any:
        """Allow direct access to data keys, preventing recursion."""
        # This check is crucial to prevent recursion when `pickle` tries to access `self.data`.
        if name == "data":
            raise AttributeError()
        
        if name in self.data:
            return self.data[name]
        raise AttributeError(f"'Annotation' object has no attribute '{name}'")


class Document:
    """A class to represent a full document page, including all its annotations."""

    def __init__(self, data: Dict[str, Any], filename: str = None):
        self.raw_data = data
        self.filename = filename
        self.layout_dets: List[Annotation] = sorted(
            [Annotation(ann) for ann in data.get("layout_dets", [])],
            key=lambda x: x.order,
        )
        self.relations: List[Dict[str, Any]] = data.get("extra", {}).get("relation", [])

    @property
    def page_info(self):
        from types import SimpleNamespace
        return SimpleNamespace(**self.raw_data.get("page_info", {}))

    @property
    def image_path(self) -> Optional[str]:
        return self.raw_data.get("page_info", {}).get("image_path")

    @classmethod
    def from_json(cls, file_path: str) -> Document:
        """Load a document from a JSON file path."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data, filename=os.path.basename(file_path))

    def get_annotation_by_id(self, anno_id: str) -> Optional[Annotation]:
        """Find an annotation by its ID."""
        for ann in self.layout_dets:
            if ann.anno_id == anno_id:
                return ann
        return None
