import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings

QUESTION = {"question": "How do plants make food?", "grade": 10, "subject": "Science"}


@pytest.fixture
def client(rag, monkeypatch):
    monkeypatch.setattr(main, "rag", rag)  # use the small fake RAG instead of the real index
    monkeypatch.setattr(main, "get_rag", lambda: rag)
    return TestClient(main.app)            # (not used with "with", so startup doesn't run)


def stream_events(client, body):
    response = client.post("/api/ask/stream", json=body)
    return [json.loads(line) for line in response.text.splitlines()]


def test_subjects_lists_the_indexed_textbooks(client):
    assert [s["subject"] for s in client.get("/api/subjects").json()] == ["Science", "English", "Science"]


def test_ask_answers_with_sources(client):
    response = client.post("/api/ask", json=QUESTION)
    assert response.status_code == 200
    assert response.json()["found"] is True
    assert response.json()["sources"][0]["chapter"] == 6


def test_ask_rejects_unknown_subject(client):
    response = client.post("/api/ask", json={**QUESTION, "subject": "Physics"})
    assert response.status_code == 400


def test_ask_rejects_empty_question(client):
    response = client.post("/api/ask", json={**QUESTION, "question": ""})
    assert response.status_code == 422


def test_stream_sends_one_json_event_per_line(client):
    events = stream_events(client, QUESTION)
    assert events[0]["type"] == "token"
    assert events[-1]["type"] == "done"


def test_stream_reports_ollama_errors_instead_of_crashing(client, fake_llm, monkeypatch):
    def ollama_down(*args, **kwargs):
        raise ConnectionError("connection refused")
    monkeypatch.setattr(type(fake_llm), "stream_complete", ollama_down)

    events = stream_events(client, QUESTION)
    assert events[-1]["type"] == "error"
    assert "Is it running?" in events[-1]["message"]


def test_missing_index_gives_a_helpful_error(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "rag", None)
    monkeypatch.setattr(settings, "storage_dir", tmp_path)  # an empty folder: no index here
    response = TestClient(main.app).get("/api/subjects")
    assert response.status_code == 503
    assert "python -m app.ingest" in response.json()["detail"]


def test_health_reports_when_ollama_is_down(client, monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:9")  # nothing listens here
    body = client.get("/api/health").json()
    assert body["status"] == "error"
    assert body["index"].startswith("ok")
    assert "not reachable" in body["ollama"]


def test_feedback_is_saved(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    body = {"question": "Q?", "answer": "A.", "helpful": True, "grade": 10, "subject": "Science"}
    assert client.post("/api/feedback", json=body).status_code == 204
    saved = json.loads(settings.feedback_file.read_text(encoding="utf-8"))
    assert saved["helpful"] is True and saved["question"] == "Q?"


def test_web_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "NCERT Textbook Assistant" in response.text


def test_metrics_endpoint_returns_summary(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    # Post a question to generate a metric entry
    client.post("/api/ask", json=QUESTION)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_conversations" in data
    assert data["total_conversations"] >= 1
    assert data["found_count"] >= 1
    assert len(data["recent_conversations"]) >= 1
    rec = data["recent_conversations"][0]
    assert rec["question"] == QUESTION["question"]
    assert "total_latency_s" in rec


def test_ask_with_conversation_history(client):
    body = {
        **QUESTION,
        "question": "How do they absorb sunlight?",
        "history": [
            {"role": "user", "content": "What are green plants?"},
            {"role": "assistant", "content": "Green plants make food using sunlight [1]."},
        ],
    }
    response = client.post("/api/ask", json=body)
    assert response.status_code == 200
    assert response.json()["found"] is True
