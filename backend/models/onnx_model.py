"""
ONNX Runtime model provider for SnapStudy.

This adapter enables running quantized ONNX models on-device.
ONNX Runtime supports CPU, CUDA, DirectML, and QNN (Qualcomm Neural Network) backends.

On Snapdragon-powered PCs, ONNX Runtime with DirectML or QNN execution provider
enables NPU/GPU acceleration for significantly faster inference.

Setup:
  1. Export your model to ONNX format (e.g., with optimum, llama.cpp, or AI Hub)
  2. Place model files in ./models/
  3. Set in .env:
       AI_PROVIDER=onnx
       ONNX_LLM_PATH=./models/llm.onnx
       ONNX_EMBED_PATH=./models/embeddings.onnx

Qualcomm AI Hub exports models in ONNX-compatible formats that can be loaded here.
See: https://aihub.qualcomm.com

Note: For language generation, consider using ONNX versions of:
  - Phi-3 Mini (Microsoft, optimized for Snapdragon)
  - Llama 3.2 3B
  - Mistral 7B
"""
import time
import json
import numpy as np
from pathlib import Path
from typing import List, Optional

from .base import AIModel, GenerateResponse, EmbedResponse, ModelInfo
from backend.config.settings import settings


class ONNXModel(AIModel):
    """
    ONNX Runtime inference provider.

    For language generation: wraps an ONNX-exported causal LM with a tokenizer.
    For embeddings: wraps an ONNX sentence-transformer.

    Falls back gracefully if onnxruntime is not installed.
    """

    PROVIDER = "onnx"

    def __init__(self):
        self._ort = None
        self._llm_session = None
        self._embed_session = None
        self._tokenizer = None
        self._embed_tokenizer = None
        self._embed_dims = 384
        self._llm_path = Path(settings.ONNX_LLM_PATH)
        self._embed_path = Path(settings.ONNX_EMBED_PATH)
        self._initialized = False
        self._init_error = None
        self._try_init()

    def _try_init(self):
        try:
            import onnxruntime as ort
            self._ort = ort

            # Determine best available execution provider
            available_eps = ort.get_available_providers()
            # Prefer: QNN (Snapdragon NPU) > DirectML (GPU) > CUDA > CPU
            ep_priority = ["QNNExecutionProvider", "DmlExecutionProvider",
                           "CUDAExecutionProvider", "CPUExecutionProvider"]
            self._ep = next((ep for ep in ep_priority if ep in available_eps), "CPUExecutionProvider")

            so = ort.SessionOptions()
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            if self._embed_path.exists():
                self._embed_session = ort.InferenceSession(
                    str(self._embed_path),
                    sess_options=so,
                    providers=[self._ep],
                )
                self._initialized = True

            if self._llm_path.exists():
                self._llm_session = ort.InferenceSession(
                    str(self._llm_path),
                    sess_options=so,
                    providers=[self._ep],
                )
                self._initialized = True

        except ImportError:
            self._init_error = "onnxruntime not installed. Run: pip install onnxruntime"
        except Exception as e:
            self._init_error = str(e)

    def _mean_pooling(self, token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        mask_expanded = np.expand_dims(attention_mask, axis=-1).astype(float)
        sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        return sum_embeddings / sum_mask

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> GenerateResponse:
        if not self._llm_session:
            return GenerateResponse(
                text=(
                    f"ONNX LLM model not loaded. "
                    f"Place your ONNX model at: {self._llm_path}\n"
                    f"Error: {self._init_error or 'Model file not found'}"
                ),
                model="onnx-llm",
                provider=self.PROVIDER,
                latency_ms=0.0,
                metadata={"error": True},
            )

        # Actual ONNX generation depends heavily on the specific model architecture.
        # The implementation below is a placeholder for the session.run() call.
        # You will need to adapt input/output names to your specific exported model.
        t0 = time.perf_counter()
        try:
            # Generic generative model inference — adapt to your model's I/O names
            # This is a structural placeholder. Actual implementation depends on model.
            raise NotImplementedError(
                "ONNX LLM generation requires model-specific input/output adaptation. "
                "See the ONNX model card for your exported model's I/O specification."
            )
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000
            return GenerateResponse(
                text=f"ONNX generation error: {e}",
                model="onnx-llm",
                provider=self.PROVIDER,
                latency_ms=latency,
                metadata={"error": str(e)},
            )

    def embed(self, text: str) -> EmbedResponse:
        if not self._embed_session:
            # Fall back to a simple hash-based mock embedding
            from .mock_model import MockModel
            return MockModel().embed(text)

        t0 = time.perf_counter()
        try:
            from transformers import AutoTokenizer
            if not self._embed_tokenizer:
                self._embed_tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

            encoded = self._embed_tokenizer(
                text, padding=True, truncation=True, max_length=256, return_tensors="np"
            )
            outputs = self._embed_session.run(
                None,
                {
                    "input_ids": encoded["input_ids"],
                    "attention_mask": encoded["attention_mask"],
                },
            )
            token_embeddings = outputs[0]
            sentence_embedding = self._mean_pooling(token_embeddings, encoded["attention_mask"])
            # L2 normalize
            norm = np.linalg.norm(sentence_embedding, axis=1, keepdims=True)
            sentence_embedding = (sentence_embedding / np.maximum(norm, 1e-9))[0]
            embedding = sentence_embedding.tolist()
            self._embed_dims = len(embedding)

        except Exception as e:
            from .mock_model import MockModel
            return MockModel().embed(text)

        latency = (time.perf_counter() - t0) * 1000
        return EmbedResponse(
            embedding=embedding,
            model="onnx-embed",
            provider=self.PROVIDER,
            latency_ms=latency,
            dimensions=self._embed_dims,
        )

    def embed_batch(self, texts: List[str]) -> List[EmbedResponse]:
        return [self.embed(t) for t in texts]

    def summarize(self, text: str, max_length: int = 300) -> GenerateResponse:
        prompt = f"Summarize in {max_length} words:\n\n{text[:2000]}"
        return self.generate(prompt, max_tokens=max_length * 2)

    def generate_quiz(
        self,
        context: str,
        topic: str,
        difficulty: str = "medium",
        num_questions: int = 5,
        question_types: Optional[List[str]] = None,
    ) -> GenerateResponse:
        prompt = f"Generate {num_questions} {difficulty} quiz questions about {topic} based on:\n{context[:2000]}"
        return self.generate(prompt, max_tokens=2048, temperature=0.3)

    def get_info(self) -> ModelInfo:
        ep = getattr(self, "_ep", "CPUExecutionProvider")
        return ModelInfo(
            name="ONNX Model",
            provider=self.PROVIDER,
            backend=f"ONNX Runtime ({ep})",
            device="Local Device",
            is_available=self.is_available(),
            supports_gpu="Dml" in ep or "CUDA" in ep,
            supports_npu="QNN" in ep,
            context_length=2048,
            embedding_dims=self._embed_dims,
            metadata={
                "execution_provider": ep,
                "llm_path": str(self._llm_path),
                "embed_path": str(self._embed_path),
                "init_error": self._init_error,
            },
        )

    def is_available(self) -> bool:
        return self._initialized and self._init_error is None
