"""
Document Deduplication Pipeline Exceptions.
"""

class PipelineBaseException(Exception):
    """파이프라인의 기본 예외 클래스입니다."""
    pass

class ModelInferenceError(PipelineBaseException):
    """모델 추론 과정에서 발생하는 예외를 처리합니다."""
    pass

class VectorDBConnectionError(PipelineBaseException):
    """Vector Database 연결 및 작업 중 발생하는 예외를 처리합니다."""
    pass
