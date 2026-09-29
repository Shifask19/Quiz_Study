#!/usr/bin/env python3
"""
SnapStudy startup script.
Initialises the database, loads demo data if needed, and starts the server.

Usage:
  python scripts/start.py
"""
import sys
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    print("=" * 50)
    print("  SnapStudy — Private AI Tutor, On-Device")
    print("=" * 50)

    # Init DB
    print("\n[1/3] Initialising database...")
    from backend.database.connection import init_db
    init_db()
    print("      Database ready.")

    # Check model
    print("\n[2/3] Checking AI model...")
    from backend.models.factory import get_model, reset_model
    reset_model()
    model = get_model()
    info = model.get_info()
    print(f"      Provider : {info.provider}")
    print(f"      Model    : {info.name}")
    print(f"      Available: {info.is_available}")
    if info.provider == "mock":
        print("      NOTE: Running in mock mode. Set AI_PROVIDER=local_llm for real answers.")

    # Check demo
    print("\n[3/3] Checking demo data...")
    from backend.database.connection import SessionLocal
    from backend.database.models import Document
    db = SessionLocal()
    doc_count = db.query(Document).count()
    db.close()
    if doc_count == 0:
        print("      No documents found. Loading demo data...")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "create_demo_data.py")], check=False)
    else:
        print(f"      {doc_count} document(s) found.")

    # Start server
    print("\nStarting server at http://localhost:8000")
    print("API docs at  http://localhost:8000/api/docs")
    print("Press Ctrl+C to stop.\n")
    from backend.config.settings import settings
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", settings.HOST,
        "--port", str(settings.PORT),
        "--reload" if settings.DEBUG else "--no-access-log",
    ])

if __name__ == "__main__":
    main()
