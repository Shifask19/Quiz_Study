"""
API endpoint tests using FastAPI TestClient.
Tests cover documents, tutor, quiz, and analytics endpoints.
"""
import pytest
import io


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "ai_provider" in data

    def test_health_includes_version(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert "version" in data


class TestDocumentEndpoints:
    def test_list_documents_empty(self, client):
        resp = client.get("/api/documents/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_upload_txt_document(self, client, test_txt_file):
        with open(test_txt_file, "rb") as f:
            resp = client.post(
                "/api/documents/upload",
                files={"file": ("test_notes.txt", f, "text/plain")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["filename"] == "test_notes.txt"
        assert data["file_type"] == "txt"

    def test_upload_unsupported_type_rejected(self, client):
        resp = client.post(
            "/api/documents/upload",
            files={"file": ("test.exe", io.BytesIO(b"bad"), "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_upload_empty_file_rejected(self, client):
        resp = client.post(
            "/api/documents/upload",
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        )
        assert resp.status_code == 400

    def test_get_nonexistent_document_404(self, client):
        resp = client.get("/api/documents/99999")
        assert resp.status_code == 404

    def test_delete_nonexistent_document_404(self, client):
        resp = client.delete("/api/documents/99999")
        assert resp.status_code == 404


class TestTutorEndpoints:
    def test_ask_no_documents_returns_fallback(self, client):
        resp = client.post("/api/tutor/ask", json={
            "question": "What is database normalization?",
            "document_ids": [99999],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert isinstance(data["found_in_documents"], bool)

    def test_create_conversation(self, client):
        resp = client.post("/api/tutor/conversations", json={"title": "Test Conv"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Conv"
        assert "id" in data

    def test_list_conversations(self, client):
        resp = client.get("/api/tutor/conversations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_delete_nonexistent_conversation_404(self, client):
        resp = client.delete("/api/tutor/conversations/99999")
        assert resp.status_code == 404

    def test_ask_with_conversation_id(self, client):
        # Create conversation first
        conv_resp = client.post("/api/tutor/conversations", json={"title": "Test"})
        conv_id = conv_resp.json()["id"]
        # Ask a question
        resp = client.post("/api/tutor/ask", json={
            "question": "Explain sorting algorithms",
            "conversation_id": conv_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == conv_id


class TestQuizEndpoints:
    def test_generate_quiz_invalid_document(self, client):
        resp = client.post("/api/quiz/generate", json={
            "document_id": 99999,
            "difficulty": "medium",
            "num_questions": 3,
        })
        assert resp.status_code == 404

    def test_generate_quiz_invalid_difficulty(self, client):
        resp = client.post("/api/quiz/generate", json={
            "document_id": 1,
            "difficulty": "impossible",
        })
        assert resp.status_code == 400

    def test_quiz_history(self, client):
        resp = client.get("/api/quiz/history")
        assert resp.status_code == 200

    def test_quiz_stats(self, client):
        resp = client.get("/api/quiz/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_attempts" in data
        assert "overall_accuracy" in data


class TestAnalyticsEndpoints:
    def test_dashboard(self, client):
        resp = client.get("/api/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "documents_uploaded" in data
        assert "quiz_accuracy" in data

    def test_mastery_list(self, client):
        resp = client.get("/api/analytics/mastery")
        assert resp.status_code == 200
        data = resp.json()
        assert "mastery" in data

    def test_weak_topics(self, client):
        resp = client.get("/api/analytics/weak-topics")
        assert resp.status_code == 200

    def test_model_info(self, client):
        resp = client.get("/api/analytics/model-info")
        assert resp.status_code == 200
        data = resp.json()
        assert "model" in data
        assert "provider" in data
        assert "backend" in data

    def test_benchmark_history(self, client):
        resp = client.get("/api/analytics/benchmark")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_model" in data
        assert "history" in data


class TestEndToEndFlow:
    """
    Full E2E: upload → process → ask → retrieve chunks → generate answer → show source
    """
    def test_upload_ask_get_answer(self, client, test_txt_file):
        # 1. Upload document
        with open(test_txt_file, "rb") as f:
            upload_resp = client.post(
                "/api/documents/upload",
                files={"file": ("e2e_test.txt", f, "text/plain")},
            )
        assert upload_resp.status_code == 200
        doc_id = upload_resp.json()["id"]

        # 2. Wait for processing (background task runs synchronously in TestClient)
        import time
        for _ in range(10):
            doc_resp = client.get(f"/api/documents/{doc_id}")
            status = doc_resp.json()["processing_status"]
            if status in ("ready", "failed"):
                break
            time.sleep(0.5)

        # 3. Ask a question
        ask_resp = client.post("/api/tutor/ask", json={
            "question": "What is database normalization?",
            "document_ids": [doc_id],
        })
        assert ask_resp.status_code == 200
        answer_data = ask_resp.json()
        assert len(answer_data["answer"]) > 0
        assert "found_in_documents" in answer_data
        # sources may or may not be populated depending on processing status
        assert isinstance(answer_data["sources"], list)

        # 4. Clean up
        client.delete(f"/api/documents/{doc_id}")
