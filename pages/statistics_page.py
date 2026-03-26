import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
import os

from src.core.dedup_engine import DocumentDupPipeline
from src.config import get_delivery_batches, get_batch_dirs
from src.core.models import get_json_files

def set_korean_font():
    """한글 폰트 설정 (기본값 사용)"""
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False

def get_doc_type(filename: str) -> str:
    """파일명에서 문서 타입(Prefix) 추출"""
    if "_" in filename:
        return filename.split("_")[0]
    return "UNKNOWN"

def statistics_page():
    st.header("📊 데이터 중복 및 정제 통계")
    st.caption("Milvus Vector DB 분석을 통한 데이터셋 품질 및 정제 효율 지표")

    set_korean_font()

    # --- 1. 엔진 및 배치 선택 ---
    batches = get_delivery_batches()
    if not batches:
        st.warning("경고: `data/` 폴더 내에 유효한 납품 배치 폴더가 없습니다.")
        return

    selected_batch = st.sidebar.selectbox("통계 분석 대상 배치", options=batches)
    
    threshold = st.sidebar.slider("유사도 임계값 (분석용)", 0.80, 0.99, 0.95, 0.01)

    # 파이프라인 초기화
    if "dedup_pipeline" not in st.session_state:
        try:
            with st.status("엔진 로딩 중...", expanded=False):
                st.session_state.dedup_pipeline = DocumentDupPipeline()
        except Exception as e:
            st.error(f"엔진 로드 실패: {str(e)}")
            return

    pipeline = st.session_state.dedup_pipeline

    if st.sidebar.button("🚀 통계 결과 업데이트", type="primary", use_container_width=True):
        st.session_state.stats_refresh = True

    # --- 2. 데이터 분석 실행 ---
    with st.spinner("📦 배치의 모든 벡터를 분석하여 클러스터링 중..."):
        try:
            # 1. 클러스터링 결과 가져오기
            clusters = pipeline.get_batch_clusters(stage=1, threshold=threshold)
            
            if not clusters:
                st.info("💡 분석할 데이터가 DB에 없습니다. 'Duplicate Detector' 페이지에서 먼저 탐지를 실행하세요.")
                return

            # 전체 문서 (클러스터에 포함된 모든 ID)
            all_ids = []
            for c in clusters:
                all_ids.extend(c)
            
            total_docs = len(all_ids)
            unique_docs = len(clusters)
            duplicate_docs = total_docs - unique_docs
            dedup_rate = (duplicate_docs / total_docs * 100) if total_docs > 0 else 0

            # 3. 메인 지표 표시
            st.divider()
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("전체 문서 수", f"{total_docs:,}")
            m_col2.metric("고유 문서 수", f"{unique_docs:,}")
            m_col3.metric("중복 제거 수", f"{duplicate_docs:,}", delta=f"-{dedup_rate:.1f}%", delta_color="inverse")
            m_col4.metric("최종 압축률", f"{(total_docs/unique_docs if unique_docs > 0 else 1):.2f}x")

            # 4. 시각화 섹션
            st.write("")
            v_col1, v_col2 = st.columns(2)

            with v_col1:
                # [Chart 1] Duplicate Ratio (Pie Chart)
                st.subheader("📍 Data Composition")
                fig1, ax1 = plt.subplots(figsize=(6, 6))
                labels = ['Unique', 'Duplicate']
                sizes = [unique_docs, duplicate_docs]
                colors = ['#4CAF50', '#FF5252']
                ax1.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors, explode=(0.05, 0))
                ax1.axis('equal')
                st.pyplot(fig1)

            with v_col2:
                # [Chart 2] Cluster Size Distribution (Histogram)
                st.subheader("📏 Cluster Size Distribution")
                cluster_sizes = [len(c) for c in clusters if len(c) > 1] # Groups with 2+ docs
                if cluster_sizes:
                    counts = Counter(cluster_sizes)
                    size_labels = sorted(counts.keys())
                    size_values = [counts[s] for s in size_labels]
                    
                    fig2, ax2 = plt.subplots(figsize=(8, 6))
                    ax2.bar([f"Size {s}" for s in size_labels], size_values, color='#2196F3')
                    ax2.set_ylabel("Count of Groups")
                    ax2.set_xlabel("Documents per Cluster")
                    ax2.set_title("How many duplicates per group?")
                    st.pyplot(fig2)
                else:
                    st.info("No duplicated clusters found.")

            # [Chart 3] Deduplication by Document Type
            st.divider()
            st.subheader("📂 Refinement Effect by Type (Top 10)")
            
            type_stats = defaultdict(lambda: {"total": 0, "unique": 0})
            for cluster in clusters:
                rep_type = get_doc_type(cluster[0])
                type_stats[rep_type]["unique"] += 1
                for doc in cluster:
                    dtype = get_doc_type(doc)
                    type_stats[dtype]["total"] += 1
            
            type_df_data = []
            for dtype, counts in type_stats.items():
                if dtype == "UNKNOWN": continue
                type_df_data.append({
                    "Type": dtype,
                    "Total": counts["total"],
                    "Unique": counts["unique"],
                    "Dup_Rate": (1 - counts["unique"]/counts["total"]) * 100
                })
            
            if type_df_data:
                df_types = pd.DataFrame(type_df_data).sort_values("Total", ascending=False).head(10)
                
                fig3, ax3 = plt.subplots(figsize=(10, 5))
                x = np.arange(len(df_types))
                width = 0.35
                
                ax3.bar(x - width/2, df_types['Total'], width, label='Original', color='#BBDEFB')
                ax3.bar(x + width/2, df_types['Unique'], width, label='Refined', color='#1976D2')
                
                ax3.set_xticks(x)
                ax3.set_xticklabels(df_types['Type'], rotation=45)
                ax3.legend()
                ax3.set_title("Data Volume Reduction by Type")
                st.pyplot(fig3)
                
                # 상세 표
                st.dataframe(df_types.style.format({"Dup_Rate": "{:.1f}%"}), use_container_width=True)

            # [Section 4] Visual Examples of Duplicates
            st.divider()
            st.subheader("🖼️ Example Duplicated Groups (Samples)")
            st.write("Visual comparison of identified duplicates for reporting.")
            
            dup_clusters = [c for c in clusters if len(c) > 1]
            if not dup_clusters:
                st.info("No duplication found to display visual examples.")
            else:
                _, img_dir = get_batch_dirs(selected_batch)
                
                # Show top 5 examples
                for i, cluster in enumerate(dup_clusters[:5]):
                    with st.expander(f"Group {i+1}: {len(cluster)} documents", expanded=True):
                        # Show representative vs one of the duplicates
                        cols = st.columns(min(len(cluster), 4)) 
                        for j, doc_id in enumerate(cluster[:4]): # Limit to 4 images per row
                            with cols[j]:
                                # filename -> img path
                                img_name = doc_id.replace(".json", ".img") # Heuristic: name mapping
                                # Actually use the correct mapping (json -> img)
                                # For safety, try common extensions
                                possible_exts = [".img", ".jpg", ".png", ".jpeg"]
                                img_path = None
                                base_name = doc_id.rsplit('.', 1)[0]
                                
                                for ext in possible_exts:
                                    p = os.path.join(img_dir, base_name + ext)
                                    if os.path.exists(p):
                                        img_path = p
                                        break
                                
                                if img_path:
                                    st.image(img_path, caption=f"{'🏆 Rep' if j==0 else '👯 Dup'}\n{doc_id}", use_column_width=True)
                                else:
                                    st.warning(f"Image not found: {doc_id}")
            
        except Exception as e:
            st.error(f"Error during analysis: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

if __name__ == "__main__":
    from collections import defaultdict
    statistics_page()
