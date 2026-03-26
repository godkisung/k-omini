"""샘플링 설정 및 실행 Streamlit 페이지.

워크플로우:
    1. 납품 배치 선택
    2. 샘플링 파라미터 설정 (비율, 최솟값, 시드)
    3. 샘플링 실행 → 파일 기반 캐시 저장
    4. 검수 페이지(review_page)로 이동
"""

import os
from datetime import datetime

import streamlit as st

from src.config import get_delivery_batches, get_batch_dirs
from src.core.models import get_json_files
from src.sampling import StratifiedSampler
from src.sampling.cache_manager import SamplingCache


def sampling_page() -> None:
    """샘플링 페이지 메인 함수."""
    st.header("🎲 납품 데이터 샘플링")
    st.caption("층화 랜덤 샘플링으로 검수 대상을 선정합니다.")

    # ── 1. 기존 캐시 확인 ────────────────────────────────────────────────
    _render_existing_sessions()
    st.divider()

    # ── 2. 새 샘플링 설정 ────────────────────────────────────────────────
    st.subheader("🆕 새 검수 세션 시작")

    batches = get_delivery_batches()
    if not batches:
        st.error("❌ `data/` 폴더에 납품 배치가 없습니다. `Alchera_delivery_*` 또는 `Alchera_rework_*` 형태의 폴더를 확인하세요.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_batch = st.selectbox(
            "납품 배치 선택",
            options=batches,
            help="data/ 하위의 납품 배치 폴더",
        )
    with col2:
        today_str = datetime.now().strftime("%Y-%m-%d")
        session_date = st.text_input("검수 날짜", value=today_str)

    # ── 파라미터 설정 ──────────────────────────────────────────────────
    with st.expander("⚙️ 샘플링 파라미터", expanded=True):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            sample_rate = st.slider(
                "샘플링 비율 (%)",
                min_value=5, max_value=50, value=15, step=5,
                help="각 문서 유형에서 추출할 비율",
            ) / 100.0
        with col_b:
            min_per_type = st.number_input(
                "유형별 최솟값",
                min_value=1, max_value=10, value=2,
                help="소수 유형도 최소 이 수만큼 포함",
            )
        with col_c:
            default_seed = int(datetime.now().strftime("%Y%m%d"))
            seed = st.number_input(
                "난수 시드",
                min_value=1, value=default_seed,
                help="같은 시드면 동일한 결과. 날짜 기반 기본값 사용 권장.",
            )

        st.divider()
        use_dedup = st.toggle(
            "🛑 중복 문서 필터링 (다양성 확보)", 
            value=True,
            help="Milvus에 저장된 유사도 데이터를 활용하여, 중복/유사 문서는 대표 1개만 샘플링 대상에 포함합니다."
        )
        if use_dedup:
            dedup_threshold = st.slider("유사도 임계값", 0.80, 0.99, 0.95, 0.01, help="이 점수 이상이면 중복으로 간주합니다.")

    # ── 미리보기 ──────────────────────────────────────────────────────
    json_dir, img_dir = get_batch_dirs(selected_batch)
    if not os.path.isdir(json_dir):
        st.warning(f"⚠️ JSON 폴더를 찾을 수 없습니다: `{json_dir}`")
        return

    all_files = get_json_files(json_dir)
    if not all_files:
        st.warning("⚠️ 해당 배치에 JSON 파일이 없습니다.")
        return

    sampler = StratifiedSampler(
        sample_rate=sample_rate,
        min_per_type=min_per_type,
        seed=seed,
    )
    preview_result = sampler.sample(all_files, batch_name=selected_batch)

    with st.expander("📊 샘플링 미리보기", expanded=True):
        st.markdown(f"**전체:** {len(all_files)}개 → **샘플:** {preview_result.total_count}개")

        import pandas as pd
        breakdown_rows = []
        for dt, info in sorted(preview_result.type_breakdown.items()):
            breakdown_rows.append({
                "코드": dt,
                "유형명": info["name"],
                "전체": info["total"],
                "샘플": info["sampled"],
                "비율(%)": info["rate"],
            })

        if breakdown_rows:
            df = pd.DataFrame(breakdown_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ── 실행 버튼 ──────────────────────────────────────────────────────
    # 이미 같은 날짜 캐시가 있는지 확인
    cache = SamplingCache(batch_name=selected_batch, date=session_date)
    already_exists = cache.exists()

    if already_exists:
        st.warning(
            f"⚠️ 이미 `{selected_batch} / {session_date}` 세션이 존재합니다. "
            "실행하면 **기존 검수 데이터가 모두 삭제**됩니다."
        )

    btn_label = "🔄 재샘플링 (기존 삭제)" if already_exists else "🚀 샘플링 실행"
    if st.button(btn_label, type="primary", use_container_width=True):
        _run_sampling(
            cache=cache,
            all_files=all_files,
            sample_rate=sample_rate,
            min_per_type=int(min_per_type),
            seed=int(seed),
            batch_name=selected_batch,
            use_dedup=use_dedup,
            dedup_threshold=dedup_threshold if use_dedup else 0.95
        )


# ── 헬퍼 함수 ────────────────────────────────────────────────────────────────

def _render_existing_sessions() -> None:
    """저장된 기존 검수 세션 목록을 표시합니다."""
    sessions = SamplingCache.list_all()
    if not sessions:
        st.info("💡 저장된 검수 세션이 없습니다. 아래에서 새 세션을 시작하세요.")
        return

    st.subheader("📂 저장된 검수 세션")
    for s in sessions:
        done_icon = "✅" if s["done"] else "🔄"
        label = f"{done_icon} **{s['batch']}** ({s['date']})  — {s['progress']} 완료"

        with st.expander(label, expanded=not s["done"]):
            col1, col2 = st.columns([3, 1])
            with col1:
                progress_ratio = s["reviewed"] / s["total"] if s["total"] > 0 else 0.0
                st.progress(progress_ratio, text=f"{s['reviewed']} / {s['total']} 페이지 검수 완료")
            with col2:
                if st.button(
                    "▶️ 이어서 검수",
                    key=f"resume_{s['batch']}_{s['date']}",
                    use_container_width=True,
                ):
                    # session_state에 로드할 캐시 정보 기록 후 리다이렉트
                    st.session_state["active_cache_path"] = s["path"]
                    st.session_state["active_batch"] = s["batch"]
                    st.session_state["active_date"] = s["date"]
                    st.switch_page("pages/review_page.py")


def _run_sampling(
    cache: SamplingCache,
    all_files: list[str],
    sample_rate: float,
    min_per_type: int,
    seed: int,
    batch_name: str,
    use_dedup: bool = False,
    dedup_threshold: float = 0.95
) -> None:
    """샘플링을 실행하고 캐시에 저장합니다."""
    if cache.exists():
        cache.delete()

    from app_helpers import get_dedup_engine
    from src.sampling.sampler import SimilarityAwareSampler, StratifiedSampler

    if use_dedup:
        with st.spinner("📦 Milvus에서 배치 유사도 분석 및 클러스터링 중..."):
            try:
                engine = get_dedup_engine()
                # Stage 1 (Global Vision) 기반 클러스터링
                clusters = engine.get_batch_clusters(stage=1, threshold=dedup_threshold)
                
                sampler = SimilarityAwareSampler(
                    sample_rate=sample_rate,
                    min_per_type=min_per_type,
                    seed=seed,
                )
                result = sampler.sample_with_diversity(all_files, clusters, batch_name=batch_name)
                
                num_clusters = len(clusters)
                num_duplicates = sum(len(c) - 1 for c in clusters)
                st.info(f"🔍 중복 분석 결과: **{num_duplicates}개**의 중복 문서를 발견하여 {num_clusters}개의 대표 그룹으로 압축했습니다.")
            except Exception as e:
                st.error(f"❌ 유사도 분석 중 오류 발생: {str(e)}")
                st.warning("중복 제거 없이 일반 샘플링을 진행합니다.")
                use_dedup = False

    if not use_dedup:
        sampler = StratifiedSampler(
            sample_rate=sample_rate,
            min_per_type=min_per_type,
            seed=seed,
        )
        result = sampler.sample(all_files, batch_name=batch_name)

    cache.init_from_sampling(
        sampled_files=result.sampled_files,
        sample_rate=sample_rate,
        min_per_type=min_per_type,
        seed=seed,
        type_breakdown=result.type_breakdown,
    )

    st.success(f"✅ 샘플링 완료! 총 **{result.total_count}개** 추출됨")
    st.session_state["active_cache_path"] = cache._path
    st.session_state["active_batch"] = batch_name
    st.session_state["active_date"] = cache.date

    st.info("👉 사이드바에서 **'검수 진행'** 페이지로 이동하여 검수를 시작하세요.")


if __name__ == "__main__":
    sampling_page()
