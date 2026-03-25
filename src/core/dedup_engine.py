"""
Document Deduplication Pipeline Core Models & Vector DB Integration.

이 모듈은 ColPali, DINOv2, Florence-2 모델을 이용한 시각적/구조적 임베딩 추출 기능과
Milvus Vector DB와의 연동 인터페이스를 제공합니다.
"""

import io
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw
import numpy as np
import torch
from transformers import AutoProcessor, AutoModelForCausalLM, AutoModel

try:
    from pymilvus import Collection, connections, FieldSchema, CollectionSchema, DataType, utility
except ImportError:
    pass

from .exceptions import PipelineBaseException, ModelInferenceError, VectorDBConnectionError
from .models import Document, Annotation

class DocumentDupPipeline:
    """3-Stage 문서 중복/템플릿 탐지 파이프라인 관리 엔진."""

    def __init__(self, milvus_host: str = "localhost", milvus_port: str = "19530") -> None:
        """
        초기화 시 하드웨어(1080 Ti 2장) 설문을 고려하여 모델들을 메모리에 로드하고, Milvus 연결을 설정합니다.
        
        Args:
            milvus_host (str): Milvus 호스트 주소.
            milvus_port (str): Milvus 포트 번호.
        """
        # 1080 Ti 2장 환경 (GPU 0: ColPali / GPU 1: DINOv2 & Florence-2)
        self.device_heavy = "cuda:0" if torch.cuda.device_count() > 0 else "cpu"
        self.device_light = "cuda:1" if torch.cuda.device_count() > 1 else self.device_heavy
        
        self._init_models()
        self._connect_vector_db(milvus_host, milvus_port)

    def _init_models(self) -> None:
        """비전 파운데이션 모델들을 지연 로딩합니다."""
        try:
            # Stage 2 & 3: DINOv2 for Structure & Region Embedding (GPU 1 할당)
            self.dino_processor = AutoProcessor.from_pretrained("facebook/dinov2-base")
            self.dino_model = AutoModel.from_pretrained("facebook/dinov2-base")
            # 1080ti 지원을 위해 fp16으로 변환하여 로드 (속도보다 VRAM 최적화)
            self.dino_model = self.dino_model.half().to(self.device_light).eval()

            # Stage 3: Florence-2 for Object Detection (GPU 1 할당)
            self.flo_processor = AutoProcessor.from_pretrained("microsoft/Florence-2-base", trust_remote_code=True)
            self.flo_model = AutoModelForCausalLM.from_pretrained("microsoft/Florence-2-base", trust_remote_code=True)
            self.flo_model = self.flo_model.half().to(self.device_light).eval()
            
            # NOTE: ColPali (Stage 1)는 별도 구현이 필요하나 아키텍처 상 이곳에 통합 가능.
            
        except Exception as e:
            raise ModelInferenceError(f"Failed to load models: {str(e)}")

    def _connect_vector_db(self, host: str, port: str) -> None:
        """Milvus에 연결하고 필요한 Collection들을 보장합니다."""
        try:
            if 'connections' not in globals():
                print("pymilvus is not installed. VectorDB connectivity will be bypassed.")
                self.template_col = None
                return
                
            connections.connect(alias="default", host=host, port=port)
            self.dim_dino = 768  # dinov2_base output dimension
            
            # Stage 2 Collection Example
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim_dino)
            ]
            schema = CollectionSchema(fields=fields, description="Stage 2: Template Structure Embeddings")
            self.template_col = Collection(name="stage2_templates", schema=schema)
            
            # 인덱스가 없다면 생성 (Cosine 유사도 기준)
            if not self.template_col.has_index():
                index_params = {
                    "metric_type": "COSINE",
                    "index_type": "HNSW",
                    "params": {"M": 8, "efConstruction": 64}
                }
                self.template_col.create_index(field_name="embedding", index_params=index_params)
            self.template_col.load()
            
        except Exception as e:
            raise VectorDBConnectionError(f"Milvus connection/setup failed: {str(e)}")

    def process_stage_2_template(self, document: Document) -> List[float]:
        """
        Stage 2: 파싱된 Document 객체 내 Annotation 정보를 토대로 
        구조 이미지를 렌더링하고 DINOv2 임베딩을 추출합니다.

        Args:
            document (Document): 분석할 문서 데이터 클래스 객체.

        Returns:
            List[float]: 모델이 추출한 템플릿 임베딩 벡터 (768-dim)
            
        Raises:
            ModelInferenceError: 임베딩 추출 실패 시.
        """
        try:
            doc_id = document.filename
            page_info = document.page_info
            page_width = page_info.get("width", 1000)  # fallback
            page_height = page_info.get("height", 1400) # fallback
            
            canvas_size = 512
            img = Image.new("RGB", (canvas_size, canvas_size), color="white")
            draw = ImageDraw.Draw(img)
            
            color_map = {
                "text": (200, 200, 200),
                "title": (100, 100, 100),
                "table": (173, 216, 230),
                "figure": (144, 238, 144),
                "image": (144, 238, 144)
            }

            for ann in document.layout_dets:
                if getattr(ann, 'ignore', False):
                    continue
                    
                obj_type = ann.category_type.lower()
                poly = ann.poly
                
                if not poly or len(poly) < 4:
                    continue
                    
                # Bounding Box 치환 (K-Omnidoc poly 지원)
                x_coords = poly[0::2]
                y_coords = poly[1::2]
                x1, y1, x2, y2 = min(x_coords), min(y_coords), max(x_coords), max(y_coords)

                # Coordinate Normalization -> Scale to canvas
                nx1 = (x1 / page_width) * canvas_size
                ny1 = (y1 / page_height) * canvas_size
                nx2 = (x2 / page_width) * canvas_size
                ny2 = (y2 / page_height) * canvas_size
                
                color = color_map.get(obj_type, (200, 200, 200))
                draw.rectangle([nx1, ny1, nx2, ny2], fill=color)

            # DINOv2 임베딩 추출
            inputs = self.dino_processor(images=img, return_tensors="pt").to(self.device_light)
            inputs["pixel_values"] = inputs["pixel_values"].half()
            
            with torch.no_grad():
                features = self.dino_model(**inputs)
                cls_embedding = features[0].float().cpu().numpy()
                embedding = (cls_embedding / np.linalg.norm(cls_embedding)).tolist()
            
            # Vector DB에 Insert
            if self.template_col is not None:
                self.template_col.insert([
                    {"doc_id": doc_id, "embedding": embedding}
                ])
            
            return embedding
            
        except Exception as e:
            raise ModelInferenceError(f"Stage 2 Processing Error: {str(e)}")

    def process_stage_3_region(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        Stage 3: Florence-2를 통해 특정 영억을 탐지하고, 크롭한 뒤 임베딩을 추출합니다.

        Args:
            image (Image.Image): 원본 전체 문서 이미지.

        Returns:
            List[Dict[str, Any]]: 식별된 객체 타입과 해당 객체의 임베딩 리스트.
        """
        try:
            task_prompt = "<OD>"
            inputs = self.flo_processor(text=task_prompt, images=image, return_tensors="pt").to(self.device_light)
            inputs["pixel_values"] = inputs["pixel_values"].half()
            
            with torch.no_grad():
                generated_ids = self.flo_model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=1024,
                    num_beams=3
                )
            
            generated_text = self.flo_processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed_answer = self.flo_processor.post_process_generation(generated_text, task=task_prompt, image_size=(image.width, image.height))
            
            od_results = parsed_answer.get(task_prompt, {})
            bboxes = od_results.get("bboxes", [])
            labels = od_results.get("labels", [])
            
            region_results = []
            target_labels = {"signature", "stamp", "table"}
            
            for bbox, label in zip(bboxes, labels):
                if label.lower() in target_labels:
                    crop_img = image.crop(tuple(bbox))
                    
                    dino_inputs = self.dino_processor(images=crop_img, return_tensors="pt").to(self.device_light)
                    dino_inputs["pixel_values"] = dino_inputs["pixel_values"].half()
                    
                    with torch.no_grad():
                        feats = self.dino_model(**dino_inputs)
                        region_emb = feats[0].float().cpu().numpy()
                        region_emb = (region_emb / np.linalg.norm(region_emb)).tolist()
                        
                    region_results.append({
                        "label": label,
                        "embedding": region_emb,
                        "bbox": bbox
                    })
                    
            return region_results

        except Exception as e:
            raise ModelInferenceError(f"Stage 3 Processing Error: {str(e)}")
