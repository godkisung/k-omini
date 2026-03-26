import streamlit as st
import os
from PIL import Image
import pandas as pd
from typing import List, Dict, Any

from src.core.dedup_engine import DocumentDupPipeline
from src.core.models import Document, get_json_files
from src.config import get_batch_dirs, get_delivery_batches

def duplicate_detector_page():
    st.header("🔍 이미지 유사도 및 중복 탐지")
    st.caption("Jina-CLIP-v2, DINOv2, Florence-2를 이용한 고도화된 3단계 중복 탐지")

    # --- 1. 환경 점검 ---
    with st.sidebar:
        st.subheader("🛠️ 엔진 상태")
        try:
            # 파이프라인 초기화 (지연 로딩)
            if "dedup_pipeline" not in st.session_state:
                with st.status("에셋 모델 로딩 중...", expanded=False):
                    st.session_state.dedup_pipeline = DocumentDupPipeline()
                st.success("✅ 엔진 로드 완료")
            else:
                st.success("✅ 엔진 활성 상태")
        except Exception as e:
            st.error(f"❌ 엔진 로드 실패: {str(e)}")
            st.info("💡 CUDA GPU와 pymilvus 설치 여부를 확인하세요.")
            return

    # --- 2. 대상 선택 ---
    batches = get_delivery_batches()
    if not batches:
        st.warning("경고: `data/` 폴더 내에 유효한 납품 배치 폴더가 없습니다.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_batch = st.selectbox("탐지 대상 배치 선택", options=batches)
        json_dir, img_dir = get_batch_dirs(selected_batch)
    
    with col2:
        # 필터링 옵션
        st.write("") # 간격 조절
        process_mode = st.multiselect(
            "실행 단계 선택",
            options=["Stage 1 (Exact)", "Stage 2 (Template)", "Stage 3 (Region)"],
            default=["Stage 1 (Exact)", "Stage 2 (Template)"]
        )

    # 파일 목록 로드
    all_json_files = get_json_files(json_dir)
    if not all_json_files:
        st.error("해당 배치에 JSON 파일이 없습니다.")
        return

    st.write(f"📁 총 **{len(all_json_files)}개**의 문서를 탐지 대상으로 시스템에 등록합니다.")

    # --- 3. 실행 제어 ---
    if st.button("🚀 중복 탐지 프로세스 시작", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        pipeline = st.session_state.dedup_pipeline
        
        for i, json_path in enumerate(all_json_files):
            filename = os.path.basename(json_path)
            status_text.text(f"처리 중 ({i+1}/{len(all_json_files)}): {filename}")
            
            try:
                # 1. 문서 로드
                doc = Document.from_json(json_path)
                # 이미지 경로 보정 (img_dir 기준)
                img_name = os.path.basename(doc.image_path)
                abs_img_path = os.path.join(img_dir, img_name)
                
                if not os.path.exists(abs_img_path):
                    st.warning(f"이미지 파일을 찾을 수 없음: {abs_img_path}")
                    continue
                
                img = Image.open(abs_img_path).convert("RGB")
                doc_id = filename
                
                row = {"doc_id": doc_id}
                
                # Update: Stage 1
                if "Stage 1 (Exact)" in process_mode:
                    emb1 = pipeline.process_stage_1_exact(doc_id, img)
                    row["stage1_done"] = True
                
                # Update: Stage 2
                if "Stage 2 (Template)" in process_mode:
                    emb2 = pipeline.process_stage_2_template(doc)
                    row["stage2_done"] = True
                
                # Update: Stage 3
                if "Stage 3 (Region)" in process_mode:
                    regions = pipeline.process_stage_3_region(doc_id, img)
                    row["stage3_regions_found"] = len(regions)
                
                results.append(row)
                
            except Exception as e:
                st.error(f"오류 발생 ({filename}): {str(e)}")
            
            progress_bar.progress((i + 1) / len(all_json_files))
            
        status_text.text("✅ 처리 완료!")
        
        # 결과 표시
        if results:
            df = pd.DataFrame(results)
            st.success(f"총 {len(results)}개 문서의 임베딩이 분석 및 Vector DB(Milvus)에 저장되었습니다.")
            st.dataframe(df, use_container_width=True)
            
            st.info("""
            💡 **탐지 결과 확인 방법**:
            데이터가 Milvus Vector DB에 저장되었습니다. 이제 'Search Page' 또는 아래의 '리포트 내보내기' 기능을 통해 
            중복 현황을 파악할 수 있습니다.
            """)
            
    # --- 4. 리포트 내보내기 (중복 분석) ---
    st.divider()
    st.subheader("📊 중복 제거 리포트 생성")
    st.write("Milvus DB를 분석하여 전체 배치 내의 중복 그룹을 식별하고 CSV로 내보냅니다.")
    
    col_r1, col_r2 = st.columns([1, 1])
    with col_r1:
        report_threshold = st.slider("유사도 임계값 (리포트용)", 0.80, 0.99, 0.95, 0.01)
    
    if st.button("📝 중복 현황 리포트 생성", use_container_width=True):
        pipeline = st.session_state.dedup_pipeline
        with st.spinner("📦 배치의 모든 벡터를 분석하여 클러스터링 중..."):
            try:
                clusters = pipeline.get_batch_clusters(stage=1, threshold=report_threshold)
                
                report_data = []
                for idx, cluster in enumerate(clusters):
                    cluster_id = f"CLUSTER_{idx+1:04d}"
                    for i, doc_id in enumerate(cluster):
                        report_data.append({
                            "Cluster_ID": cluster_id,
                            "Filename": doc_id,
                            "Is_Representative": "Yes" if i == 0 else "No",
                            "Group_Size": len(cluster),
                            "Recommendation": "Keep" if i == 0 else "Remove/Check"
                        })
                
                if report_data:
                    df_report = pd.DataFrame(report_data)
                    st.success(f"✅ 분석 완료: 총 {len(clusters)}개의 그룹을 발견했습니다.")
                    st.dataframe(df_report, use_container_width=True)
                    
                    # CSV 다운로드 버튼
                    csv = df_report.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 중복 리포트 다운로드 (CSV)",
                        data=csv,
                        file_name=f"dedup_report_{selected_batch}_{report_threshold}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("분석할 데이터가 DB에 없습니다. 탐지 프로세스를 먼저 실행하세요.")
                    
            except Exception as e:
                st.error(f"리포트 생성 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    duplicate_detector_page()
