"""
Abstract base classes for AI model providers.

This abstraction layer allows swapping between:
  - Mock (development/demo)
  - Local LLM via Ollama (llama.cpp, etc.)
  - ONNX Runtime (quantized models)
  - Qualcomm AI Hub (Snapdragon NPU acceleration)

To add a new provider: subclass AIModel and implement all abstract methods.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class GenerateResponse:
    text: str
    model: str
    provider: str
    latency_ms: float = 0.0
    tokens_generated: int = 0
    tokens_per_second: float = 0.0
    memory_mb: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbedResponse:
    embedding: List[float]
    model: str
    provider: str
    latency_ms: float = 0.0
    dimensions: int = 0


@dataclass
class ModelInfo:
    name: str
    provider: str
    backend: str
    device: str
    is_available: bool
    supports_gpu: bool = False
    supports_npu: bool = False
    context_length: int = 2048
    embedding_dims: int = 384
    metadata: Dict[str, Any] = field(default_factory=dict)


class AIModel(ABC):
    """Abstract interface that all AI model providers must implement."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> GenerateResponse:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    def embed(self, text: str) -> EmbedResponse:
        """Embed text into a dense vector."""
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[EmbedResponse]:
        """Embed multiple texts. Providers can override for batched efficiency."""
        ...

    @abstractmethod
    def summarize(self, text: str, max_length: int = 300) -> GenerateResponse:
        """Summarize text."""
        ...

    @abstractmethod
    def generate_quiz(
        self,
        context: str,
        topic: str,
        difficulty: str = "medium",
        num_questions: int = 5,
        question_types: Optional[List[str]] = None,
    ) -> GenerateResponse:
        """Generate quiz questions as JSON string."""
        ...

    @abstractmethod
    def get_info(self) -> ModelInfo:
        """Return model/provider metadata."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Health-check: return True if the model is reachable and loaded."""
        ...

    def embed_batch(self, texts: List[str]) -> List[EmbedResponse]:
        """Default: call embed() in a loop. Override for efficiency."""
        return [self.embed(t) for t in texts]
