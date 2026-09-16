"""Smoke test: the actual HTTP API surface (upload -> chat -> documents ->
delete) against the live Gemini + Supabase backends. Real network calls, not
a unit test - run manually while verifying setup, per docs/phases.md Phase 4.
Cleans up after itself.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
client = TestClient(app)


def test_status_ok():
    res = client.get("/api/status")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "chatModel" in body


def test_chat_without_documents_still_responds():
    res = client.post("/api/chat", json={"message": "Hello!", "history": []})
    assert res.status_code == 200
    assert res.json()["reply"]


def test_chat_requires_a_message():
    res = client.post("/api/chat", json={"message": "", "history": []})
    assert res.status_code == 400
    assert res.json() == {"error": "Message is required."}


def test_upload_rejects_unsupported_file_type():
    res = client.post(
        "/api/upload", files={"documents": ("notes.csv", b"a,b\n1,2", "text/csv")}
    )
    assert res.status_code == 400
    assert res.json()["errors"][0]["error"] == "Only .txt, .md, or .pdf files are supported"


def test_upload_chat_grounding_and_delete_cycle():
    doc_id = None
    try:
        pdf_bytes = (FIXTURES / "sample.pdf").read_bytes()
        upload_res = client.post(
            "/api/upload",
            files={"documents": ("sample.pdf", pdf_bytes, "application/pdf")},
        )
        assert upload_res.status_code == 200
        uploaded = upload_res.json()["documents"]
        assert len(uploaded) == 1
        doc_id = uploaded[0]["id"]

        docs_res = client.get("/api/documents")
        assert any(d["id"] == doc_id for d in docs_res.json()["documents"])

        chat_res = client.post(
            "/api/chat",
            json={"message": "What does this document contain?", "history": []},
        )
        assert chat_res.status_code == 200
        chat_body = chat_res.json()
        assert chat_body["reply"]
        assert len(chat_body["sources"]) > 0
    finally:
        if doc_id is not None:
            delete_res = client.delete(f"/api/documents/{doc_id}")
            assert delete_res.status_code == 200
