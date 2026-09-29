"""
Sentence Transformers embedding provider.

Uses the all-MiniLM-L6-v2 model for local embeddings.
This model runs entirely on-device (CPU or GPU).
Model is ~90MB and downloads automatically on first use.

For generation (text answers), this module delegates to the configured
AI_PROVIDER since sentence-transformers is an embedding-only model.
Generation falls back to the mock provider if no LLM is configured.
"""
import time
import logging
from typing import List, Optional

from .base import AIModel, GenerateResponse, EmbedResponse, ModelInfo
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class SentenceTransformerModel(AIModel):
    """
    Embedding provider using sentence-transformers all-MiniLM-L6-v2.
    Generation is delegated to a separate LLM (or mock if none configured).
    """

    PROVIDER = "sentence_transformers"

    def __init__(self):
        self._model = None
        self._dims = 384
        self._init_error = None
        self._llm = None
        self._try_init()

    def _try_init(self):
        try:
            import os
            os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self._dims = self._model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded. Dims: {self._dims}")
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"SentenceTransformer init failed: {e}")

        # For generation, delegate to LLM or mock
        try:
            llm_provider = settings.AI_PROVIDER
            if llm_provider == "local_llm":
                from .local_llm import LocalLLMModel
                self._llm = LocalLLMModel()
                if not self._llm.is_available():
                    self._llm = None
            elif llm_provider == "onnx":
                from .onnx_model import ONNXModel
                self._llm = ONNXModel()
        except Exception:
            pass

        if self._llm is None:
            from .mock_model import MockModel
            self._llm = MockModel()

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> GenerateResponse:
        return self._llm.generate(prompt, system_prompt, max_tokens, temperature)

    def embed(self, text: str) -> EmbedResponse:
        if self._model is None:
            from .mock_model import MockModel
            return MockModel().embed(text)

        t0 = time.perf_counter()
        try:
            import numpy as np
            embedding = self._model.encode(text, normalize_embeddings=True).tolist()
            latency = (time.perf_counter() - t0) * 1000
            return EmbedResponse(
                embedding=embedding,
                model=settings.EMBEDDING_MODEL,
                provider=self.PROVIDER,
                latency_ms=latency,
                dimensions=len(embedding),
            )
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            from .mock_model import MockModel
            return MockModel().embed(text)

    def embed_batch(self, texts: List[str]) -> List[EmbedResponse]:
        if self._model is None or not texts:
            from .mock_model import MockModel
            m = MockModel()
            return [m.embed(t) for t in texts]

        t0 = time.perf_counter()
        try:
            import numpy as np
            embeddings = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
            total_latency = (time.perf_counter() - t0) * 1000
            per_latency = total_latency / max(len(texts), 1)
            return [
                EmbedResponse(
                    embedding=emb.tolist(),
                    model=settings.EMBEDDING_MODEL,
                    provider=self.PROVIDER,
                    latency_ms=per_latency,
                    dimensions=len(emb),
                )
                for emb in embeddings
            ]
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return [self.embed(t) for t in texts]

    def summarize(self, text: str, max_length: int = 300) -> GenerateResponse:
        return self._llm.summarize(text, max_length)

    def generate_quiz(
        self,
        context: str,
        topic: str,
        difficulty: str = "medium",
        num_questions: int = 5,
        question_types: Optional[List[str]] = None,
    ) -> GenerateResponse:
        return self._llm.generate_quiz(context, topic, difficulty, num_questions, question_types)

    def get_info(self) -> ModelInfo:
        llm_info = self._llm.get_info() if self._llm else None
        return ModelInfo(
            name=f"{settings.EMBEDDING_MODEL} + {llm_info.name if llm_info else 'mock'}",
            provider=self.PROVIDER,
            backend="sentence-transformers (local)",
            device="CPU",
            is_available=self._model is not None,
            supports_gpu=False,
            supports_npu=False,
            context_length=512,
            embedding_dims=self._dims,
            metadata={
                "embedding_model": settings.EMBEDDING_MODEL,
                "generation_provider": llm_info.provider if llm_info else "mock",
                "init_error": self._init_error,
            },
        )

    def is_available(self) -> bool:
        return self._model is not None
