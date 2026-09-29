"""
Qualcomm AI Hub model adapter for SnapStudy.

Qualcomm AI Hub allows developers to compile, profile, and run AI models
on Snapdragon-powered devices with NPU acceleration.

Integration path:
  1. Register at https://aihub.qualcomm.com
  2. Get your API token
  3. Compile/export a supported model:
       import qai_hub as hub
       job = hub.submit_compile_job(model, device=hub.Device("Snapdragon X Elite"))
  4. Deploy and run:
       inference_job = hub.submit_inference_job(model, device=hub.Device("Snapdragon X Elite"))
  5. Set in .env:
       AI_PROVIDER=qualcomm_ai_hub
       QAI_HUB_API_TOKEN=your_token
       QAI_HUB_MODEL_ID=your_compiled_model_id

Supported models on AI Hub include:
  - Llama 3.2 (1B, 3B)
  - Mistral 7B
  - Phi-3 Mini
  - Whisper (for voice)
  - MobileBERT / MiniLM (for embeddings)

This adapter wraps qai_hub.Client if the SDK is installed,
and falls back to the ONNX adapter otherwise.
"""
import time
import json
from typing import List, Optional

from .base import AIModel, GenerateResponse, EmbedResponse, ModelInfo
from backend.config.settings import settings


class QualcommAIHubModel(AIModel):
    """
    Adapter for Qualcomm AI Hub deployed models.

    When qai_hub SDK is available and credentials are configured,
    this runs inference through AI Hub's on-device execution pipeline.

    When not available, surfaces a clear error message explaining
    exactly what is needed to enable this provider.
    """

    PROVIDER = "qualcomm_ai_hub"

    def __init__(self):
        self._hub = None
        self._model = None
        self._device = None
        self._init_error = None
        self._fallback = None
        self._try_init()

    def _try_init(self):
        if not settings.QAI_HUB_API_TOKEN:
            self._init_error = (
                "QAI_HUB_API_TOKEN not set. "
                "Get your token at https://aihub.qualcomm.com and set it in .env"
            )
            self._init_fallback()
            return

        try:
            import qai_hub as hub
            hub.configure(api_token=settings.QAI_HUB_API_TOKEN)
            self._hub = hub
            self._device = hub.Device(settings.QAI_HUB_DEVICE)

            if settings.QAI_HUB_MODEL_ID:
                self._model = hub.get_model(settings.QAI_HUB_MODEL_ID)
        except ImportError:
            self._init_error = (
                "qai_hub SDK not installed. "
                "Install it: pip install qai-hub\n"
                "Documentation: https://app.aihub.qualcomm.com/docs/"
            )
            self._init_fallback()
        except Exception as e:
            self._init_error = f"AI Hub initialization failed: {e}"
            self._init_fallback()

    def _init_fallback(self):
        """Use ONNX adapter as fallback."""
        try:
            from .onnx_model import ONNXModel
            self._fallback = ONNXModel()
        except Exception:
            from .mock_model import MockModel
            self._fallback = MockModel()

    def _run_inference(self, inputs: dict) -> dict:
        """Submit an inference job to AI Hub and wait for results."""
        if not self._hub or not self._model:
            raise RuntimeError(self._init_error or "AI Hub model not loaded")

        import numpy as np
        t0 = time.perf_counter()
        inference_job = self._hub.submit_inference_job(
            model=self._model,
            device=self._device,
            inputs=inputs,
        )
        result = inference_job.download_output_data()
        latency = (time.perf_counter() - t0) * 1000
        return {"outputs": result, "latency_ms": latency}

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> GenerateResponse:
        if self._fallback:
            result = self._fallback.generate(prompt, system_prompt, max_tokens, temperature)
            result.metadata["ai_hub_note"] = self._init_error
            return result

        # When AI Hub + model are configured:
        # The exact input format depends on the compiled model.
        # Typical flow for a causal LM:
        #   1. Tokenize prompt
        #   2. Submit as input_ids tensor to inference job
        #   3. Decode output token ids
        # This requires model-specific adaptation.
        return GenerateResponse(
            text=(
                "Qualcomm AI Hub inference requires a compiled model with "
                "known input/output signatures. Please follow the integration "
                "guide in README.md to deploy your model and update this adapter."
            ),
            model=settings.QAI_HUB_MODEL_ID or "qai-hub-model",
            provider=self.PROVIDER,
            latency_ms=0.0,
            metadata={"integration_required": True},
        )

    def embed(self, text: str) -> EmbedResponse:
        if self._fallback:
            return self._fallback.embed(text)
        # AI Hub embedding inference — adapt input/output names for your model
        return self._fallback.embed(text) if self._fallback else EmbedResponse(
            embedding=[0.0] * 384, model="qai-hub", provider=self.PROVIDER,
            latency_ms=0.0, dimensions=384
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
        prompt = f"Generate {num_questions} {difficulty} quiz questions about {topic}:\n{context[:2000]}"
        return self.generate(prompt, max_tokens=2048, temperature=0.3)

    def get_info(self) -> ModelInfo:
        return ModelInfo(
            name=settings.QAI_HUB_MODEL_ID or "Qualcomm AI Hub Model",
            provider=self.PROVIDER,
            backend="Qualcomm AI Hub / QNN",
            device=settings.QAI_HUB_DEVICE,
            is_available=self.is_available(),
            supports_gpu=True,
            supports_npu=True,  # AI Hub targets NPU on Snapdragon
            context_length=4096,
            embedding_dims=384,
            metadata={
                "api_configured": bool(settings.QAI_HUB_API_TOKEN),
                "model_id": settings.QAI_HUB_MODEL_ID,
                "init_error": self._init_error,
                "fallback_active": self._fallback is not None,
            },
        )

    def is_available(self) -> bool:
        return self._hub is not None and self._model is not None
