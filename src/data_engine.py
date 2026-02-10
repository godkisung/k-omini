import os
import glob
from typing import List
from src.core.models import Annotation, Document, get_json_files as core_get_json_files
from src.config import DATA_DIR

# Re-exporting for backward compatibility
Annotation = Annotation
Document = Document

def get_json_files(directory: str = None) -> List[str]:
    """지정된 디렉토리(기본값: config.DATA_DIR)에서 모든 JSON 파일을 가져옵니다."""
    if directory is None:
        directory = DATA_DIR
    
    return core_get_json_files(directory)

def load_document(file_path: str) -> Document:
    """JSON 파일 경로에서 Document 객체를 로드합니다."""
    return Document.from_json(file_path)
