"""
Quiz generation and evaluation service.

Generates questions from document content using the AI model.
Evaluates answers, tracks performance per topic, and recommends
revision topics based on incorrect answers.
"""
import json
import re
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

def _now() -> datetime:
    return datetime.now(timezone.utc)
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from backend.database.models import QuizAttempt, TopicMastery, Document, Chunk
from backend.models.factory import get_model
from backend.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


@dataclass
class QuizQuestion:
    id: int
    type: str           # multiple_choice | true_false | short_answer
    question: str
    options: Optional[Dict[str, str]]  # {"A": "...", "B": "...", ...}
    correct_answer: str
    explanation: str
    topic: str
    difficulty: str
    source_chunk: Optional[str] = None


@dataclass
class QuizResult:
    quiz_id: str
    total_questions: int
    correct: int
    score_percent: float
    questions: List[Dict]
    weak_topics: List[str]
    strong_topics: List[str]
    recommendations: List[str]


def _parse_quiz_json(raw: str) -> List[Dict]:
    """Parse quiz questions from model output, handling imperfect JSON."""
    # Try direct parse
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "questions" in data:
            return data["questions"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block
    match = re.search(r'\{.*"questions"\s*:\s*\[.*\]\s*\}', raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return data.get("questions", [])
        except Exception:
            pass

    # Try array extraction
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    logger.warning("Could not parse quiz JSON from model output")
    return []


def generate_quiz(
    db: Session,
    document_id: int,
    topic: Optional[str],
    difficulty: str = "medium",
    num_questions: int = 5,
    question_types: Optional[List[str]] = None,
) -> List[QuizQuestion]:
    """
    Generate quiz questions from a document.

    1. Retrieve relevant chunks (RAG search on topic if provided)
    2. Build context from chunks
    3. Ask AI model to generate questions
    4. Parse and validate response
    5. Return structured questions
    """
    if question_types is None:
        question_types = ["multiple_choice", "true_false"]

    # Get document
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    # Retrieve relevant chunks
    rag = get_rag_service()
    search_query = topic if topic else f"main concepts in {doc.original_filename}"
    retrieved = rag.search(
        search_query,
        top_k=8,
        document_ids=[document_id],
        min_score=0.0,
    )

    if not retrieved:
        # Fall back to first chunks in DB
        db_chunks = (
            db.query(Chunk)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
            .limit(6)
            .all()
        )
        context = "\n\n".join(c.text for c in db_chunks)
    else:
        context = "\n\n".join(c.text for c in retrieved)

    if not context.strip():
        raise ValueError("No content available to generate quiz questions. Ensure the document is processed.")

    effective_topic = topic or doc.original_filename

    # Generate via AI model
    model = get_model()
    response = model.generate_quiz(
        context=context,
        topic=effective_topic,
        difficulty=difficulty,
        num_questions=num_questions,
        question_types=question_types,
    )

    raw_questions = _parse_quiz_json(response.text)

    if not raw_questions:
        logger.warning(f"No questions parsed. Raw output: {response.text[:300]}")
        # Return a fallback question
        raw_questions = [{
            "id": 1,
            "type": "multiple_choice",
            "question": f"Which of the following is a key concept in {effective_topic}?",
            "options": {"A": "See your study material", "B": "N/A", "C": "N/A", "D": "N/A"},
            "correct_answer": "A",
            "explanation": "Please process your document and try again for better questions.",
            "topic": effective_topic,
            "difficulty": difficulty,
        }]

    questions = []
    for i, q in enumerate(raw_questions[:num_questions]):
        questions.append(QuizQuestion(
            id=q.get("id", i + 1),
            type=q.get("type", "multiple_choice"),
            question=q.get("question", ""),
            options=q.get("options"),
            correct_answer=str(q.get("correct_answer", "")),
            explanation=q.get("explanation", ""),
            topic=q.get("topic", effective_topic),
            difficulty=q.get("difficulty", difficulty),
        ))

    return questions


def evaluate_quiz(
    db: Session,
    quiz_id: str,
    document_id: Optional[int],
    questions: List[Dict],
    user_answers: Dict[int, str],   # {question_id: user_answer}
) -> QuizResult:
    """
    Evaluate submitted quiz answers.
    Store results in DB and update topic mastery scores.
    """
    correct_count = 0
    results = []
    topic_scores: Dict[str, List[bool]] = {}

    for q in questions:
        qid = q["id"]
        user_ans = user_answers.get(qid, "").strip()
        correct_ans = str(q.get("correct_answer", "")).strip()
        topic = q.get("topic", "General")

        # Flexible comparison
        is_correct = _compare_answers(
            user_answer=user_ans,
            correct_answer=correct_ans,
            question_type=q.get("type", "multiple_choice"),
        )

        if is_correct:
            correct_count += 1

        if topic not in topic_scores:
            topic_scores[topic] = []
        topic_scores[topic].append(is_correct)

        # Save attempt
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            document_id=document_id,
            topic=topic,
            difficulty=q.get("difficulty", "medium"),
            question_text=q.get("question", ""),
            question_type=q.get("type", "multiple_choice"),
            correct_answer=correct_ans,
            user_answer=user_ans,
            is_correct=is_correct,
            explanation=q.get("explanation", ""),
            timestamp=_now(),
        )
        db.add(attempt)

        results.append({
            **q,
            "user_answer": user_ans,
            "is_correct": is_correct,
        })

    # Update topic mastery
    for topic, scores in topic_scores.items():
        mastery = db.query(TopicMastery).filter(TopicMastery.topic == topic).first()
        if not mastery:
            mastery = TopicMastery(
                topic=topic,
                questions_attempted=0,
                correct_answers=0,
                score=0.0,
            )
            db.add(mastery)
            db.flush()
        mastery.questions_attempted = (mastery.questions_attempted or 0) + len(scores)
        mastery.correct_answers = (mastery.correct_answers or 0) + sum(1 for s in scores if s)
        mastery.score = mastery.correct_answers / max(mastery.questions_attempted, 1)
        mastery.last_studied = _now()
        if document_id:
            doc_ids = mastery.document_ids or []
            if document_id not in doc_ids:
                doc_ids.append(document_id)
                mastery.document_ids = doc_ids

    db.commit()

    total = len(questions)
    score_pct = (correct_count / max(total, 1)) * 100

    # Identify weak/strong topics
    weak_topics = [t for t, s in topic_scores.items() if sum(s) / len(s) < 0.5]
    strong_topics = [t for t, s in topic_scores.items() if sum(s) / len(s) >= 0.8]

    recommendations = []
    for t in weak_topics:
        recommendations.append(f"Review {t} — you got less than 50% correct in this topic.")
    if score_pct >= 80:
        recommendations.append("Great job! Try a harder difficulty level for a challenge.")
    elif score_pct < 40:
        recommendations.append("Take more time to review the material before trying again.")

    return QuizResult(
        quiz_id=quiz_id,
        total_questions=total,
        correct=correct_count,
        score_percent=round(score_pct, 1),
        questions=results,
        weak_topics=weak_topics,
        strong_topics=strong_topics,
        recommendations=recommendations,
    )


def _compare_answers(user_answer: str, correct_answer: str, question_type: str) -> bool:
    """
    Flexible answer comparison.
    - Multiple choice / True/False: exact match (case-insensitive)
    - Short answer: check if key words from correct answer appear in user answer
    """
    ua = user_answer.strip().lower()
    ca = correct_answer.strip().lower()

    if question_type in ("multiple_choice", "true_false"):
        return ua == ca

    # Short answer: keyword overlap
    if not ua:
        return False
    ca_words = set(re.findall(r'\w+', ca))
    ua_words = set(re.findall(r'\w+', ua))
    stop_words = {"a", "an", "the", "is", "are", "was", "were", "of", "in", "to", "and", "or"}
    ca_keywords = ca_words - stop_words
    if not ca_keywords:
        return len(ua_words) > 0
    overlap = len(ca_keywords & ua_words) / len(ca_keywords)
    return overlap >= 0.4


def get_quiz_history(db: Session, limit: int = 50) -> List[Dict]:
    """Return recent quiz attempts grouped by quiz_id."""
    attempts = (
        db.query(QuizAttempt)
        .order_by(QuizAttempt.timestamp.desc())
        .limit(limit)
        .all()
    )
    quiz_map: Dict[str, Dict] = {}
    for a in attempts:
        if a.quiz_id not in quiz_map:
            quiz_map[a.quiz_id] = {
                "quiz_id": a.quiz_id,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "topic": a.topic,
                "difficulty": a.difficulty,
                "total": 0,
                "correct": 0,
            }
        quiz_map[a.quiz_id]["total"] += 1
        if a.is_correct:
            quiz_map[a.quiz_id]["correct"] += 1

    for q in quiz_map.values():
        q["score_percent"] = round((q["correct"] / max(q["total"], 1)) * 100, 1)

    return list(quiz_map.values())
