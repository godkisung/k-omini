"""샘플링 세션 파일 기반 캐시 관리 모듈.

앱 재시작 시에도 검수 진행 상태를 유지하기 위해 JSON 파일로 상태를 영속화합니다.
캐시 파일 경로: .sampling_cache/{배치명}_{날짜}.json
"""

import json
import os
from datetime import datetime
from typing import Optional


# 캐시 디렉토리 위치 (프로젝트 루트 기준)
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
CACHE_DIR = os.path.join(_PROJECT_ROOT, ".sampling_cache")

# 기본 검수 결과 구조
_DEFAULT_REVIEW_ENTRY: dict = {
    "is_error": False,
    "error_types": [],
    "memo": "",
    "reviewed": False,
}


class SamplingCache:
    """샘플링 세션 캐시를 관리합니다.

    캐시 파일은 ``{CACHE_DIR}/{batch_name}_{date}.json`` 형태로 저장됩니다.

    Args:
        batch_name: 납품 배치 폴더명 (예: 'Alchera_delivery_P1_260227').
        date: 캐시 날짜 (기본값: 오늘, 'YYYY-MM-DD' 형식).
    """

    def __init__(self, batch_name: str, date: Optional[str] = None) -> None:
        self.batch_name = batch_name
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._path = self._build_path(batch_name, self.date)
        self._data: dict = {}

    # ------------------------------------------------------------------
    # 경로 유틸
    # ------------------------------------------------------------------

    @staticmethod
    def _build_path(batch_name: str, date: str) -> str:
        """캐시 파일 경로를 반환합니다."""
        filename = f"{batch_name}_{date}.json"
        return os.path.join(CACHE_DIR, filename)

    # ------------------------------------------------------------------
    # 캐시 존재 여부 확인
    # ------------------------------------------------------------------

    def exists(self) -> bool:
        """현재 배치+날짜에 해당하는 캐시 파일이 존재하는지 확인합니다."""
        return os.path.exists(self._path)

    @classmethod
    def list_all(cls) -> list[dict]:
        """저장된 모든 캐시 파일 정보를 반환합니다.

        Returns:
            각 캐시의 요약 정보 리스트.
            예: [{"batch": "...", "date": "...", "path": "...", "progress": "23/78"}]
        """
        os.makedirs(CACHE_DIR, exist_ok=True)
        results = []
        for fname in sorted(os.listdir(CACHE_DIR)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(CACHE_DIR, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
                total = len(data.get("sampled_files", []))
                reviewed = sum(
                    1
                    for v in data.get("review_results", {}).values()
                    if v.get("reviewed", False)
                )
                results.append(
                    {
                        "batch": data.get("batch", ""),
                        "date": data.get("date", ""),
                        "path": fpath,
                        "total": total,
                        "reviewed": reviewed,
                        "progress": f"{reviewed}/{total}",
                        "done": reviewed == total and total > 0,
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return results

    # ------------------------------------------------------------------
    # 로드 / 저장 / 삭제
    # ------------------------------------------------------------------

    def load(self) -> dict:
        """캐시 파일을 로드하여 내부 데이터에 반영합니다.

        Returns:
            로드된 캐시 데이터.

        Raises:
            FileNotFoundError: 캐시 파일이 존재하지 않을 때.
        """
        if not self.exists():
            raise FileNotFoundError(f"캐시 파일이 없습니다: {self._path}")
        with open(self._path, encoding="utf-8") as f:
            self._data = json.load(f)
        return self._data

    def save(self) -> None:
        """현재 내부 데이터를 캐시 파일에 저장합니다."""
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def delete(self) -> None:
        """캐시 파일을 삭제합니다."""
        if self.exists():
            os.remove(self._path)
        self._data = {}

    # ------------------------------------------------------------------
    # 초기화 (새 샘플링)
    # ------------------------------------------------------------------

    def init_from_sampling(
        self,
        sampled_files: list[str],
        sample_rate: float,
        min_per_type: int,
        seed: int,
        type_breakdown: dict,
    ) -> None:
        """새 샘플링 결과로 캐시를 초기화하고 즉시 저장합니다.

        Args:
            sampled_files: 샘플링된 파일명 목록 (basename).
            sample_rate: 사용된 샘플링 비율.
            min_per_type: 사용된 최솟값.
            seed: 사용된 난수 시드.
            type_breakdown: 유형별 샘플 수 내역.
        """
        self._data = {
            "batch": self.batch_name,
            "date": self.date,
            "sample_rate": sample_rate,
            "min_per_type": min_per_type,
            "seed": seed,
            "sampled_files": sampled_files,
            "type_breakdown": type_breakdown,
            "review_results": {
                fname: dict(_DEFAULT_REVIEW_ENTRY) for fname in sampled_files
            },
        }
        self.save()

    # ------------------------------------------------------------------
    # 검수 결과 접근자
    # ------------------------------------------------------------------

    @property
    def sampled_files(self) -> list[str]:
        """샘플링된 파일명 목록."""
        return self._data.get("sampled_files", [])

    @property
    def review_results(self) -> dict:
        """현재까지의 검수 결과 딕셔너리."""
        return self._data.get("review_results", {})

    @property
    def type_breakdown(self) -> dict:
        """유형별 샘플 수 내역."""
        return self._data.get("type_breakdown", {})

    def get_result(self, filename: str) -> dict:
        """특정 파일의 검수 결과를 반환합니다."""
        return self._data.get("review_results", {}).get(
            filename, dict(_DEFAULT_REVIEW_ENTRY)
        )

    def update_result(
        self,
        filename: str,
        is_error: bool,
        error_types: list[str],
        memo: str,
    ) -> None:
        """특정 파일의 검수 결과를 업데이트하고 즉시 캐시에 저장합니다.

        Args:
            filename: 검수 대상 파일명 (basename).
            is_error: 오류 여부.
            error_types: 오류 유형 목록.
            memo: 검수자 메모.
        """
        if "review_results" not in self._data:
            self._data["review_results"] = {}
        self._data["review_results"][filename] = {
            "is_error": is_error,
            "error_types": error_types,
            "memo": memo,
            "reviewed": True,
        }
        self.save()

    # ------------------------------------------------------------------
    # 진행률 계산
    # ------------------------------------------------------------------

    def progress(self) -> tuple[int, int]:
        """(완료 수, 전체 수) 튜플을 반환합니다."""
        total = len(self.sampled_files)
        reviewed = sum(
            1
            for v in self.review_results.values()
            if v.get("reviewed", False)
        )
        return reviewed, total

    def next_unreviewed_idx(self) -> int:
        """아직 검수되지 않은 첫 번째 파일의 인덱스를 반환합니다.

        모두 완료됐으면 0을 반환합니다.
        """
        for i, fname in enumerate(self.sampled_files):
            result = self.review_results.get(fname, {})
            if not result.get("reviewed", False):
                return i
        return 0
