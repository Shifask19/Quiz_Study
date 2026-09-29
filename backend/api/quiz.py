"""
Quiz Lab API endpoints.

POST /quiz/generate              Generate quiz questions
POST /quiz/evaluate              Evaluate submitted answers
GET  /quiz/history               Get quiz history
GET  /quiz/stats                 Quiz performance stats
"""
import uuid
import logging
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.quiz_service import generate_quiz, evaluate_quiz, get_quiz_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quiz", tags=["quiz"])


class GenerateQuizRequest(BaseModel):
    document_id: int
    topic: Optional[str] = None
    difficulty: str = "medium"
    num_questions: int = Field(default=5, ge=1, le=20)
    question_types: Optional[List[str]] = None


class QuizQuestionResponse(BaseModel):
    id: int
    type: str
    question: str
    options: Optional[Dict[str, str]]
    topic: str
    difficulty: str


class GenerateQuizResponse(BaseModel):
    quiz_id: str
    questions: List[QuizQuestionResponse]
    document_id: int
    topic: Optional[str]
    difficulty: str


class EvaluateRequest(BaseModel):
    quiz_id: str
    document_id: Optional[int] = None
    questions: List[Dict]                  # full question objects from generate
    user_answers: Dict[str, str]           # {"1": "A", "2": "True", ...}


class EvaluateResponse(BaseModel):
    quiz_id: str
    total_questions: int
    correct: int
    score_percent: float
    questions: List[Dict]
    weak_topics: List[str]
    strong_topics: List[str]
    recommendations: List[str]


@router.post("/generate", response_model=GenerateQuizResponse)
def generate_quiz_endpoint(req: GenerateQuizRequest, db: Session = Depends(get_db)):
    """Generate quiz questions from a document."""
    if req.difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(status_code=400, detail="difficulty must be easy, medium, or hard")

    valid_types = {"multiple_choice", "true_false", "short_answer"}
    if req.question_types:
        invalid = set(req.question_types) - valid_types
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid question types: {invalid}. Valid: {valid_types}",
            )

    try:
        questions = generate_quiz(
            db=db,
            document_id=req.document_id,
            topic=req.topic,
            difficulty=req.difficulty,
            num_questions=req.num_questions,
            question_types=req.question_types,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {e}")

    quiz_id = str(uuid.uuid4())
    return GenerateQuizResponse(
        quiz_id=quiz_id,
        questions=[
            QuizQuestionResponse(
                id=q.id,
                type=q.type,
                question=q.question,
                options=q.options,
                topic=q.topic,
                difficulty=q.difficulty,
            )
            for q in questions
        ],
        document_id=req.document_id,
        topic=req.topic,
        difficulty=req.difficulty,
    )


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_quiz_endpoint(req: EvaluateRequest, db: Session = Depends(get_db)):
    """Evaluate submitted quiz answers and update mastery."""
    # Convert string keys to int
    user_answers = {int(k): v for k, v in req.user_answers.items()}
    questions = req.questions

    # Attach correct_answer back into question list from the request
    # (caller must include full question objects including correct_answer)
    result = evaluate_quiz(
        db=db,
        quiz_id=req.quiz_id,
        document_id=req.document_id,
        questions=questions,
        user_answers=user_answers,
    )

    return EvaluateResponse(
        quiz_id=result.quiz_id,
        total_questions=result.total_questions,
        correct=result.correct,
        score_percent=result.score_percent,
        questions=result.questions,
        weak_topics=result.weak_topics,
        strong_topics=result.strong_topics,
        recommendations=result.recommendations,
    )


@router.get("/history")
def quiz_history(limit: int = 20, db: Session = Depends(get_db)):
    return get_quiz_history(db, limit=limit)


@router.get("/stats")
def quiz_stats(db: Session = Depends(get_db)):
    from backend.database.models import QuizAttempt
    from sqlalchemy import func, Integer

    total = db.query(func.count(QuizAttempt.id)).scalar() or 0
    correct = db.query(func.count(QuizAttempt.id)).filter(QuizAttempt.is_correct == True).scalar() or 0
    accuracy = round((correct / max(total, 1)) * 100, 1)

    # Per-topic breakdown
    topic_rows = (
        db.query(QuizAttempt.topic)
        .filter(QuizAttempt.topic.isnot(None))
        .distinct()
        .all()
    )
    topic_stats = []
    for (t,) in topic_rows:
        t_total = db.query(func.count(QuizAttempt.id)).filter(QuizAttempt.topic == t).scalar() or 0
        t_correct = db.query(func.count(QuizAttempt.id)).filter(
            QuizAttempt.topic == t, QuizAttempt.is_correct == True
        ).scalar() or 0
        topic_stats.append({
            "topic": t,
            "total": t_total,
            "correct": t_correct,
            "accuracy": round((t_correct / max(t_total, 1)) * 100, 1),
        })

    return {
        "total_attempts": total,
        "total_correct": correct,
        "overall_accuracy": accuracy,
        "by_topic": topic_stats,
    }
