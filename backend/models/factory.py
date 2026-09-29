"""
AI model factory — returns the correct provider based on configuration.
"""
from typing import Optional
from .base import AIModel
from backend.config.settings import settings


_model_instance: Optional[AIModel] = None


def get_model() -> AIModel:
    """
    Return (and cache) the configured AI model provider.

    Provider selection order:
      1. AI_PROVIDER env var (or EMBEDDING_PROVIDER for embeddings)
      2. Auto-detect: try sentence_transformers → local_llm → onnx → mock

    Thread safety note: this is a simple singleton; for production
    multi-worker setups, use a proper dependency injection container.
    """
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    embed_provider = settings.EMBEDDING_PROVIDER.lower()
    provider = settings.AI_PROVIDER.lower()

    # If embedding provider is sentence_transformers, use it as the primary model
    # (handles embeddings locally; delegates generation to LLM or mock)
    if embed_provider == "sentence_transformers" and provider in ("mock", "sentence_transformers"):
        from .sentence_transformer_model import SentenceTransformerModel
        model = SentenceTransformerModel()
        if model.is_available():
            _model_instance = model
            return _model_instance
        import logging
        logging.warning("SentenceTransformer unavailable. Falling back to mock.")
        from .mock_model import MockModel
        _model_instance = MockModel()
        return _model_instance

    if provider == "local_llm":
        from .local_llm import LocalLLMModel
        model = LocalLLMModel()
        if not model.is_available():
            import logging
            logging.warning(
                "local_llm provider unavailable (Ollama not running?). "
                "Falling back to mock. Start Ollama or change AI_PROVIDER in .env"
            )
            from .mock_model import MockModel
            model = MockModel()

    elif provider == "onnx":
        from .onnx_model import ONNXModel
        model = ONNXModel()
        if not model.is_available():
            import logging
            logging.warning("ONNX provider unavailable. Falling back to mock.")
            from .mock_model import MockModel
            model = MockModel()

    elif provider == "qualcomm_ai_hub":
        from .qualcomm_ai_hub import QualcommAIHubModel
        model = QualcommAIHubModel()
        # QAI Hub adapter has its own internal fallback

    else:
        # mock or unknown
        from .mock_model import MockModel
        model = MockModel()

    _model_instance = model
    return _model_instance


def reset_model():
    """Force re-initialization (useful for tests)."""
    global _model_instance
    _model_instance = None
