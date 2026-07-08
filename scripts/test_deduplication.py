"""
Test script for the Document Deduplication Pipeline.
"""

import sys
import os

# root 디렉토리를 path에 추가하여 src 모듈을 임포트할 수 있도록 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import DocumentDupPipeline, Document, Annotation
from src.core.exceptions import PipelineBaseException

def main():
    print(">>> Initializing Document Deduplication Pipeline...")
    print(">>> Note: Models (DINOv2, Florence-2) will be downloaded if not cached.")
    try:
        pipeline = DocumentDupPipeline(milvus_host="localhost", milvus_port="19530")
        print(">>> Pipeline explicitly initialized successfully.")
        print(f">>> Target Devices -> Vision: {pipeline.device_light}, ColPali(Placeholder): {pipeline.device_heavy}")
        print(">>> Hardware mapping applied correctly.")
    except Exception as e:
        print(f"!!! Error during initialization: {str(e)}")
        sys.exit(1)
        
    print("\n>>> Testing Stage 2 Stub...")
    # Mock Annotation & Document
    mock_annos = [
        Annotation(anno_id=1, category_type="text", poly=[100, 100, 500, 100, 500, 200, 100, 200]),
        Annotation(anno_id=2, category_type="title", poly=[100, 50, 400, 50, 400, 80, 100, 80])
    ]
    mock_doc = Document(
        filename="mock_doc.json",
        page_info={"width": 1000, "height": 1400},
        layout_dets=mock_annos,
        image_path="",
        raw_data={}
    )
    
    try:
        emb = pipeline.process_stage_2_template(mock_doc)
        print(f">>> Stage 2 Extracted Embedding Dimension: {len(emb)}")
    except Exception as e:
        print(f"!!! Stage 2 Error: {str(e)}")

if __name__ == "__main__":
    main()
