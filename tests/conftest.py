"""
Test configuration and shared fixtures for SnapStudy test suite.
"""
import os
import sys
import pytest
from pathlib import Path

# ── Set env vars BEFORE any backend module is imported ───────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_test_upload_dir = str(ROOT / "tests" / "tmp_uploads")
_test_vector_dir = str(ROOT / "tests" / "tmp_vector_db")
_test_db_path    = str(ROOT / "tests" / "test_snapstudy.db")

os.environ["DATABASE_URL"]      = f"sqlite:///{_test_db_path}"
os.environ["AI_PROVIDER"]        = "mock"
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["DEBUG"]              = "false"
os.environ["UPLOAD_DIR"]         = _test_upload_dir
os.environ["VECTOR_DB_DIR"]      = _test_vector_dir

Path(_test_upload_dir).mkdir(parents=True, exist_ok=True)
Path(_test_vector_dir).mkdir(parents=True, exist_ok=True)
# Remove stale test DB from previous run
if Path(_test_db_path).exists():
    Path(_test_db_path).unlink()


@pytest.fixture(scope="session")
def test_txt_file(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("docs")
    f = d / "test_notes.txt"
    f.write_text(
        "Database Normalization\n\n"
        "Normalization is the process of organizing a relational database to reduce redundancy.\n"
        "First Normal Form (1NF): All attributes must be atomic.\n"
        "Second Normal Form (2NF): No partial dependencies.\n"
        "Third Normal Form (3NF): No transitive dependencies.\n\n"
        "Sorting Algorithms\n\n"
        "Merge Sort divides the array and merges sorted halves. Time: O(n log n).\n"
        "Quick Sort selects a pivot and partitions. Time: O(n log n) average.\n"
        "Bubble Sort compares adjacent elements. Time: O(n squared).\n"
    )
    return f


@pytest.fixture(scope="session")
def db_session():
    """Unit-test DB session (no HTTP layer)."""
    from backend.database.connection import SessionLocal, init_db
    init_db()
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient backed by the test SQLite file DB."""
    import backend.services.rag_service as rag_mod
    rag_mod._rag_instance = None

    from backend.models.factory import reset_model
    reset_model()

    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as c:
        yield c


# ── Cleanup after session ─────────────────────────────────────────────────────
def pytest_sessionfinish(session, exitstatus):
    """Remove the test DB file after all tests run."""
    p = Path(_test_db_path)
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass
