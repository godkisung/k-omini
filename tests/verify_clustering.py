import os
import sys
import numpy as np
from collections import defaultdict
from src.core.dedup_engine import DocumentDupPipeline
from src.sampling.sampler import SimilarityAwareSampler, get_doc_type

def verify_clustering_integrity():
    """
    배치 데이터의 클러스터링 무결성 및 다양성 샘플링 로직을 검증합니다.
    """
    print("🚀 [DEDUPLICATION VERIFICATION] 클러스터링 및 샘플링 무결성 검사 시작...")
    
    try:
        # 1. 엔진 초기화
        engine = DocumentDupPipeline()
        
        # 2. 실데이터 통계 확인
        print("📊 1. Milvus DB 상태 점검...")
        # num_entities는 인덱스 동기화 상태에 따라 다를 수 있으므로 직접 쿼리 카운트 확인
        total_res = engine.exact_col.query(expr="id >= 0", output_fields=["doc_id"], limit=16384)
        total_count = len(total_res)
        unique_ids = set(r['doc_id'] for r in total_res)
        
        print(f"   - 전체 레코드 수: {total_count}개")
        print(f"   - 고유 문서 ID 수: {len(unique_ids)}개")
        
        # 3. 클러스터링 실행
        print("\n🔍 2. 배치 내 자가 유사도 분석 및 클러스터링 실행 중...")
        # Stage 1 (Global Vision) 기반 클러스터링 (기본값 Threshold 0.95)
        clusters = engine.get_batch_clusters(stage=1, threshold=0.95)
        
        num_clusters = len(clusters)
        docs_in_clusters = sum(len(c) for c in clusters)
        duplicates_count = sum(len(c) - 1 for c in clusters if len(c) > 1)
        
        print(f"   - 발견된 유사 그룹(Cluster) 수: {num_clusters}개")
        print(f"   - 클러스터링 포함 문서 수: {docs_in_clusters}개")
        print(f"   - 배제 대상 중복 문서 수: {duplicates_count}개")
        
        # 4. 다양성 샘플링 연동 테스트
        print("\n🎲 3. 중복 제거 기반 다양성 샘플링 시뮬레이션...")
        all_file_ids = [r['doc_id'] for r in total_res]
        
        sampler = SimilarityAwareSampler(sample_rate=0.2, min_per_type=1, seed=42)
        # sample_with_diversity internally calls get_batch_clusters if needed, 
        # but here we pass the pre-calculated clusters for testing.
        result = sampler.sample_with_diversity(all_file_ids, clusters, batch_name="VERIFICATION_TEST")
        
        print(f"   - 필터링 전 후보군: {len(set(all_file_ids))}개 (고유 ID 기준)")
        print(f"   - 중복 필터링 후 대상: {len(set(all_file_ids)) - duplicates_count}개")
        print(f"   - 최종 추출된 샘플 수: {result.total_count}개")
        
        # 5. 무결성 체크 (Intersection Test)
        # 필터링 후 남은 문서들이 실제로 대표(Representative)들인지 확인
        representatives = set(c[0] for c in clusters)
        sampled_set = set(result.sampled_files)
        
        # 모든 샘플은 대표 목록에 포함되어야 함
        is_integrity_ok = sampled_set.issubset(representatives)
        
        if is_integrity_ok:
            print("\n✅ [SUCCESS] 교집합 정합성 검증 완료: 모든 샘플이 그룹 대표 문서에서 추출되었습니다.")
        else:
            invalid_samples = sampled_set - representatives
            print(f"\n❌ [FAILURE] 정합성 오류 발견: {len(invalid_samples)}개의 샘플이 대표 문서가 아닙니다.")
            print(f"   - 위반 사례: {list(invalid_samples)[:3]}")

    except Exception as e:
        print(f"\n❌ [ERROR] 검증 중 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_clustering_integrity()
