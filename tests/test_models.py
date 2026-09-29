"""
Tests for AI model providers: mock, factory selection, embed/generate interfaces.
"""
import pytest
from backend.models.mock_model import MockModel
from backend.models.base import AIModel, GenerateResponse, EmbedResponse


class TestMockModel:
    def setup_method(self):
        self.model = MockModel()

    def test_is_available(self):
        assert self.model.is_available() is True

    def test_generate_returns_response(self):
        resp = self.model.generate("What is database normalization?")
        assert isinstance(resp, GenerateResponse)
        assert len(resp.text) > 10
        assert resp.provider == "mock"
        assert resp.model == MockModel.MODEL_NAME

    def test_generate_latency_is_positive(self):
        resp = self.model.generate("test")
        assert resp.latency_ms >= 0

    def test_generate_uses_keyword_template(self):
        resp = self.model.generate("Explain database normalization in detail")
        assert "normal" in resp.text.lower() or "redundancy" in resp.text.lower()

    def test_embed_returns_correct_dims(self):
        resp = self.model.embed("Hello world")
        assert isinstance(resp, EmbedResponse)
        assert resp.dimensions == MockModel.EMBED_DIMS
        assert len(resp.embedding) == MockModel.EMBED_DIMS

    def test_embed_is_normalised(self):
        import math
        resp = self.model.embed("test sentence")
        norm = math.sqrt(sum(x**2 for x in resp.embedding))
        assert abs(norm - 1.0) < 1e-5

    def test_embed_deterministic(self):
        r1 = self.model.embed("same text")
        r2 = self.model.embed("same text")
        assert r1.embedding == r2.embedding

    def test_embed_different_texts_differ(self):
        r1 = self.model.embed("database normalization")
        r2 = self.model.embed("sorting algorithms")
        assert r1.embedding != r2.embedding

    def test_embed_batch(self):
        texts = ["text one", "text two", "text three"]
        results = self.model.embed_batch(texts)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, EmbedResponse)

    def test_summarize_returns_text(self):
        resp = self.model.summarize("Long text about databases and normalization " * 20)
        assert len(resp.text) > 10

    def test_generate_quiz_returns_valid_json(self):
        import json
        resp = self.model.generate_quiz(
            context="Database normalization reduces redundancy. First Normal Form requires atomic attributes.",
            topic="Database Normalization",
            difficulty="medium",
            num_questions=3,
        )
        data = json.loads(resp.text)
        assert "questions" in data
        assert len(data["questions"]) == 3

    def test_get_info_returns_model_info(self):
        from backend.models.base import ModelInfo
        info = self.model.get_info()
        assert isinstance(info, ModelInfo)
        assert info.provider == "mock"
        assert info.is_available is True


class TestModelFactory:
    def test_factory_returns_ai_model_instance(self):
        from backend.models.factory import get_model, reset_model
        reset_model()
        model = get_model()
        assert isinstance(model, AIModel)

    def test_factory_caches_instance(self):
        from backend.models.factory import get_model
        m1 = get_model()
        m2 = get_model()
        assert m1 is m2

    def test_reset_clears_cache(self):
        from backend.models.factory import get_model, reset_model
        m1 = get_model()
        reset_model()
        m2 = get_model()
        # New instance after reset
        assert m1 is not m2
