"""
Document Deduplication Pipeline Core Models & Vector DB Integration.

이 모듈은 Jina-CLIP-v2(Stage 1), DINOv2(Stage 2), Florence-2(Stage 3) 모델을 이용한 시각적/구조적 임베딩 추출 파이프라인과
Milvus Vector DB(Lite)와의 연동 인터페이스를 제공합니다.
"""

import io
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from PIL import Image, ImageDraw
import numpy as np
import torch
from transformers import AutoProcessor, AutoModelForCausalLM, AutoModel

try:
    from pymilvus import Collection, connections, FieldSchema, CollectionSchema, DataType, utility
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False

from .exceptions import PipelineBaseException, ModelInferenceError, VectorDBConnectionError
from .models import Document, Annotation

class DocumentDupPipeline:
    """3-Stage 문서 중복/템플릿 탐지 파이프라인 관리 엔진."""

    def __init__(self, milvus_uri: str = "./milvus_local.db") -> None:
        """
        환경별 자동 분기 (회사: 1080 Ti 2장, 집: RTX 5070 Ti 1장)
        """
        num_gpus = torch.cuda.device_count()
        self.device_heavy = "cuda:0" if num_gpus > 0 else "cpu"
        self.device_light = "cuda:1" if num_gpus > 1 else self.device_heavy
        
        # GPU 종류에 따른 모델 데이터 타입 (dtype) 자동 결정
        # 1080 Ti(Pascal)는 FP16 연산이 비효율적/불안정하므로 FP32(float32) 강제 할당
        # 최신 RTX 5070 Ti(Ada) 등은 효율성을 위해 FP16(float16) 할당
        self.dtype = torch.float32
        if num_gpus > 0:
            gpu_name = torch.cuda.get_device_name(0).lower()
            if "1080" not in gpu_name:
                self.dtype = torch.float16
        
        self.dim_stage1 = 1024  # Jina-clip-v2 embedding dim
        self.dim_stage2 = 768  # dinov2_base output dimension
        self.dim_stage3 = 768  # dinov2_base output dimension
        
        self._init_models()
        self._connect_vector_db(milvus_uri)

    def _init_models(self) -> None:
        """비전 파운데이션 모델 지연 로딩 및 GPU 할당."""
        try:
            # Stage 1: Exact Match using Jina-CLIP-v2 (GPU 0)
            self.stage1_model = AutoModel.from_pretrained(
                "jinaai/jina-clip-v2", 
                trust_remote_code=True,
                torch_dtype=self.dtype
            )
            self.stage1_model = self.stage1_model.to(self.device_heavy).eval()

            # Stage 2 & 3: Template & Region Structure using DINOv2 (GPU 1)
            self.dino_processor = AutoProcessor.from_pretrained("facebook/dinov2-base")
            self.dino_model = AutoModel.from_pretrained("facebook/dinov2-base", torch_dtype=self.dtype)
            self.dino_model = self.dino_model.to(self.device_light).eval()

            # Stage 3: Region Object Detection using Florence-2 (GPU 1)
            self.flo_processor = AutoProcessor.from_pretrained("microsoft/Florence-2-base", trust_remote_code=True)
            
            # [FIX 1] device_map을 추가하여 로드 시점부터 바로 GPU에 안착 (Flash Attention 2 경고 해결)
            self.flo_model = AutoModelForCausalLM.from_pretrained(
                "microsoft/Florence-2-base", 
                trust_remote_code=True,
                attn_implementation="flash_attention_2",
                torch_dtype=self.dtype,
                device_map=self.device_light
            )
            self.flo_model.eval()
            
        except Exception as e:
            raise ModelInferenceError(f"Failed to load vision models: {str(e)}")

    def _connect_vector_db(self, uri: str) -> None:
        """Milvus DB 연결 및 3-Stage Collection 보장."""
        if not MILVUS_AVAILABLE:
            print("pymilvus is not installed. VectorDB connectivity will be bypassed.")
            self.exact_col = None
            self.template_col = None
            self.region_col = None
            return
            
        try:
            # 로컬 테스트를 위해 URI 기반 접속으로 통일
            connections.connect(alias="default", uri=uri)
            
            # --- Stage 1 Collection (Exact) ---
            fields_s1 = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim_stage1)
            ]
            self.exact_col = Collection(name="stage1_exact", schema=CollectionSchema(fields_s1))
            self._create_index_if_not_exists(self.exact_col)
            
            # --- Stage 2 Collection (Template) ---
            fields_s2 = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim_stage2)
            ]
            self.template_col = Collection(name="stage2_templates", schema=CollectionSchema(fields_s2))
            self._create_index_if_not_exists(self.template_col)
            
            # --- Stage 3 Collection (Region) ---
            fields_s3 = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="label", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim_stage3)
            ]
            self.region_col = Collection(name="stage3_regions", schema=CollectionSchema(fields_s3))
            self._create_index_if_not_exists(self.region_col)
            
        except Exception as e:
            raise VectorDBConnectionError(f"Milvus connection/setup failed: {str(e)}")

    def _create_index_if_not_exists(self, collection: Any) -> None:
        """
        명시적 인덱스 이름 부여 및 Milvus Lite 호환 인덱스(FLAT) 적용
        """
        index_name = "vector_index"
        
        if len(collection.indexes) == 0:
            # [FIX 2] HNSW 대신 Milvus Lite에서 지원하는 FLAT을 사용
            index_params = {
                "metric_type": "COSINE",
                "index_type": "FLAT",
                "params": {}
            }
            collection.create_index(
                field_name="embedding", 
                index_params=index_params,
                index_name=index_name
            )
        collection.load()

    def process_stage_1_exact(self, doc_id: str, image: Image.Image) -> List[float]:
        """
        Stage 1: 이미지/텍스트 통합 임베딩을 통한 Exact Match 추출 (Jina-CLIP-v2).
        Cosine Similarity 0.98 이상 판단 용도의 고정밀 통합 특징 추출.
        """
        try:
            with torch.no_grad():
                # Jina-CLIP-v2 encode_image 메서드 활용
                emb_tensor = self.stage1_model.encode_image([image])
                embedding = (emb_tensor / np.linalg.norm(emb_tensor, axis=1, keepdims=True))[0].tolist()
            
            if self.exact_col is not None:
                self.exact_col.insert([{"doc_id": doc_id, "embedding": embedding}])
                
            return embedding
        except Exception as e:
            raise ModelInferenceError(f"Stage 1 Processing Error: {str(e)}")

    def process_stage_2_template(self, document: Document) -> List[float]:
        """
        Stage 2: 파싱된 레이아웃(Bounding Box)의 구조만으로 템플릿 임베딩 추출.
        텍스트를 빈 상자로 렌더링하여 내용의 영향을 완전히 배제합니다.
        """
        try:
            doc_id = getattr(document, 'filename', 'unknown_doc')
            page_info = getattr(document, 'page_info', {})
            page_width = page_info.get("width", 1000)
            page_height = page_info.get("height", 1400)
            
            canvas_size = 512
            img = Image.new("RGB", (canvas_size, canvas_size), color="white")
            draw = ImageDraw.Draw(img)
            
            # 카테고리별로 구별되는 색상 부여로 구조 인식 극대화
            color_map = {
                "text": (220, 220, 220),       # Light Gray
                "title": (100, 100, 100),      # Dark Gray
                "table": (173, 216, 230),      # Light Blue
                "figure": (144, 238, 144),     # Light Green
                "image": (144, 238, 144),
                "list": (200, 200, 200)
            }

            for ann in document.layout_dets:
                if getattr(ann, 'ignore', False): continue
                
                poly = getattr(ann, 'poly', [])
                if not poly or len(poly) < 4: continue
                
                x_coords = poly[0::2]
                y_coords = poly[1::2]
                
                if not x_coords or not y_coords: continue
                
                x1, y1, x2, y2 = min(x_coords), min(y_coords), max(x_coords), max(y_coords)

                nx1 = (x1 / page_width) * canvas_size
                ny1 = (y1 / page_height) * canvas_size
                nx2 = (x2 / page_width) * canvas_size
                ny2 = (y2 / page_height) * canvas_size
                
                cat_type = getattr(ann, 'category_type', 'unknown').lower()
                color = color_map.get(cat_type, (200, 200, 200))
                draw.rectangle([nx1, ny1, nx2, ny2], fill=color)

            inputs = self.dino_processor(images=img, return_tensors="pt").to(self.device_light)
            if "pixel_values" in inputs:
                inputs["pixel_values"] = inputs["pixel_values"].to(self.dtype)
            
            with torch.no_grad():
                features = self.dino_model(**inputs)
                cls_embedding = features.last_hidden_state[:, 0, :].squeeze(0).float().cpu().numpy()
                embedding = (cls_embedding / (np.linalg.norm(cls_embedding) + 1e-6)).tolist()
            
            if self.template_col is not None:
                self.template_col.insert([{"doc_id": doc_id, "embedding": embedding}])
            
            return embedding
        except Exception as e:
            raise ModelInferenceError(f"Stage 2 Processing Error: {str(e)}")

    def process_stage_2_image(self, doc_id: str, image: Image.Image) -> List[float]:
        """Stage 2: 이미지 원본에서 DINOv2 특징 추출 (검색용)"""
        try:
            inputs = self.dino_processor(images=image, return_tensors="pt").to(self.device_light)
            if "pixel_values" in inputs:
                inputs["pixel_values"] = inputs["pixel_values"].to(self.dtype)
            
            with torch.no_grad():
                features = self.dino_model(**inputs)
                cls_embedding = features.last_hidden_state[:, 0, :].squeeze(0).float().cpu().numpy()
                embedding = (cls_embedding / (np.linalg.norm(cls_embedding) + 1e-6)).tolist()
            
            return embedding
        except Exception as e:
            raise ModelInferenceError(f"Stage 2 Image Processing Error: {str(e)}")

    def process_stage_3_region(self, doc_id: str, image: Image.Image) -> List[Dict[str, Any]]:
        """
        Stage 3: Florence-2로 표/서명/도장 탐지 후 크롭, DINOv2 임베딩 저장.
        """
        try:
            task_prompt = "<OD>"
            inputs = self.flo_processor(text=task_prompt, images=image, return_tensors="pt").to(self.device_light)
            if "pixel_values" in inputs:
                inputs["pixel_values"] = inputs["pixel_values"].to(self.dtype)
            
            with torch.no_grad():
                generated_ids = self.flo_model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=1024,
                    num_beams=3
                )
            
            generated_text = self.flo_processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed_answer = self.flo_processor.post_process_generation(
                generated_text, task=task_prompt, image_size=(image.width, image.height)
            )
            
            od_results = parsed_answer.get(task_prompt, {})
            
            # Florence-2 출력 포맷 방어 로직 (딕셔너리가 아닌 예외 상황 필터링)
            if not isinstance(od_results, dict):
                return []
                
            bboxes = od_results.get("bboxes", [])
            labels = od_results.get("labels", [])
            
            region_results = []
            target_labels = {"signature", "stamp", "table"}
            
            for bbox, label in zip(bboxes, labels):
                bbox = [max(0, bbox[0]), max(0, bbox[1]), min(image.width, bbox[2]), min(image.height, bbox[3])]
                
                if label.lower() in target_labels and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                    crop_img = image.crop(tuple(bbox))
                    
                    dino_inputs = self.dino_processor(images=crop_img, return_tensors="pt").to(self.device_light)
                    if "pixel_values" in dino_inputs:
                        dino_inputs["pixel_values"] = dino_inputs["pixel_values"].to(self.dtype)
                    
                    with torch.no_grad():
                        feats = self.dino_model(**dino_inputs)
                        region_emb = feats.last_hidden_state[:, 0, :].squeeze(0).float().cpu().numpy()
                        region_emb = (region_emb / (np.linalg.norm(region_emb) + 1e-6)).tolist()
                        
                    if self.region_col is not None:
                        self.region_col.insert([{
                            "doc_id": doc_id, 
                            "label": label.lower(), 
                            "embedding": region_emb
                        }])
                        
                    region_results.append({
                        "label": label.lower(),
                        "embedding": region_emb,
                        "bbox": bbox
                    })
                    
            return region_results
        except Exception as e:
            raise ModelInferenceError(f"Stage 3 Processing Error: {str(e)}")

    def _search_collection(self, collection, embedding, top_k=5) -> List[Dict[str, Any]]:
        """내부용: 일반적인 Milvus 컬렉션 검색 로직 (Milvus-Lite 전용)"""
        if collection is None:
            return []
        
        # Milvus Lite에서는 FLAT 인덱스를 사용하므로 nprobe 설정 등은 필요 없음
        search_params = {"metric_type": "COSINE", "params": {}}
        results = collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["doc_id"]
        )
        
        hits = []
        if len(results) > 0:
            for hit in results[0]:
                hits.append({
                    "doc_id": hit.entity.get("doc_id"),
                    "score": hit.distance
                })
        return hits

    def get_batch_clusters(self, stage: int = 1, threshold: float = 0.95) -> List[List[str]]:
        """
        현재 Milvus에 저장된 배치 전체를 대상으로 자가 유사도 조사를 수행하여 클러스터를 형성함.
        유니온-파인드(Union-Find) 알고리즘을 활용하여 연결 요소(Connected Components)를 찾음.
        """
        # 1. 컬렉션 로드 및 모든 데이터 가져오기
        col = self.exact_col if stage == 1 else self.template_col
        if col is None: return []
        
        # 전체 데이터 쿼리 (doc_id, embedding)
        # Milvus Lite / Pymilvus query API 활용
        # limit=None을 지정하여 전체 데이터를 가져옴 (1000건 제한 우회)
        res = col.query(expr="id >= 0", output_fields=["doc_id", "embedding"], limit=16384)
        if not res: return []
        
        num_raw = len(res)
        
        # doc_id 기준으로 고유화 (동일 ID가 여러 벤더/페이지로 들어온 경우 첫 번째만 사용)
        unique_res = {}
        for r in res:
            did = r['doc_id']
            if did not in unique_res:
                unique_res[did] = r['embedding']
        
        doc_ids = list(unique_res.keys())
        embeddings = np.array(list(unique_res.values()), dtype=np.float32)
        num_docs = len(doc_ids)
        
        # 2. 유사도 행렬 계산 (코사인 유사도)
        # (N, D) @ (D, N) -> (N, N)
        # Milvus가 아닌 로컬에서 수행 (수천~만건 정도까지는 가능)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9
        norm_embeddings = embeddings / norms
        sim_matrix = np.matmul(norm_embeddings, norm_embeddings.T)
        
        # 3. 유니온-파인드로 그룹화
        parent = list(range(num_docs))
        def find(i):
            if parent[i] == i: return i
            parent[i] = find(parent[i])
            return parent[i]
            
        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j
        
        # 유사도가 Threshold 이상인 쌍을 합침
        # 대칭 행렬이므로 상삼각 행렬만 순회
        ii, jj = np.where(sim_matrix > threshold)
        for i, j in zip(ii, jj):
            if i < j:
                union(i, j)
                
        # 4. 결과 정리
        clusters_map = defaultdict(list)
        for i in range(num_docs):
            root = find(i)
            clusters_map[root].append(doc_ids[i])
            
        return list(clusters_map.values())

    def search_stage_1(self, image: Image.Image, top_k=5) -> List[Dict[str, Any]]:
        """Stage 1: 전체 이미지 유사도 검색 (Jina-CLIP)"""
        emb = self.process_stage_1_exact("SEARCH_QUERY", image)
        return self._search_collection(self.exact_col, emb, top_k)

    def search_stage_2(self, image: Image.Image, top_k=5) -> List[Dict[str, Any]]:
        """Stage 2: 템플릿 유사도 검색 (DINOv2)"""
        emb = self.process_stage_2_image("SEARCH_QUERY", image)
        return self._search_collection(self.template_col, emb, top_k)

    def search_stage_3(self, image: Image.Image, label: str = None, top_k=10) -> List[Dict[str, Any]]:
        """Stage 3: 특정 영역(서명/직인 등) 유사도 검색"""
        # Florence-2로 영역 탐지
        regions = self.process_stage_3_region("SEARCH_QUERY", image)
        if not regions:
            return []
            
        # label이 지정된 경우 해당 라벨 중 가장 큰 영역 선택, 아니면 전체 중 첫 번째
        target_region = None
        if label:
            label = label.lower()
            filtered = [r for r in regions if r["label"] == label]
            if filtered:
                target_region = filtered[0] # 우선 첫 번째 (보통 가장 큰 것부터 탐지됨)
        
        if not target_region:
            target_region = regions[0]

        if self.region_col is None: return []

        search_params = {"metric_type": "COSINE", "params": {}}
        # label 필터링 추가
        expr = f"label == '{target_region['label']}'"
        
        results = self.region_col.search(
            data=[target_region["embedding"]],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["doc_id", "label"]
        )
        
        hits = []
        if len(results) > 0:
            for hit in results[0]:
                hits.append({
                    "doc_id": hit.entity.get("doc_id"),
                    "label": hit.entity.get("label"),
                    "score": hit.distance
                })
        return hits