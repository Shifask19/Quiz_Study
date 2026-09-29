"""
Document management API endpoints.

POST   /documents/upload          Upload and process a document
GET    /documents/                 List all documents
GET    /documents/{id}             Get document details
DELETE /documents/{id}             Delete a document
GET    /documents/{id}/summary     Generate document summary
POST   /documents/demo             Load demo data
"""
import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.config.settings import settings
from backend.database import get_db, Document, Chunk, ProcessingStatus
from backend.services.document_processor import (
    extract_document, sanitize_filename, SUPPORTED_EXTENSIONS
)
from backend.services.rag_service import get_rag_service
from backend.services.mastery_service import generate_document_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

MAX_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    upload_date: Optional[str]
    processing_status: str
    page_count: int
    chunk_count: int
    error_message: Optional[str]
    summary: Optional[str]
    key_concepts: List[str]
    topics: List[str]
    privacy_note: str = "Processed locally on your device"


def _doc_to_response(doc: Document) -> DocumentResponse:
    d = doc.to_dict()
    return DocumentResponse(
        id=d["id"],
        filename=d["filename"],
        file_type=d["file_type"],
        file_size=d["file_size"],
        upload_date=d["upload_date"],
        processing_status=d["processing_status"],
        page_count=d["page_count"],
        chunk_count=d["chunk_count"],
        error_message=d["error_message"],
        summary=d["summary"],
        key_concepts=d["key_concepts"],
        topics=d["topics"],
    )


def _process_document_background(doc_id: int, file_path: str):
    """
    Background task: extract, chunk, embed, and index document.
    Updates document record on completion.
    """
    from backend.database.connection import SessionLocal
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return

        doc.processing_status = ProcessingStatus.PROCESSING
        db.commit()

        # Extract text
        extracted = extract_document(
            Path(file_path),
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )

        if extracted.error:
            doc.processing_status = ProcessingStatus.FAILED
            doc.error_message = extracted.error
            db.commit()
            return

        # Store chunks in DB
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

        # Index into FAISS
        rag = get_rag_service()
        rag.index_chunks(chunk_records)

        # Generate quick summary
        model_summary = ""
        key_concepts = []
        try:
            from backend.models.factory import get_model
            ai_model = get_model()
            if extracted.full_text:
                preview = extracted.full_text[:2000]
                sum_resp = ai_model.summarize(preview, max_length=200)
                model_summary = sum_resp.text

                # Extract topics/concepts from text
                words = [w.lower() for w in extracted.full_text.split() if len(w) > 5]
                from collections import Counter
                freq = Counter(words)
                stopwords = {"which", "where", "there", "their", "about", "would", "could",
                            "should", "these", "those", "other", "after", "before", "while"}
                key_concepts = [w for w, _ in freq.most_common(20) if w not in stopwords][:8]
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")

        doc.processing_status = ProcessingStatus.READY
        doc.page_count = extracted.page_count
        doc.chunk_count = len(extracted.chunks)
        doc.summary = model_summary or extracted.full_text[:300]
        doc.key_concepts = key_concepts
        doc.topics = key_concepts[:5]
        db.commit()
        logger.info(f"Document {doc_id} processed: {len(extracted.chunks)} chunks")

    except Exception as e:
        logger.error(f"Processing failed for doc {doc_id}: {e}")
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.processing_status = ProcessingStatus.FAILED
                doc.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a document and start background processing."""
    # Validate file type
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    # Read and check size
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB} MB",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Sanitize filename and save
    safe_name = sanitize_filename(file.filename or f"upload{suffix}")
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    save_path = Path(settings.UPLOAD_DIR) / unique_name

    with open(save_path, "wb") as f:
        f.write(content)

    # DB record
    doc = Document(
        filename=unique_name,
        original_filename=safe_name,
        file_type=suffix.lstrip("."),
        file_size=len(content),
        file_path=str(save_path),
        processing_status=ProcessingStatus.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Kick off background processing
    background_tasks.add_task(_process_document_background, doc.id, str(save_path))

    return _doc_to_response(doc)


@router.get("/", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.upload_date.desc()).all()
    return [_doc_to_response(d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove file
    try:
        if Path(doc.file_path).exists():
            os.remove(doc.file_path)
    except Exception as e:
        logger.warning(f"Could not delete file: {e}")

    # Remove from vector index
    rag = get_rag_service()
    rag.remove_document(doc_id)

    db.delete(doc)
    db.commit()
    return {"message": f"Document '{doc.original_filename}' deleted successfully."}


@router.get("/{doc_id}/summary")
def get_document_summary(
    doc_id: int,
    summary_type: str = "quick",
    db: Session = Depends(get_db),
):
    if summary_type not in ("quick", "exam", "simple"):
        raise HTTPException(status_code=400, detail="summary_type must be quick, exam, or simple")
    try:
        result = generate_document_summary(db, doc_id, summary_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {e}")


@router.post("/demo")
async def load_demo_data(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Load the bundled demo document so judges can try the app immediately."""
    demo_path = Path(__file__).resolve().parent.parent.parent / "data" / "demo" / "demo_study_material.txt"
    if not demo_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Demo data not found. Run: python scripts/create_demo_data.py",
        )

    # Check if already loaded
    existing = db.query(Document).filter(
        Document.original_filename == "demo_study_material.txt"
    ).first()
    if existing:
        return {"message": "Demo data already loaded.", "document_id": existing.id}

    content = demo_path.read_bytes()
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

    background_tasks.add_task(_process_document_background, doc.id, str(save_path))

    return {
        "message": "Demo data loaded and processing started.",
        "document_id": doc.id,
        "filename": "demo_study_material.txt",
    }
