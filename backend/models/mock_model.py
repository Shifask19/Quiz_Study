"""
Mock AI model for development, testing, and demo mode.

This provider uses rule-based responses and pre-written templates.
It does NOT call any external service or perform real inference.
It is clearly labelled as mock in all responses.

Purpose:
  - Allow full application testing without a real model installed.
  - Provide judges a working demo even if a local LLM is not configured.
  - Serve as the reference implementation for the AIModel interface.
"""
import time
import json
import random
import re
from typing import List, Optional

from .base import AIModel, GenerateResponse, EmbedResponse, ModelInfo


class MockModel(AIModel):
    """
    Deterministic mock provider.
    All responses are clearly marked as mock/demo output.
    No real inference occurs. No external calls are made.
    """

    PROVIDER = "mock"
    MODEL_NAME = "SnapStudy-Mock-1.0"
    EMBED_DIMS = 384

    # Demo answers keyed on keywords
    _QA_TEMPLATES = [
        ("normaliz", "Database normalization is the process of organizing a relational database to reduce redundancy and improve data integrity. The normal forms (1NF, 2NF, 3NF, BCNF) define progressively stricter rules for table design."),
        ("index", "A database index is a data structure that improves the speed of data retrieval. Common types include B-tree, hash, and full-text indexes. Indexes speed up SELECT queries but add overhead to INSERT/UPDATE/DELETE operations."),
        ("sql", "SQL (Structured Query Language) is the standard language for relational databases. Core commands include SELECT, INSERT, UPDATE, DELETE, CREATE, and DROP."),
        ("algorithm", "An algorithm is a step-by-step procedure for solving a problem. Key properties include correctness, efficiency (time and space complexity), and termination."),
        ("sort", "Sorting algorithms arrange elements in order. Common algorithms: Bubble Sort O(n²), Merge Sort O(n log n), Quick Sort O(n log n) average, Heap Sort O(n log n)."),
        ("os", "An operating system manages hardware resources and provides services for programs. Key components: process management, memory management, file system, I/O management."),
        ("memory", "Memory management in operating systems handles allocation and deallocation of RAM. Techniques include paging, segmentation, and virtual memory."),
        ("network", "Computer networks connect devices to share resources. The OSI model has 7 layers: Physical, Data Link, Network, Transport, Session, Presentation, Application."),
    ]

    def _find_template(self, query: str) -> Optional[str]:
        q = query.lower()
        for keyword, answer in self._QA_TEMPLATES:
            if keyword in q:
                return answer
        return None

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> GenerateResponse:
        t0 = time.perf_counter()
        time.sleep(0.05)  # simulate minimal latency

        answer = self._find_template(prompt)
        if not answer:
            answer = (
                "Based on the provided study material, this concept relates to the "
                "core topics in your document. For a detailed explanation, please "
                "ensure your document has been fully processed and indexed. "
                "[Note: This is a mock response — configure a real AI provider for actual answers.]"
            )

        latency = (time.perf_counter() - t0) * 1000
        words = len(answer.split())
        return GenerateResponse(
            text=answer,
            model=self.MODEL_NAME,
            provider=self.PROVIDER,
            latency_ms=latency,
            tokens_generated=words,
            tokens_per_second=words / max(latency / 1000, 0.001),
            memory_mb=0.0,
            metadata={"mock": True},
        )

    def embed(self, text: str) -> EmbedResponse:
        t0 = time.perf_counter()
        # Deterministic pseudo-embedding based on text content
        random.seed(hash(text) % (2**31))
        embedding = [random.gauss(0, 0.1) for _ in range(self.EMBED_DIMS)]
        # Normalize
        norm = sum(x**2 for x in embedding) ** 0.5
        embedding = [x / norm for x in embedding]
        latency = (time.perf_counter() - t0) * 1000
        return EmbedResponse(
            embedding=embedding,
            model=self.MODEL_NAME,
            provider=self.PROVIDER,
            latency_ms=latency,
            dimensions=self.EMBED_DIMS,
        )

    def embed_batch(self, texts: List[str]) -> List[EmbedResponse]:
        return [self.embed(t) for t in texts]

    def summarize(self, text: str, max_length: int = 300) -> GenerateResponse:
        t0 = time.perf_counter()
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 20]
        summary = ". ".join(sentences[:3]) + "." if sentences else "No content to summarize."
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        summary += " [Note: Mock summary — configure a real AI provider for accurate summaries.]"
        latency = (time.perf_counter() - t0) * 1000
        return GenerateResponse(
            text=summary,
            model=self.MODEL_NAME,
            provider=self.PROVIDER,
            latency_ms=latency,
            tokens_generated=len(summary.split()),
            metadata={"mock": True},
        )

    def generate_quiz(
        self,
        context: str,
        topic: str,
        difficulty: str = "medium",
        num_questions: int = 5,
        question_types: Optional[List[str]] = None,
    ) -> GenerateResponse:
        t0 = time.perf_counter()

        # Extract sentences from context for grounded questions
        sentences = [s.strip() for s in re.split(r'[.!?]', context) if len(s.strip()) > 30]
        sentences = sentences[:20]  # cap

        questions = []
        qtypes = question_types or ["multiple_choice", "true_false"]

        for i in range(num_questions):
            qtype = qtypes[i % len(qtypes)]
            src = sentences[i % len(sentences)] if sentences else f"Key concept {i+1} in {topic}"

            if qtype == "true_false":
                questions.append({
                    "id": i + 1,
                    "type": "true_false",
                    "question": f"True or False: {src[:120]}",
                    "correct_answer": "True",
                    "explanation": f"This statement is directly taken from the study material on {topic}.",
                    "topic": topic,
                    "difficulty": difficulty,
                })
            elif qtype == "short_answer":
                words = src.split()[:8]
                questions.append({
                    "id": i + 1,
                    "type": "short_answer",
                    "question": f"In your own words, explain: {' '.join(words)}...?",
                    "correct_answer": src[:200],
                    "explanation": f"The answer can be found in the study material on {topic}.",
                    "topic": topic,
                    "difficulty": difficulty,
                })
            else:
                # multiple choice
                options = [
                    src[:80] if src else f"Option A for {topic}",
                    f"An incorrect alternative related to {topic}",
                    f"Another plausible but wrong answer",
                    f"A distractor option for {topic}",
                ]
                random.shuffle(options)
                correct_idx = options.index(src[:80]) if src[:80] in options else 0
                labels = ["A", "B", "C", "D"]
                questions.append({
                    "id": i + 1,
                    "type": "multiple_choice",
                    "question": f"Which of the following best describes a key concept in {topic}?",
                    "options": {labels[j]: options[j] for j in range(4)},
                    "correct_answer": labels[correct_idx],
                    "explanation": f"The correct answer is grounded in the study material section on {topic}.",
                    "topic": topic,
                    "difficulty": difficulty,
                })

        latency = (time.perf_counter() - t0) * 1000
        return GenerateResponse(
            text=json.dumps({"questions": questions}, indent=2),
            model=self.MODEL_NAME,
            provider=self.PROVIDER,
            latency_ms=latency,
            tokens_generated=num_questions * 50,
            metadata={"mock": True, "num_questions": num_questions},
        )

    def get_info(self) -> ModelInfo:
        return ModelInfo(
            name=self.MODEL_NAME,
            provider=self.PROVIDER,
            backend="mock",
            device="CPU (Mock)",
            is_available=True,
            supports_gpu=False,
            supports_npu=False,
            context_length=2048,
            embedding_dims=self.EMBED_DIMS,
            metadata={"note": "Mock provider — no real inference. For demo/dev only."},
        )

    def is_available(self) -> bool:
        return True
