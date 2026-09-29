#!/usr/bin/env python3
"""
Create demo data for SnapStudy.
Uploads and processes the bundled demo study material so the app
is immediately usable after installation.

Usage:
  python scripts/create_demo_data.py
"""
import sys
import os
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "sentence_transformers")

def main():
    print("SnapStudy — Loading Demo Data")
    print("=" * 40)

    from backend.database.connection import SessionLocal, init_db
    from backend.database.models import Document, ProcessingStatus
    from backend.config.settings import settings

    init_db()
    db = SessionLocal()

    try:
        # Check if demo already loaded
        existing = db.query(Document).filter(
            Document.original_filename == "demo_study_material.txt"
        ).first()

        if existing:
            print(f"Demo data already loaded (Document ID: {existing.id}, Status: {existing.processing_status.value})")
            if existing.processing_status != ProcessingStatus.READY:
                print("Re-processing demo document...")
                _process(db, existing)
            else:
                print("Demo document is ready. You can start the app and ask questions!")
            return

        # Copy demo file to uploads
        demo_src = ROOT / "data" / "demo" / "demo_study_material.txt"
        if not demo_src.exists():
            print(f"ERROR: Demo file not found at {demo_src}")
            sys.exit(1)

        content = demo_src.read_bytes()
        unique_name = f"demo_{uuid.uuid4().hex[:8]}_demo_study_material.txt"
        save_path = Path(settings.UPLOAD_DIR) / unique_name
        save_path.write_bytes(content)

        doc = Document(
            filename=unique_name,
            original_filename="demo_study_material.txt",
            file_type="txt",
            file_size=len(content),
            file_path=str(save_path),
            processing_status=ProcessingStatus.PENDING,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        print(f"Created document record (ID: {doc.id})")

        _process(db, doc)

    finally:
        db.close()

    print("\nDemo data loaded successfully!")
    print("Start the app and click 'Load Demo Data' or go to My Library.")


def _process(db, doc):
    from backend.services.document_processor import extract_document
    from backend.services.rag_service import get_rag_service
    from backend.database.models import Chunk, ProcessingStatus
    from backend.config.settings import settings

    print(f"Processing '{doc.original_filename}'...")
    doc.processing_status = ProcessingStatus.PROCESSING
    db.commit()

    extracted = extract_document(
        Path(doc.file_path),
        chunk_size=settings.CHUNK_SIZE,
        overlap=settings.CHUNK_OVERLAP,
    )

    if extracted.error:
        doc.processing_status = ProcessingStatus.FAILED
        doc.error_message = extracted.error
        db.commit()
        print(f"ERROR: {extracted.error}")
        return

    print(f"  Extracted {extracted.page_count} pages, {len(extracted.chunks)} chunks")

    # Clear existing chunks
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.commit()

    chunk_records = []
    for tc in extracted.chunks:
        chunk = Chunk(
            document_id=doc.id,
            chunk_index=tc.chunk_index,
            page=tc.page,
            text=tc.text,
            word_count=tc.word_count,
        )
        db.add(chunk)
        db.flush()
        chunk_records.append({
            "id": chunk.id,
            "document_id": doc.id,
            "filename": doc.original_filename,
            "text": tc.text,
            "page": tc.page,
        })

    print(f"  Embedding {len(chunk_records)} chunks (this may take a moment)...")
    rag = get_rag_service()

    # Remove old vectors for this doc
    rag.remove_document(doc.id)
    indexed = rag.index_chunks(chunk_records)
    print(f"  Indexed {indexed} vectors")

    from backend.models.factory import get_model
    model = get_model()
    summary = ""
    key_concepts = []
    if extracted.full_text:
        try:
            resp = model.summarize(extracted.full_text[:2000], max_length=200)
            summary = resp.text
        except Exception:
            summary = extracted.full_text[:300]

        words = [w.lower() for w in extracted.full_text.split() if len(w) > 5]
        from collections import Counter
        freq = Counter(words)
        stopwords = {"which", "where", "there", "their", "about", "would", "could", "should"}
        key_concepts = [w for w, _ in freq.most_common(20) if w not in stopwords][:8]

    doc.processing_status = ProcessingStatus.READY
    doc.page_count = extracted.page_count
    doc.chunk_count = len(extracted.chunks)
    doc.summary = summary
    doc.key_concepts = key_concepts
    doc.topics = key_concepts[:5]
    db.commit()
    print(f"  Done. Document is ready!")


if __name__ == "__main__":
    main()
