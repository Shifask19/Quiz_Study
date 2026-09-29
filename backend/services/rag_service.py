"""
RAG (Retrieval-Augmented Generation) service.

Handles:
  - Embedding documents into FAISS vector index
  - Persisting the index to disk
  - Semantic search / top-k retrieval
  - Building grounded prompts with source citations
  - Generating answers via the AI model
"""
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np

from backend.config.settings import settings
from backend.models.factory import get_model

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_filename: str
    text: str
    page: int
    score: float   # cosine similarity 0–1


@dataclass
class RAGResponse:
    answer: str
    sources: List[Dict[str, Any]]
    retrieved_chunks: List[RetrievedChunk]
    model: str
    provider: str
    latency_ms: float
    found_in_documents: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


TUTOR_SYSTEM_PROMPT = """You are SnapStudy, a private AI tutor running entirely on the student's device.
Your job is to help students understand their study material.

Rules:
1. Answer ONLY based on the provided context from the student's documents.
2. If the answer is not found in the context, say exactly: "I couldn't find this information in your uploaded material."
3. Never hallucinate or invent facts not present in the context.
4. Be clear, educational, and concise.
5. Reference the source document/page when citing specific facts.
6. Adapt your explanation level to be student-friendly."""


class RAGService:
    """
    Manages the FAISS vector index for all ingested document chunks.
    Thread-safe for reads; writes should be serialized by the caller.
    """

    INDEX_FILE = "index.faiss"
    META_FILE = "index_meta.json"

    def __init__(self):
        self._index = None
        self._meta: List[Dict] = []  # parallel list: meta[i] corresponds to index vector i
        self._dims: int = settings.EMBEDDING_MODEL == "all-MiniLM-L6-v2" and 384 or 384
        self._index_path = Path(settings.VECTOR_DB_DIR) / self.INDEX_FILE
        self._meta_path = Path(settings.VECTOR_DB_DIR) / self.META_FILE
        self._loaded = False
        self._try_load()

    # ──────────────────────────────────────────────────────────
    # FAISS helpers
    # ──────────────────────────────────────────────────────────

    def _get_faiss(self):
        import faiss
        return faiss

    def _create_index(self, dims: int):
        faiss = self._get_faiss()
        # Inner product index; vectors are L2-normalised → equivalent to cosine similarity
        index = faiss.IndexFlatIP(dims)
        return index

    def _try_load(self):
        """Load persisted index from disk if it exists."""
        try:
            faiss = self._get_faiss()
            if self._index_path.exists() and self._meta_path.exists():
                self._index = faiss.read_index(str(self._index_path))
                self._meta = json.loads(self._meta_path.read_text())
                self._dims = self._index.d
                self._loaded = True
                logger.info(f"Loaded FAISS index: {self._index.ntotal} vectors, dim={self._dims}")
        except Exception as e:
            logger.warning(f"Could not load FAISS index: {e}. Starting fresh.")
            self._index = None
            self._meta = []

    def _save(self):
        """Persist index to disk."""
        try:
            faiss = self._get_faiss()
            faiss.write_index(self._index, str(self._index_path))
            self._meta_path.write_text(json.dumps(self._meta))
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")

    # ──────────────────────────────────────────────────────────
    # Indexing
    # ──────────────────────────────────────────────────────────

    def index_chunks(
        self,
        chunks: List[Dict],   # each: {id, document_id, filename, text, page}
        batch_size: int = 32,
    ) -> int:
        """
        Embed and index a list of chunks. Returns number of vectors added.
        chunks must contain: id, document_id, filename, text, page
        """
        if not chunks:
            return 0

        model = get_model()
        vectors = []
        metas = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            texts = [c["text"] for c in batch]
            embeddings = model.embed_batch(texts)
            for chunk, emb in zip(batch, embeddings):
                vec = np.array(emb.embedding, dtype=np.float32)
                # L2 normalize for cosine similarity via inner product
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                vectors.append(vec)
                metas.append({
                    "chunk_id": chunk["id"],
                    "document_id": chunk["document_id"],
                    "filename": chunk["filename"],
                    "text": chunk["text"],
                    "page": chunk["page"],
                })

        if not vectors:
            return 0

        arr = np.stack(vectors).astype(np.float32)
        dims = arr.shape[1]

        if self._index is None or self._dims != dims:
            self._index = self._create_index(dims)
            self._dims = dims
            if self._meta:
                # Rebuild if dims changed (rare)
                logger.warning("Embedding dimensions changed. Rebuilding index.")
                self._meta = []

        self._index.add(arr)
        self._meta.extend(metas)
        self._save()
        logger.info(f"Indexed {len(vectors)} chunks. Total: {self._index.ntotal}")
        return len(vectors)

    def remove_document(self, document_id: int):
        """
        Remove all vectors for a document and rebuild the index.
        (FAISS FlatIP does not support single-vector deletion.)
        """
        if self._index is None:
            return

        try:
            faiss = self._get_faiss()
            keep_indices = [i for i, m in enumerate(self._meta) if m["document_id"] != document_id]

            if len(keep_indices) == len(self._meta):
                return  # nothing to remove

            if not keep_indices:
                self._index = None
                self._meta = []
                self._save()
                return

            # Reconstruct kept vectors
            old_total = self._index.ntotal
            # For FlatIP we can reconstruct
            kept_vectors = np.zeros((len(keep_indices), self._dims), dtype=np.float32)
            for new_i, old_i in enumerate(keep_indices):
                self._index.reconstruct(old_i, kept_vectors[new_i])

            self._index = self._create_index(self._dims)
            self._index.add(kept_vectors)
            self._meta = [self._meta[i] for i in keep_indices]
            self._save()
            logger.info(f"Removed document {document_id}. Index: {old_total} → {self._index.ntotal}")
        except Exception as e:
            logger.error(f"Failed to remove document from index: {e}")

    # ──────────────────────────────────────────────────────────
    # Retrieval
    # ──────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_ids: Optional[List[int]] = None,
        min_score: float = 0.2,
    ) -> List[RetrievedChunk]:
        """
        Semantic search over all indexed chunks.
        Optionally filter to specific document IDs.
        Returns top-k chunks ranked by cosine similarity.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        model = get_model()
        emb_resp = model.embed(query)
        vec = np.array(emb_resp.embedding, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        # Search more than top_k when filtering by document
        search_k = min(self._index.ntotal, top_k * 4 if document_ids else top_k)
        scores, indices = self._index.search(vec, search_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._meta):
                continue
            if score < min_score:
                continue
            meta = self._meta[idx]
            if document_ids and meta["document_id"] not in document_ids:
                continue
            results.append(RetrievedChunk(
                chunk_id=meta["chunk_id"],
                document_id=meta["document_id"],
                document_filename=meta["filename"],
                text=meta["text"],
                page=meta["page"],
                score=float(score),
            ))
            if len(results) >= top_k:
                break

        return results

    # ──────────────────────────────────────────────────────────
    # RAG generation
    # ──────────────────────────────────────────────────────────

    def answer(
        self,
        question: str,
        document_ids: Optional[List[int]] = None,
        top_k: int = 5,
        conversation_history: Optional[List[Dict]] = None,
    ) -> RAGResponse:
        """
        Full RAG pipeline:
          1. Retrieve relevant chunks
          2. Build grounded prompt
          3. Generate answer via AI model
          4. Return answer + source citations
        """
        t0 = time.perf_counter()
        model = get_model()
        model_info = model.get_info()

        chunks = self.search(question, top_k=top_k, document_ids=document_ids)

        if not chunks:
            # No relevant content found
            return RAGResponse(
                answer="I couldn't find this information in your uploaded material. Please make sure you have uploaded and processed relevant documents.",
                sources=[],
                retrieved_chunks=[],
                model=model_info.name,
                provider=model_info.provider,
                latency_ms=(time.perf_counter() - t0) * 1000,
                found_in_documents=False,
            )

        # Build context string
        context_parts = []
        for i, chunk in enumerate(chunks):
            context_parts.append(
                f"[Source {i+1}: {chunk.document_filename}, Page {chunk.page}]\n{chunk.text}"
            )
        context = "\n\n---\n\n".join(context_parts)

        # Build history string
        history_str = ""
        if conversation_history:
            history_lines = []
            for msg in conversation_history[-6:]:  # last 3 turns
                role = "Student" if msg.get("role") == "user" else "SnapStudy"
                history_lines.append(f"{role}: {msg.get('content', '')}")
            if history_lines:
                history_str = "\n\nPrevious conversation:\n" + "\n".join(history_lines) + "\n"

        prompt = (
            f"Context from student's study material:\n\n{context}"
            f"{history_str}"
            f"\n\nStudent's question: {question}\n\n"
            f"Answer based strictly on the context above. "
            f"If the answer is not in the context, say 'I couldn't find this information in your uploaded material.'"
        )

        gen = model.generate(prompt, system_prompt=TUTOR_SYSTEM_PROMPT, max_tokens=1024)

        # Build deduplicated source list
        seen = set()
        sources = []
        for chunk in chunks:
            key = (chunk.document_filename, chunk.page)
            if key not in seen:
                seen.add(key)
                sources.append({
                    "document": chunk.document_filename,
                    "page": chunk.page,
                    "excerpt": chunk.text[:150] + "..." if len(chunk.text) > 150 else chunk.text,
                    "score": round(chunk.score, 3),
                    "document_id": chunk.document_id,
                })

        total_latency = (time.perf_counter() - t0) * 1000

        return RAGResponse(
            answer=gen.text,
            sources=sources,
            retrieved_chunks=chunks,
            model=gen.model,
            provider=gen.provider,
            latency_ms=total_latency,
            found_in_documents=True,
            metadata={
                "generation_latency_ms": gen.latency_ms,
                "tokens_per_second": gen.tokens_per_second,
            },
        )

    def get_stats(self) -> Dict:
        return {
            "total_vectors": self._index.ntotal if self._index else 0,
            "dimensions": self._dims,
            "index_file": str(self._index_path),
        }


# Module-level singleton
_rag_instance: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGService()
    return _rag_instance
