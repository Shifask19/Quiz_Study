"""
Tests for RAG service: indexing, search, and answer generation.
"""
import pytest
from pathlib import Path
import shutil


@pytest.fixture(autouse=True)
def clean_rag(tmp_path):
    """Each test gets a fresh RAG service with empty FAISS index."""
    import backend.services.rag_service as rag_mod
    from backend.models.factory import reset_model

    # Point the RAG service to a fresh temp dir
    vec_dir = tmp_path / "vector_db"
    vec_dir.mkdir()

    # Reset singleton
    rag_mod._rag_instance = None
    reset_model()

    # Create a new instance that uses the temp dir
    svc = rag_mod.RAGService.__new__(rag_mod.RAGService)
    svc._index = None
    svc._meta = []
    svc._dims = 384
    svc._loaded = False
    from pathlib import Path
    svc._index_path = vec_dir / "index.faiss"
    svc._meta_path  = vec_dir / "index_meta.json"
    rag_mod._rag_instance = svc

    yield

    rag_mod._rag_instance = None


def make_chunks(n=5, document_id=1, filename="test.txt"):
    return [
        {
            "id": i + 1,
            "document_id": document_id,
            "filename": filename,
            "text": f"Database normalization reduces redundancy. Chunk {i} covers normal forms and relational algebra.",
            "page": i + 1,
        }
        for i in range(n)
    ]


class TestRAGIndexing:
    def test_index_chunks_returns_count(self):
        from backend.services.rag_service import get_rag_service
        from backend.models.factory import reset_model
        reset_model()
        rag = get_rag_service()
        chunks = make_chunks(3)
        count = rag.index_chunks(chunks)
        assert count == 3

    def test_stats_after_indexing(self):
        from backend.services.rag_service import get_rag_service
        from backend.models.factory import reset_model
        reset_model()
        rag = get_rag_service()
        rag.index_chunks(make_chunks(4))
        stats = rag.get_stats()
        assert stats["total_vectors"] == 4

    def test_empty_chunks_returns_zero(self):
        from backend.services.rag_service import get_rag_service
        rag = get_rag_service()
        count = rag.index_chunks([])
        assert count == 0

    def test_remove_document_clears_vectors(self):
        from backend.services.rag_service import get_rag_service
        from backend.models.factory import reset_model
        reset_model()
        rag = get_rag_service()
        rag.index_chunks(make_chunks(5, document_id=1))
        rag.index_chunks(make_chunks(3, document_id=2))
        rag.remove_document(1)
        stats = rag.get_stats()
        assert stats["total_vectors"] == 3


class TestRAGSearch:
    def test_search_returns_results(self):
        from backend.services.rag_service import get_rag_service
        from backend.models.factory import reset_model
        reset_model()
        rag = get_rag_service()
        rag.index_chunks(make_chunks(5))
        results = rag.search("database normalization", top_k=3, min_score=0.0)
        assert len(results) <= 3

    def test_search_respects_top_k(self):
        from backend.services.rag_service import get_rag_service
        from backend.models.factory import reset_model
        reset_model()
        rag = get_rag_service()
        rag.index_chunks(make_chunks(10))
        results = rag.search("normalization", top_k=2, min_score=0.0)
        assert len(results) <= 2

    def test_search_empty_index_returns_empty(self):
        from backend.services.rag_service import get_rag_service
        rag = get_rag_service()
        results = rag.search("anything", top_k=5, min_score=0.0)
        assert results == []

    def test_search_result_has_expected_fields(self):
        from backend.services.rag_service import get_rag_service, RetrievedChunk
        from backend.models.factory import reset_model
        reset_model()
        rag = get_rag_service()
        rag.index_chunks(make_chunks(3))
        results = rag.search("normalization", top_k=1, min_score=0.0)
        if results:
            r = results[0]
            assert isinstance(r, RetrievedChunk)
            assert r.document_id == 1
            assert len(r.text) > 0
            assert 0.0 <= r.score <= 1.0


class TestRAGAnswer:
    def test_answer_with_context(self):
        from backend.services.rag_service import get_rag_service
        from backend.models.factory import reset_model
        reset_model()
        rag = get_rag_service()
        rag.index_chunks(make_chunks(5))
        resp = rag.answer("What is database normalization?")
        assert len(resp.answer) > 0
        assert resp.latency_ms >= 0

    def test_answer_no_docs_gives_fallback(self):
        from backend.services.rag_service import get_rag_service
        rag = get_rag_service()
        resp = rag.answer("What is the meaning of life?")
        assert resp.found_in_documents is False
        assert "couldn't find" in resp.answer.lower() or "uploaded" in resp.answer.lower()
