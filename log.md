[2026-02-05 19:35:31,805] [    INFO] ocr_utils.py:34 - PaddleOCR 모듈 로드 성공
[2026-02-05 19:35:31,805] [ WARNING] ocr_utils.py:48 - PPStructure를 import할 수 없습니다: No module named 'ppstructure'
[2026-02-05 19:35:31,809] [ WARNING] ocr_utils.py:79 - ONNX 모드 실패, 일반 모드로 재시도: Unknown argument: use_onnx
Creating model: ('PP-LCNet_x1_0_textline_ori', None)
Model files already exist. Using cached files. To redownload, please delete the directory manually: `/home/kisung/.paddlex/official_models/PP-LCNet_x1_0_textline_ori`.
Creating model: ('PP-OCRv5_server_det', None)
Model files already exist. Using cached files. To redownload, please delete the directory manually: `/home/kisung/.paddlex/official_models/PP-OCRv5_server_det`.
Creating model: ('korean_PP-OCRv5_mobile_rec', None)
Model files already exist. Using cached files. To redownload, please delete the directory manually: `/home/kisung/.paddlex/official_models/korean_PP-OCRv5_mobile_rec`.
[2026-02-05 19:35:34,300] [    INFO] ocr_utils.py:87 - ✅ PaddleOCR 엔진 초기화 성공 (일반 모드)
[2026-02-05 19:35:34,342] [   ERROR] ocr_utils.py:192 - ❌ 영역 텍스트 추출 실패: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]  (at /paddle/paddle/fluid/framework/new_executor/instruction/onednn/onednn_instruction.cc:116)