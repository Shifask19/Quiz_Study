"""
SnapStudy Configuration
All settings loaded from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "SnapStudy"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:4173"

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/snapstudy.db"

    # Storage
    UPLOAD_DIR: str = str(BASE_DIR / "data" / "uploads")
    VECTOR_DB_DIR: str = str(BASE_DIR / "data" / "vector_db")
    MAX_UPLOAD_SIZE_MB: int = 50

    # AI Provider
    AI_PROVIDER: str = "mock"  # mock | local_llm | onnx | qualcomm_ai_hub
    LOCAL_LLM_URL: str = "http://localhost:11434"
    LOCAL_LLM_MODEL: str = "llama3.2:3b"
    LOCAL_LLM_TIMEOUT: int = 120
    ONNX_LLM_PATH: str = str(BASE_DIR / "models" / "llm.onnx")
    ONNX_EMBED_PATH: str = str(BASE_DIR / "models" / "embeddings.onnx")

    # Qualcomm AI Hub
    QAI_HUB_API_TOKEN: str = ""
    QAI_HUB_MODEL_ID: str = ""
    QAI_HUB_DEVICE: str = "snapdragon-x-elite"

    # Embedding
    EMBEDDING_PROVIDER: str = "sentence_transformers"  # sentence_transformers | onnx | qualcomm_ai_hub | mock
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # RAG
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    TOP_K_RETRIEVAL: int = 5

    # Voice
    VOICE_ENABLED: bool = False
    TTS_MODEL: str = "local"
    STT_MODEL: str = "local"

    # Benchmark
    BENCHMARK_ITERATIONS: int = 3


settings = Settings()

# Ensure directories exist
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.VECTOR_DB_DIR).mkdir(parents=True, exist_ok=True)
Path(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
