"""검수 진행 Streamlit 페이지.

샘플링 페이지에서 선택된 캐시를 로드하여 검수를 수행합니다.
기존 inspect_page.py의 시각화 로직을 재사용하고,
사이드바에 검수 기록 패널을 추가합니다.

워크플로우:
    ① sampling_page에서 캐시 경로를 session_state에 저장
    ② review_page 진입 시 캐시 로드
    ③ 샘플 파일을 순서대로 탐색하며 검수 결과 기록
    ④ 결과는 항목 저장 시마다 캐시에 즉시 반영
    ⑤ 완료 후 Excel 다운로드
"""

import os

import streamlit as st
from PIL import Image

from src.config import get_batch_dirs
from src.core.models import Document
from src.core.visualizer import draw_annotations_on_image
from src.config import get_config
from src.sampling.cache_manager import SamplingCache, CACHE_DIR
from src.sampling.exporter import ReviewExporter

config = get_config()

# ── 오류 유형 목록 ──────────────────────────────────────────────────────────
ERROR_TYPES = [
    "카테고리 분류 오류",
    "바운딩 박스 오류",
    "텍스트 누락/오기",
    "관계(relation) 오류",
    "ignore 플래그 오류",
    "순서(order) 오류",
    "기타",
]


def review_page() -> None:
    """검수 페이지 메인 함수."""
    st.header("🔍 샘플 검수")

    # ── 캐시 로드 ────────────────────────────────────────────────────────
    cache = _load_active_cache()
    if cache is None:
        st.info("👈 먼저 **'샘플링'** 페이지에서 세션을 시작하거나 이어서 진행하세요.")
        return

    reviewed, total = cache.progress()

    # ── 상단 진행률 표시 ─────────────────────────────────────────────────
    progress_ratio = reviewed / total if total > 0 else 0.0
    st.progress(progress_ratio, text=f"**{reviewed} / {total}** 페이지 검수 완료")

    col_info, col_download = st.columns([3, 1])
    with col_info:
        st.caption(
            f"📦 배치: `{cache.batch_name}` | 📅 날짜: `{cache.date}` | "
            f"🎯 샘플링 비율: `{int(cache._data.get('sample_rate', 0) * 100)}%`"
        )
    with col_download:
        _download_excel(cache)

    st.divider()

    # ── 파일 탐색 사이드바 ───────────────────────────────────────────────
    _initialize_review_state(cache)

    with st.sidebar:
        _render_sidebar_navigation(cache)

    # ── 메인 검수 화면 ───────────────────────────────────────────────────
    current_idx = st.session_state.get("review_current_idx", 0)
    if not cache.sampled_files:
        st.warning("샘플 파일이 없습니다.")
        return

    current_idx = max(0, min(current_idx, len(cache.sampled_files) - 1))
    st.session_state["review_current_idx"] = current_idx

    current_fname = cache.sampled_files[current_idx]
    _render_main_review(cache, current_fname, current_idx)


# ── 캐시 로드 ────────────────────────────────────────────────────────────────

def _load_active_cache() -> SamplingCache | None:
    """session_state에서 활성 캐시를 로드합니다."""
    batch = st.session_state.get("active_batch")
    date = st.session_state.get("active_date")

    if not batch or not date:
        return None

    cache = SamplingCache(batch_name=batch, date=date)
    if not cache.exists():
        return None

    cache.load()
    return cache


# ── 세션 상태 초기화 ──────────────────────────────────────────────────────────

def _initialize_review_state(cache: SamplingCache) -> None:
    """검수 세션 상태가 없으면 초기화합니다."""
    if "review_current_idx" not in st.session_state:
        # 마지막 미완료 항목부터 시작
        st.session_state["review_current_idx"] = cache.next_unreviewed_idx()


# ── 사이드바: 탐색 + 검수 기록 ───────────────────────────────────────────────

def _render_sidebar_navigation(cache: SamplingCache) -> None:
    """사이드바에 탐색 컨트롤과 검수 기록 패널을 렌더링합니다."""
    current_idx = st.session_state.get("review_current_idx", 0)
    total = len(cache.sampled_files)

    st.markdown("### 📁 파일 탐색")
    st.caption(f"{current_idx + 1} / {total}")

    # 탐색 버튼
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ 이전", use_container_width=True, disabled=current_idx == 0):
            st.session_state["review_current_idx"] = current_idx - 1
            st.rerun()
    with col2:
        if st.button("다음 ➡️", use_container_width=True, disabled=current_idx >= total - 1):
            st.session_state["review_current_idx"] = current_idx + 1
            st.rerun()

    # 페이지 직접 이동
    jump = st.number_input(
        "번호로 이동",
        min_value=1, max_value=total, value=current_idx + 1,
        step=1, label_visibility="collapsed",
    )
    if st.button("이동", use_container_width=True):
        st.session_state["review_current_idx"] = jump - 1
        st.rerun()

    st.divider()

    # 유형별 필터 (미완료 항목으로 이동)
    st.markdown("### 🔍 빠른 이동")
    if st.button("⏭️ 다음 미검수 항목", use_container_width=True):
        _jump_to_next_unreviewed(cache, current_idx)

    st.divider()
    st.markdown("### 📊 진행 현황")
    _render_type_progress(cache)


def _jump_to_next_unreviewed(cache: SamplingCache, current_idx: int) -> None:
    """현재 위치 이후의 미검수 항목으로 이동합니다."""
    files = cache.sampled_files
    for i in range(current_idx + 1, len(files)):
        result = cache.review_results.get(files[i], {})
        if not result.get("reviewed", False):
            st.session_state["review_current_idx"] = i
            st.rerun()
            return
    st.toast("✅ 이후 미검수 항목이 없습니다.")


def _render_type_progress(cache: SamplingCache) -> None:
    """유형별 검수 진행 현황을 표시합니다."""
    type_counts: dict[str, dict] = {}
    for fname in cache.sampled_files:
        dt = fname[:2].upper()
        if dt not in type_counts:
            type_counts[dt] = {"total": 0, "done": 0}
        type_counts[dt]["total"] += 1
        if cache.review_results.get(fname, {}).get("reviewed", False):
            type_counts[dt]["done"] += 1

    for dt, cnts in sorted(type_counts.items()):
        done, total = cnts["done"], cnts["total"]
        color = "🟢" if done == total else ("🟡" if done > 0 else "⬜")
        st.caption(f"{color} **{dt}**: {done}/{total}")


# ── 메인 검수 화면 ────────────────────────────────────────────────────────────

def _render_main_review(cache: SamplingCache, fname: str, idx: int) -> None:
    """메인 검수 화면을 렌더링합니다."""
    _, img_dir = get_batch_dirs(cache.batch_name)
    json_dir, _ = get_batch_dirs(cache.batch_name)

    json_path = os.path.join(json_dir, fname)
    img_name = os.path.splitext(fname)[0] + ".jpg"
    img_path = os.path.join(img_dir, img_name)

    # ── 파일명 표시 ────────────────────────────────────────────────────
    result = cache.get_result(fname)
    reviewed = result.get("reviewed", False)
    status_icon = "✅" if reviewed and not result.get("is_error") else ("🔴" if result.get("is_error") else "⬜")
    st.subheader(f"{status_icon} {idx + 1}. `{fname}`")

    # ── 이미지 + 어노테이션 ────────────────────────────────────────────
    col_img, col_panel = st.columns([3, 2])

    with col_img:
        if os.path.exists(json_path):
            try:
                doc = Document.from_json(json_path)
                if os.path.exists(img_path):
                    image = Image.open(img_path).convert("RGB")
                    relations = doc.raw_data.get("extra", {}).get("relation", [])
                    annotated = draw_annotations_on_image(
                        image.copy(), doc.layout_dets, config, relations=relations
                    )
                    st.image(annotated, caption=img_name, use_column_width=True)
                else:
                    st.warning(f"이미지 파일 없음: `{img_name}`")
            except Exception as e:
                st.error(f"JSON 로드 오류: {e}")
        else:
            st.error(f"JSON 파일 없음: `{fname}`")

    # ── 검수 기록 패널 ────────────────────────────────────────────────
    with col_panel:
        _render_review_panel(cache, fname, result)


def _render_review_panel(cache: SamplingCache, fname: str, existing: dict) -> None:
    """검수 결과 입력 패널을 렌더링합니다."""
    st.markdown("#### ✏️ 검수 결과 기록")

    is_error = st.toggle(
        "⚠️ 오류 있음",
        value=existing.get("is_error", False),
        key=f"err_toggle_{fname}",
    )

    error_types = []
    if is_error:
        error_types = st.multiselect(
            "오류 유형 (복수 선택 가능)",
            options=ERROR_TYPES,
            default=existing.get("error_types", []),
            key=f"err_types_{fname}",
        )

    memo = st.text_area(
        "검수자 메모",
        value=existing.get("memo", ""),
        height=120,
        placeholder="특이사항, 재확인 필요 항목 등 자유롭게 작성",
        key=f"memo_{fname}",
    )

    st.markdown("---")

    # JSON 상세 보기
    if os.path.exists(os.path.join(get_batch_dirs(cache.batch_name)[0], fname)):
        with st.expander("📄 JSON 어노테이션 상세", expanded=False):
            try:
                doc = Document.from_json(
                    os.path.join(get_batch_dirs(cache.batch_name)[0], fname)
                )
                st.json(doc.raw_data, expanded=False)
            except Exception:
                pass

    # 저장 버튼
    if st.button("💾 저장 및 다음으로", type="primary", use_container_width=True, key=f"save_{fname}"):
        cache.update_result(
            filename=fname,
            is_error=is_error,
            error_types=error_types,
            memo=memo,
        )
        st.toast("✅ 저장됨")
        # 다음 항목으로 자동 이동
        current_idx = st.session_state.get("review_current_idx", 0)
        if current_idx < len(cache.sampled_files) - 1:
            st.session_state["review_current_idx"] = current_idx + 1
        st.rerun()

    # 저장만 (이동 없음)
    if st.button("💾 저장 (현재 유지)", use_container_width=True, key=f"save_stay_{fname}"):
        cache.update_result(
            filename=fname,
            is_error=is_error,
            error_types=error_types,
            memo=memo,
        )
        st.toast("✅ 저장됨")
        st.rerun()


# ── Excel 다운로드 ─────────────────────────────────────────────────────────────

def _download_excel(cache: SamplingCache) -> None:
    """Excel 파일을 생성하여 다운로드 버튼을 활성화합니다."""
    exporter = ReviewExporter(cache)
    excel_bytes = exporter.to_bytes()
    filename = f"검수결과_{cache.batch_name}_{cache.date}.xlsx"

    st.download_button(
        label="📥 Excel 파일 저장",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="excel_dl_btn",
    )


if __name__ == "__main__":
    review_page()
