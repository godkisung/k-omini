"""층화 랜덤 샘플링 모듈.

파일명 prefix(CB, GR, RT 등)를 기준으로 문서 유형별 층(stratum)을 구성하고,
각 층에서 동일 비율로 랜덤 샘플을 추출합니다.
"""

import math
import os
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# K-Omnidoc 문서 유형 코드 → 전체 이름 매핑
DOC_TYPE_NAMES: dict[str, str] = {
    "CB": "기업보고서",
    "EX": "문제집",
    "ET": "기타",
    "GR": "정부보고서",
    "IR": "IR자료",
    "IT": "소개자료",
    "LT": "강의자료",
    "MG": "매뉴얼/가이드",
    "PB": "간행물",
    "PP": "논문",
    "PR": "발표자료",
    "RP": "리포트",
    "RT": "보고서",
    "SK": "SKON문서",
}

# 알려진 문서 유형 코드 집합
KNOWN_DOC_TYPES = set(DOC_TYPE_NAMES.keys())


def get_doc_type(filename: str) -> str:
    """파일명에서 문서 유형 코드를 추출합니다.

    Args:
        filename: JSON 파일명 (예: CB00001_00001_기업보고서_...json)

    Returns:
        문서 유형 코드 (예: 'CB'). 알 수 없는 경우 'ETC' 반환.
    """
    basename = os.path.basename(filename)
    prefix = basename[:2].upper()
    return prefix if prefix in KNOWN_DOC_TYPES else "ETC"


@dataclass
class SamplingResult:
    """샘플링 실행 결과를 담는 데이터 클래스."""

    batch_name: str
    sample_rate: float
    min_per_type: int
    seed: int
    sampled_files: list[str] = field(default_factory=list)
    type_breakdown: dict[str, dict] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        """전체 샘플 수."""
        return len(self.sampled_files)


class StratifiedSampler:
    """문서 유형별 층화 랜덤 샘플러.

    각 층(문서 유형)에서 ``max(min_per_type, ceil(층_크기 × sample_rate))``
    개수만큼 랜덤으로 추출합니다.

    Args:
        sample_rate: 각 층에서 추출할 비율 (0.0 ~ 1.0). 기본값 0.15 (15%).
        min_per_type: 층당 최솟값. 소수 유형도 최소 이 수만큼 포함됩니다.
                      단, 층의 전체 파일 수보다 클 수 없습니다.
        seed: 난수 시드. 동일한 시드로 재실행 시 동일한 결과를 보장합니다.
    """

    def __init__(
        self,
        sample_rate: float = 0.15,
        min_per_type: int = 2,
        seed: Optional[int] = None,
    ) -> None:
        if not (0.0 < sample_rate <= 1.0):
            raise ValueError(f"sample_rate는 (0, 1] 범위여야 합니다: {sample_rate}")
        if min_per_type < 1:
            raise ValueError(f"min_per_type는 1 이상이어야 합니다: {min_per_type}")

        self.sample_rate = sample_rate
        self.min_per_type = min_per_type
        self.seed = seed

    def sample(self, file_paths: list[str], batch_name: str = "") -> SamplingResult:
        """주어진 파일 목록에서 층화 랜덤 샘플을 추출합니다.

        Args:
            file_paths: JSON 파일 경로 목록.
            batch_name: 배치 이름 (캐시 파일명 생성에 사용).

        Returns:
            SamplingResult 객체.
        """
        rng = random.Random(self.seed)

        # 1. 문서 유형별로 그룹화
        groups: dict[str, list[str]] = defaultdict(list)
        for fp in file_paths:
            doc_type = get_doc_type(fp)
            groups[doc_type].append(fp)

        sampled_files: list[str] = []
        type_breakdown: dict[str, dict] = {}

        # 2. 층별로 샘플 추출
        for doc_type, files in sorted(groups.items()):
            total = len(files)
            n_sample = max(
                min(self.min_per_type, total),  # 전체보다 클 수 없음
                math.ceil(total * self.sample_rate),
            )
            n_sample = min(n_sample, total)  # 샘플이 전체를 초과하지 않도록

            chosen = rng.sample(files, n_sample)
            sampled_files.extend(chosen)

            type_breakdown[doc_type] = {
                "name": DOC_TYPE_NAMES.get(doc_type, doc_type),
                "total": total,
                "sampled": n_sample,
                "rate": round(n_sample / total * 100, 1),
            }

        # 3. 최종 순서 셔플 (유형 순서를 무작위로)
        rng.shuffle(sampled_files)

        return SamplingResult(
            batch_name=batch_name,
            sample_rate=self.sample_rate,
            min_per_type=self.min_per_type,
            seed=self.seed if self.seed is not None else -1,
            sampled_files=[os.path.basename(f) for f in sampled_files],
            type_breakdown=type_breakdown,
        )


class SimilarityAwareSampler(StratifiedSampler):
    """유사도 기반 중복 제거 기능이 강화된 샘플러.
    
    유사한 문서 묶음(Cluster)이 주어지면, 각 묶음에서 대표 하나만 남기고 나머지는 
    샘플링 대상에서 제외하여 데이터의 다양성을 확보합니다.
    """

    def sample_with_diversity(
        self, 
        file_paths: list[str], 
        clusters: list[list[str]], 
        batch_name: str = ""
    ) -> SamplingResult:
        """중복 그룹을 고려하여 다양성이 확보된 샘플을 추출합니다.
        
        Args:
            file_paths: 전체 JSON 파일 경로 목록.
            clusters: 유사 문서 ID(파일명)들의 리스트 (엔진의 get_batch_clusters 결과).
            batch_name: 배치 이름.
        """
        # 1. 중복 제거 맵 구성
        # 각 파일이 어떤 대표 파일로 매핑되는지 정의 (클러스터의 첫 번째 요소를 대표로 가정)
        repr_map = {}
        duplicates_to_skip = set()
        
        for cluster in clusters:
            if len(cluster) > 1:
                representative = cluster[0]
                for doc_id in cluster[1:]:
                    repr_map[doc_id] = representative
                    duplicates_to_skip.add(doc_id)
        
        # 2. 필터링된 파일 목록 생성
        # 중복으로 판명된 파일은 제외하고 대표들만 남김
        diverse_file_paths = []
        for fp in file_paths:
            fname = os.path.basename(fp)
            if fname not in duplicates_to_skip:
                diverse_file_paths.append(fp)
        
        # 3. 기존 층화 샘플링 수행
        result = self.sample(diverse_file_paths, batch_name=batch_name)
        
        # 4. 결과에 중복 제거 통계 보완 (선택 사항: 나중에 UI에서 사용)
        # 여기서는 단순 샘플링 결과만 반환
        return result
