"""
Local LLM provider via Ollama HTTP API.

Ollama runs models locally (llama3, mistral, gemma, phi, etc.)
and exposes a REST API at http://localhost:11434.

Install Ollama: https://ollama.com
Pull a model:   ollama pull llama3.2:3b

Set in .env:
  AI_PROVIDER=local_llm
  LOCAL_LLM_URL=http://localhost:11434
  LOCAL_LLM_MODEL=llama3.2:3b

The models run entirely on-device. No data is sent to external services.
On a Snapdragon-powered device, Ollama can leverage available CPU/GPU resources.
"""
import time
import json
import re
from typing import List, Optional

import httpx

from .base import AIModel, GenerateResponse, EmbedResponse, ModelInfo
from backend.config.settings import settings


SYSTEM_PROMPT_TUTOR = """You are SnapStudy, a private AI tutor running locally on the student's device.
Answer questions based on the provided study material context.
If the answer is not in the context, say "I couldn't find this information in your uploaded material."
Be concise, accurate, and educational. Cite sources when possible."""


class LocalLLMModel(AIModel):
    """
    Connects to a locally-running Ollama instance.
    All inference is performed on-device.
    """

    PROVIDER = "local_llm"

    def __init__(self):
        self.base_url = settings.LOCAL_LLM_URL.rstrip("/")
        self.model = settings.LOCAL_LLM_MODEL
        self.timeout = settings.LOCAL_LLM_TIMEOUT
        self._client = httpx.Client(timeout=self.timeout)
        self._embed_dims = 384  # updated on first embed call

    def _post(self, endpoint: str, payload: dict) -> dict:
        resp = self._client.post(
            f"{self.base_url}{endpoint}",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> GenerateResponse:
        t0 = time.perf_counter()
        system = system_prompt or SYSTEM_PROMPT_TUTOR
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        }
        data = self._post("/api/generate", payload)
        latency = (time.perf_counter() - t0) * 1000
        text = data.get("response", "")
        eval_count = data.get("eval_count", len(text.split()))
        eval_duration_ns = data.get("eval_duration", 1)
        tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0

        return GenerateResponse(
            text=text,
            model=self.model,
            provider=self.PROVIDER,
            latency_ms=latency,
            tokens_generated=eval_count,
            tokens_per_second=tps,
            metadata={"total_duration_ms": data.get("total_duration", 0) / 1e6},
        )

    def embed(self, text: str) -> EmbedResponse:
        t0 = time.perf_counter()
        data = self._post("/api/embeddings", {"model": self.model, "prompt": text})
        latency = (time.perf_counter() - t0) * 1000
        embedding = data.get("embedding", [])
        self._embed_dims = len(embedding)
        return EmbedResponse(
            embedding=embedding,
            model=self.model,
            provider=self.PROVIDER,
            latency_ms=latency,
            dimensions=len(embedding),
        )

    def embed_batch(self, texts: List[str]) -> List[EmbedResponse]:
        return [self.embed(t) for t in texts]

    def summarize(self, text: str, max_length: int = 300) -> GenerateResponse:
        prompt = (
            f"Summarize the following study material in {max_length} words or less. "
            f"Focus on the key concepts, definitions, and important facts.\n\n{text[:3000]}"
        )
        return self.generate(prompt, max_tokens=max_length * 2)

    def generate_quiz(
        self,
        context: str,
        topic: str,
        difficulty: str = "medium",
        num_questions: int = 5,
        question_types: Optional[List[str]] = None,
    ) -> GenerateResponse:
        qtypes = question_types or ["multiple_choice", "true_false"]
        type_str = ", ".join(qtypes)
        prompt = f"""Generate {num_questions} quiz questions about "{topic}" at {difficulty} difficulty.
Use ONLY the following study material as your source:

---
{context[:2500]}
---

Return a valid JSON object with this exact structure:
{{
  "questions": [
    {{
      "id": 1,
      "type": "multiple_choice",
      "question": "...",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "A",
      "explanation": "...",
      "topic": "{topic}",
      "difficulty": "{difficulty}"
    }}
  ]
}}

Question types to use: {type_str}
For true_false: omit options, set correct_answer to "True" or "False".
For short_answer: omit options, correct_answer is a brief expected response.
Return ONLY valid JSON, no other text."""

        return self.generate(prompt, max_tokens=2048, temperature=0.3)

    def get_info(self) -> ModelInfo:
        return ModelInfo(
            name=self.model,
            provider=self.PROVIDER,
            backend="Ollama",
            device="Local CPU/GPU",
            is_available=self.is_available(),
            supports_gpu=True,
            supports_npu=False,
            context_length=4096,
            embedding_dims=self._embed_dims,
            metadata={"url": self.base_url},
        )

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False
