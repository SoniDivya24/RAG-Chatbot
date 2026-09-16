"""Smoke test: chunk + embed against the live Gemini embeddings API. Real
network call, not a unit test — run manually while verifying setup, per
docs/phases.md Phase 2.
"""

from app.rag_engine import RagEngine

SAMPLE_TEXT = """
Acme Robotics -- Leave Policy

Full-time employees accrue 18 days of paid vacation per year, plus 10 paid
sick days. Vacation requests must be submitted at least 5 business days in
advance through the HR portal.
""" * 5  # repeated so it's long enough to actually split into multiple chunks


def test_chunk_text_splits_into_multiple_chunks():
    engine = RagEngine()
    chunks = engine.chunk_text(SAMPLE_TEXT)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_embed_chunks_returns_matching_vectors():
    engine = RagEngine()
    chunks = engine.chunk_text(SAMPLE_TEXT)
    vectors = engine.embed_chunks(chunks)

    assert len(vectors) == len(chunks)
    assert all(len(v) == 3072 for v in vectors)  # gemini-embedding-001 dimension


def test_embed_query_returns_same_dimension_as_chunks():
    engine = RagEngine()
    query_vector = engine.embed_query("How many vacation days do I get?")
    assert len(query_vector) == 3072
