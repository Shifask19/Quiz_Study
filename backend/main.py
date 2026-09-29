"""
SnapStudy — FastAPI application entry point.

Start with:
  uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config.settings import settings
from backend.database import init_db
from backend.api.documents import router as documents_router
from backend.api.tutor import router as tutor_router
from backend.api.quiz import router as quiz_router
from backend.api.analytics import router as analytics_router
from backend.api.voice import router as voice_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# App factory
# ──────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    init_db()
    logger.info("Database initialized")

    from backend.models.factory import get_model
    model = get_model()
    info = model.get_info()
    logger.info(f"AI Provider: {info.provider} | Model: {info.name} | Available: {info.is_available}")

    from backend.services.rag_service import get_rag_service
    rag = get_rag_service()
    stats = rag.get_stats()
    logger.info(f"Vector index loaded: {stats['total_vectors']} vectors")

    yield
    # ── Shutdown ─────────────────────────────────────────
    logger.info("SnapStudy shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="SnapStudy API",
        description=(
            "SnapStudy — Private AI Tutor, Powered On-Device.\n\n"
            "Processes study documents locally and provides AI-powered tutoring, "
            "quiz generation, and adaptive revision — designed for Snapdragon-powered devices."
        ),
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(documents_router, prefix="/api")
    app.include_router(tutor_router, prefix="/api")
    app.include_router(quiz_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")
    app.include_router(voice_router, prefix="/api")

    # Health check
    @app.get("/api/health")
    def health():
        from backend.models.factory import get_model
        model_info = get_model().get_info()
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "ai_provider": model_info.provider,
            "ai_model": model_info.name,
            "ai_available": model_info.is_available,
            "privacy": "on-device",
        }

    # Serve React frontend in production
    frontend_dist = ROOT / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

        @app.get("/{full_path:path}")
        def serve_spa(full_path: str):
            index = frontend_dist / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return {"error": "Frontend not built. Run: cd frontend && npm run build"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
