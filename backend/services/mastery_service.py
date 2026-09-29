"""
Adaptive learning / topic mastery service.

Tracks per-topic performance, calculates mastery scores,
generates personalized revision sessions, and provides
learning analytics.
"""
import logging
from datetime import datetime, timedelta, timezone

def _now() -> datetime:
    return datetime.now(timezone.utc)
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.models import (
    TopicMastery, QuizAttempt, StudySession, Document
)
from backend.models.factory import get_model
from backend.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Mastery queries
# ──────────────────────────────────────────────────────────────

def get_all_mastery(db: Session) -> List[Dict]:
    """Return mastery scores for all topics, sorted weakest first."""
    masteries = db.query(TopicMastery).order_by(TopicMastery.score.asc()).all()
    return [
        {
            "topic": m.topic,
            "score": round(m.score * 100, 1),
            "questions_attempted": m.questions_attempted,
            "correct_answers": m.correct_answers,
            "last_studied": m.last_studied.isoformat() if m.last_studied else None,
        }
        for m in masteries
    ]


def get_weak_topics(db: Session, threshold: float = 0.6, limit: int = 5) -> List[Dict]:
    """Return topics where mastery score < threshold."""
    masteries = (
        db.query(TopicMastery)
        .filter(TopicMastery.score < threshold, TopicMastery.questions_attempted > 0)
        .order_by(TopicMastery.score.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "topic": m.topic,
            "score": round(m.score * 100, 1),
            "questions_attempted": m.questions_attempted,
        }
        for m in masteries
    ]


def get_dashboard_stats(db: Session) -> Dict:
    """Aggregate stats for the dashboard."""
    total_docs = db.query(Document).count()

    # Topics studied
    topics_studied = db.query(TopicMastery).filter(TopicMastery.questions_attempted > 0).count()

    # Quiz accuracy
    total_attempts = db.query(func.sum(TopicMastery.questions_attempted)).scalar() or 0
    total_correct = db.query(func.sum(TopicMastery.correct_answers)).scalar() or 0
    quiz_accuracy = round((total_correct / max(total_attempts, 1)) * 100, 1)

    # Study streak: count consecutive days with activity
    streak = _calculate_streak(db)

    # Weak topics
    weak = get_weak_topics(db, threshold=0.6, limit=3)

    # Recent quiz attempts
    recent_attempts = (
        db.query(QuizAttempt)
        .order_by(QuizAttempt.timestamp.desc())
        .limit(5)
        .all()
    )
    recent_activity = [
        {
            "type": "quiz",
            "topic": a.topic,
            "is_correct": a.is_correct,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in recent_attempts
    ]

    return {
        "documents_uploaded": total_docs,
        "topics_studied": topics_studied,
        "quiz_accuracy": quiz_accuracy,
        "study_streak": streak,
        "weak_topics": weak,
        "recent_activity": recent_activity,
        "total_questions_attempted": total_attempts,
    }


def _calculate_streak(db: Session) -> int:
    """Count consecutive days of quiz activity ending today."""
    today = _now().date()
    streak = 0
    check_date = today

    for _ in range(365):
        start = datetime.combine(check_date, datetime.min.time())
        end = start + timedelta(days=1)
        count = (
            db.query(QuizAttempt)
            .filter(QuizAttempt.timestamp >= start, QuizAttempt.timestamp < end)
            .count()
        )
        if count > 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak


# ──────────────────────────────────────────────────────────────
# Smart Revision
# ──────────────────────────────────────────────────────────────

def start_revision_session(
    db: Session,
    topic: Optional[str] = None,
    document_id: Optional[int] = None,
    num_rounds: int = 5,
) -> Dict:
    """
    Build a revision session.

    If no topic given, choose the weakest topic automatically.
    Returns a session plan with explanation, example, and first question.
    """
    model = get_model()
    rag = get_rag_service()

    # Determine topic
    if not topic:
        weak = get_weak_topics(db, threshold=0.8, limit=1)
        if weak:
            topic = weak[0]["topic"]
        elif document_id:
            doc = db.query(Document).filter(Document.id == document_id).first()
            topic = doc.original_filename if doc else "General Review"
        else:
            topic = "General Review"

    # Retrieve relevant content
    doc_ids = [document_id] if document_id else None
    chunks = rag.search(topic, top_k=6, document_ids=doc_ids, min_score=0.0)
    context = "\n\n".join(c.text for c in chunks) if chunks else ""

    # Get mastery before
    mastery_before = 0.0
    mastery_obj = db.query(TopicMastery).filter(TopicMastery.topic == topic).first()
    if mastery_obj:
        mastery_before = round(mastery_obj.score * 100, 1)

    # Generate explanation using AI
    explanation = ""
    example = ""
    if context:
        exp_prompt = (
            f"You are a tutor. Give a concise explanation of '{topic}' "
            f"using the following study material:\n\n{context[:1500]}\n\n"
            f"Keep it under 150 words, student-friendly."
        )
        exp_resp = model.generate(exp_prompt, max_tokens=300, temperature=0.5)
        explanation = exp_resp.text

        ex_prompt = (
            f"Give one concrete, simple example that illustrates '{topic}'. "
            f"Base it on: {context[:800]}\n\nOne example only, 2-3 sentences."
        )
        ex_resp = model.generate(ex_prompt, max_tokens=150, temperature=0.5)
        example = ex_resp.text

    # Generate revision questions
    from backend.services.quiz_service import generate_quiz, QuizQuestion
    questions: List[QuizQuestion] = []
    if document_id:
        try:
            questions = generate_quiz(
                db=db,
                document_id=document_id,
                topic=topic,
                difficulty="medium",
                num_questions=num_rounds,
                question_types=["multiple_choice", "true_false"],
            )
        except Exception as e:
            logger.warning(f"Could not generate revision questions: {e}")

    # Create study session record
    session = StudySession(
        session_type="revision",
        started_at=_now(),
        document_ids=[document_id] if document_id else [],
        topics=[topic],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "topic": topic,
        "mastery_before": mastery_before,
        "explanation": explanation or f"Review your notes on {topic} carefully.",
        "example": example or "Refer to examples in your uploaded study material.",
        "questions": [
            {
                "id": q.id,
                "type": q.type,
                "question": q.question,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "topic": q.topic,
                "difficulty": q.difficulty,
            }
            for q in questions
        ],
        "sources": [
            {"document": c.document_filename, "page": c.page}
            for c in chunks[:3]
        ],
    }


def complete_revision_session(
    db: Session,
    session_id: int,
    topic: str,
    correct_answers: int,
    total_questions: int,
) -> Dict:
    """Finalize a revision session and update mastery."""
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    if session:
        session.ended_at = _now()
        session.questions_asked = total_questions
        session.correct_answers = correct_answers

    # Get mastery before
    mastery_obj = db.query(TopicMastery).filter(TopicMastery.topic == topic).first()
    mastery_before = round(mastery_obj.score * 100, 1) if mastery_obj else 0.0

    # Update mastery
    if not mastery_obj:
        mastery_obj = TopicMastery(
            topic=topic,
            questions_attempted=0,
            correct_answers=0,
            score=0.0,
        )
        db.add(mastery_obj)
        db.flush()
    mastery_obj.questions_attempted = (mastery_obj.questions_attempted or 0) + total_questions
    mastery_obj.correct_answers = (mastery_obj.correct_answers or 0) + correct_answers
    mastery_obj.score = mastery_obj.correct_answers / max(mastery_obj.questions_attempted, 1)
    mastery_obj.last_studied = _now()

    db.commit()

    mastery_after = round(mastery_obj.score * 100, 1)
    improvement = round(mastery_after - mastery_before, 1)

    # Next step recommendation
    if mastery_after >= 80:
        next_step = f"Excellent! You have strong mastery of {topic}. Try a harder difficulty quiz."
    elif improvement > 0:
        next_step = f"Good progress on {topic}! Keep practicing to reach 80% mastery."
    else:
        next_step = f"Review the {topic} material again and try another revision session."

    return {
        "session_id": session_id,
        "topic": topic,
        "mastery_before": mastery_before,
        "mastery_after": mastery_after,
        "improvement": improvement,
        "questions_answered": total_questions,
        "correct": correct_answers,
        "score_percent": round((correct_answers / max(total_questions, 1)) * 100, 1),
        "next_step": next_step,
    }


# ──────────────────────────────────────────────────────────────
# Document summarization
# ──────────────────────────────────────────────────────────────

def generate_document_summary(
    db: Session,
    document_id: int,
    summary_type: str = "quick",
) -> Dict:
    """
    Generate a document summary.

    summary_type:
      - "quick"   → overview + 5 key concepts
      - "exam"    → revision notes format
      - "simple"  → plain language explanation
    """
    model = get_model()
    rag = get_rag_service()

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    # Get representative chunks from throughout the document
    chunks = rag.search(
        f"main topics overview summary {doc.original_filename}",
        top_k=8,
        document_ids=[document_id],
        min_score=0.0,
    )

    if not chunks:
        # Direct DB fetch
        from backend.database.models import Chunk
        db_chunks = (
            db.query(Chunk)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
            .limit(8)
            .all()
        )
        context = "\n\n".join(c.text for c in db_chunks)
    else:
        context = "\n\n".join(c.text for c in chunks)

    if not context:
        return {"error": "No content available. Please process the document first."}

    if summary_type == "quick":
        prompt = (
            f"Summarize this study material from '{doc.original_filename}'.\n\n"
            f"{context[:3000]}\n\n"
            f"Provide:\n"
            f"1. A 3-sentence overview\n"
            f"2. 5 key concepts (bullet points)\n"
            f"3. 3 important definitions\n"
            f"4. Any important formulas or examples mentioned\n"
            f"Be concise and exam-focused."
        )
    elif summary_type == "exam":
        prompt = (
            f"Create concise exam revision notes from:\n\n{context[:3000]}\n\n"
            f"Format: bullet points, key facts, definitions, and memory aids."
        )
    else:  # simple
        prompt = (
            f"Explain the following study material in simple, plain language "
            f"as if teaching a beginner:\n\n{context[:2500]}\n\n"
            f"Avoid jargon. Use analogies where helpful."
        )

    response = model.summarize(context[:3000])
    # For non-quick types, use generate with specific prompt
    if summary_type != "quick":
        response = model.generate(prompt, max_tokens=800, temperature=0.5)

    return {
        "document_id": document_id,
        "filename": doc.original_filename,
        "summary_type": summary_type,
        "content": response.text,
        "model": response.model,
        "latency_ms": response.latency_ms,
    }
