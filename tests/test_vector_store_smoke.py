"""Smoke test: full load -> retrieve -> delete cycle against the live Supabase
project. Real network calls (Gemini + Supabase), not a unit test — run
manually while verifying setup, per docs/phases.md Phase 3. Cleans up after
itself so it doesn't leave test data behind.
"""

from app.rag_engine import RagEngine

SAMPLE_TEXT = """
Acme Robotics -- Leave Policy

Full-time employees accrue 18 days of paid vacation per year, plus 10 paid
sick days. Vacation requests must be submitted at least 5 business days in
advance through the HR portal.
"""


def test_load_retrieve_and_delete_document():
    engine = RagEngine()
    doc = None
    try:
        doc = engine.load_document(SAMPLE_TEXT, "vector_store_smoke_test.txt")
        assert doc["chunk_count"] >= 1
        assert engine.has_documents()

        results = engine.retrieve("How many vacation days do I get?", k=1)
        assert len(results) == 1
        assert "18 days" in results[0]["text"]
        assert results[0]["metadata"]["source"] == "vector_store_smoke_test.txt"
        assert 0.0 <= results[0]["score"] <= 1.0
    finally:
        if doc is not None:
            engine.delete_document(doc["id"])  # cascades to chunks
