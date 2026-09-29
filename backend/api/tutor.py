"""
AI Tutor API endpoints.

POST /tutor/ask                    Ask a question (RAG)
GET  /tutor/conversations          List conversations
POST /tutor/conversations          Create conversation
GET  /tutor/conversations/{id}     Get conversation with messages
POST /tutor/conversations/{id}/message  Add message
DELETE /tutor/conversations/{id}   Delete conversation
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db, Conversation, Message
from backend.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tutor", tags=["tutor"])


# ──────────────────────────────────────────────────────────────
# Request / Response schemas
# ──────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    document_ids: Optional[List[int]] = None
    conversation_id: Optional[int] = None
    mode: Optional[str] = "standard"  # standard | explain_simpler | give_example | summarize | quiz_me


class SourceCitation(BaseModel):
    document: str
    page: int
    excerpt: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    found_in_documents: bool
    model: str
    provider: str
    latency_ms: float
    conversation_id: Optional[int]


class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"
    document_ids: Optional[List[int]] = None


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    timestamp: Optional[str]
    sources: Optional[List[dict]]


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: Optional[str]
    updated_at: Optional[str]
    messages: Optional[List[MessageResponse]] = None


# ──────────────────────────────────────────────────────────────
# Mode prefixes
# ──────────────────────────────────────────────────────────────

MODE_PREFIXES = {
    "explain_simpler": "Explain the following in simpler terms, as if talking to a beginner: ",
    "give_example": "Give a concrete real-world example to illustrate: ",
    "summarize": "Provide a brief summary of: ",
    "quiz_me": "Create one quiz question about: ",
}


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse)
def ask_question(
    req: AskRequest,
    db: Session = Depends(get_db),
):
    """Main RAG endpoint. Retrieves relevant chunks and generates a grounded answer."""
    question = req.question

    # Apply mode prefix
    prefix = MODE_PREFIXES.get(req.mode or "standard", "")
    if prefix:
        question = prefix + question

    # Load conversation history
    history = []
    conv_id = req.conversation_id
    if conv_id:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv:
            msgs = (
                db.query(Message)
                .filter(Message.conversation_id == conv_id)
                .order_by(Message.timestamp.asc())
                .limit(10)
                .all()
            )
            history = [{"role": m.role, "content": m.content} for m in msgs]

    rag = get_rag_service()
    rag_resp = rag.answer(
        question=question,
        document_ids=req.document_ids,
        top_k=5,
        conversation_history=history,
    )

    # Save to conversation if provided
    if conv_id:
        # User message
        user_msg = Message(
            conversation_id=conv_id,
            role="user",
            content=req.question,
        )
        db.add(user_msg)

        # Assistant message
        asst_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=rag_resp.answer,
            sources=rag_resp.sources,
        )
        db.add(asst_msg)

        # Update conversation title if first message
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv:
            msg_count = db.query(Message).filter(Message.conversation_id == conv_id).count()
            if msg_count <= 2:
                conv.title = req.question[:60] + ("..." if len(req.question) > 60 else "")
        db.commit()

    return AskResponse(
        answer=rag_resp.answer,
        sources=[
            SourceCitation(
                document=s["document"],
                page=s["page"],
                excerpt=s["excerpt"],
                score=s["score"],
            )
            for s in rag_resp.sources
        ],
        found_in_documents=rag_resp.found_in_documents,
        model=rag_resp.model,
        provider=rag_resp.provider,
        latency_ms=round(rag_resp.latency_ms, 2),
        conversation_id=conv_id,
    )


@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(db: Session = Depends(get_db)):
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(50).all()
    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat() if c.created_at else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )
        for c in convs
    ]


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(req: ConversationCreate, db: Session = Depends(get_db)):
    conv = Conversation(
        title=req.title or "New Conversation",
        document_ids=req.document_ids,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat() if conv.created_at else None,
        updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
        messages=[],
    )


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
def get_conversation(conv_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.timestamp.asc())
        .all()
    )

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat() if conv.created_at else None,
        updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                timestamp=m.timestamp.isoformat() if m.timestamp else None,
                sources=m.sources,
            )
            for m in messages
        ],
    )


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted."}
