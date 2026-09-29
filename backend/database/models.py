"""
SQLAlchemy ORM models for SnapStudy database.
"""
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc)
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text,
    DateTime, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    file_path = Column(String(500), nullable=False)
    upload_date = Column(DateTime, default=_now)
    processing_status = Column(
        SAEnum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        nullable=False
    )
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    key_concepts = Column(JSON, nullable=True)   # list of strings
    topics = Column(JSON, nullable=True)          # list of topic strings

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "upload_date": self.upload_date.isoformat() if self.upload_date else None,
            "processing_status": self.processing_status.value if self.processing_status else "pending",
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "summary": self.summary,
            "key_concepts": self.key_concepts or [],
            "topics": self.topics or [],
        }


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    embedding_id = Column(String(100), nullable=True)  # reference to FAISS index
    word_count = Column(Integer, default=0)
    topic = Column(String(255), nullable=True)

    document = relationship("Document", back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), default="New Conversation")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=datetime.utcnow)
    document_ids = Column(JSON, nullable=True)  # which docs are in context

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(50), nullable=False)   # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=_now)
    sources = Column(JSON, nullable=True)        # list of {doc, page, excerpt}
    extra_metadata = Column(JSON, nullable=True)

    conversation = relationship("Conversation", back_populates="messages")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(String(100), nullable=False)  # UUID for grouping
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    topic = Column(String(255), nullable=True)
    difficulty = Column(String(50), default="medium")
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), default="multiple_choice")
    correct_answer = Column(Text, nullable=False)
    user_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    explanation = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=_now)
    time_taken_seconds = Column(Float, nullable=True)


class TopicMastery(Base):
    __tablename__ = "topic_mastery"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(255), nullable=False, unique=True)
    score = Column(Float, default=0.0)            # 0.0 – 1.0
    questions_attempted = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    time_spent_seconds = Column(Float, default=0.0)
    last_studied = Column(DateTime, nullable=True)
    document_ids = Column(JSON, nullable=True)

    def mastery_percent(self) -> float:
        if self.questions_attempted == 0:
            return 0.0
        return round((self.correct_answers / self.questions_attempted) * 100, 1)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_type = Column(String(50), default="revision")  # revision | quiz | tutor
    started_at = Column(DateTime, default=_now)
    ended_at = Column(DateTime, nullable=True)
    document_ids = Column(JSON, nullable=True)
    topics = Column(JSON, nullable=True)
    questions_asked = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    notes = Column(Text, nullable=True)


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id = Column(Integer, primary_key=True, index=True)
    run_at = Column(DateTime, default=_now)
    model_name = Column(String(255))
    backend = Column(String(100))
    device = Column(String(255))
    avg_inference_latency_ms = Column(Float)
    tokens_per_second = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    embedding_latency_ms = Column(Float, nullable=True)
    retrieval_latency_ms = Column(Float, nullable=True)
    iterations = Column(Integer, default=3)
    raw_results = Column(JSON, nullable=True)
