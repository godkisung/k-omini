from PIL import Image
from typing import List, Dict, Any, Tuple
from src.config import get_config
from src.core.models import Annotation
from src.core.visualizer import draw_annotations_on_image as core_draw_annotations

# Config Injection
config = get_config()

def draw_annotations_on_image(
    image: Image.Image,
    annotations: List[Annotation],
    highlight_indices: List[int] = None,
    color_map: Dict[str, str] = None, # Deprecated argument
    default_color: str = "#000000", # Deprecated argument
    width: int = 3
) -> Image.Image:
    """
    Wrapper for src.core.visualizer.draw_annotations_on_image
    Uses the global config by default.
    Ignores color_map for now as core uses config object.
    """
    
    # If custom color map is passed, we might need a dynamic config wrapper
    # But for now, we assume standard usage.
    
    return core_draw_annotations(
        image=image,
        annotations=annotations,
        config=config,
        highlight_indices=highlight_indices,
        width=width
    )

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """HEX 색상 코드를 RGB 튜플로 변환합니다."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
