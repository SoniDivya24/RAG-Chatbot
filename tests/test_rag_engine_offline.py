"""Offline tests for RagEngine on the local store with a fake embedder: the
load -> dedup -> retrieve -> delete cycle without any API call."""

import pytest

from app.rag_engine import RagEngine
from app.vector_store import LocalVectorStore

LEAVE_POLICY = (
    "Acme Robotics leave policy. Full-time employees accrue 18 days of paid vacation "
    "per year plus 10 paid sick days. Vacation requests need 5 business days notice."
)
LUNCH_MENU = (
    "Canteen menu. Monday soup and bread, Tuesday pasta with tomato sauce, "
    "Wednesday curry and rice, Thursday salad bowls, Friday fish and chips."
)


@pytest.fixture
def engine(tmp_path, fake_embedder, monkeypatch):
    # The app's relevance floor (0.62) is tuned for real Gemini embeddings; the
    # fake bag-of-words vectors score lower, so use a floor that separates this
    # test data's on-topic (0.36-0.76) from off-topic (0.00-0.19) queries.
    monkeypatch.setattr("app.rag_engine.MIN_RELEVANCE_SCORE", 0.25)
    return RagEngine(store=LocalVectorStore(tmp_path / "data"), embedder=fake_embedder)


def test_load_retrieve_and_delete(engine):
    doc = engine.load_document(LEAVE_POLICY, "policy.txt")
    assert doc["duplicate"] is False and doc["chunk_count"] >= 1
    assert engine.has_documents()

    results = engine.retrieve("how many vacation days do employees get", k=3)

    assert results and "18 days" in results[0]["text"]
    assert results[0]["metadata"]["source"] == "policy.txt"

    engine.delete_document(doc["id"])
    assert not engine.has_documents()
    assert engine.list_documents() == []


def test_duplicate_content_is_not_reindexed_or_reembedded(engine, fake_embedder):
    first = engine.load_document(LEAVE_POLICY, "policy.txt")
    embedded_before = fake_embedder.calls["texts"]

    second = engine.load_document(LEAVE_POLICY, "policy-renamed.txt")

    assert second["duplicate"] is True and second["id"] == first["id"]
    assert fake_embedder.calls["texts"] == embedded_before  # no embedding spent
    assert len(engine.list_documents()) == 1


def test_retrieval_searches_across_all_documents(engine):
    engine.load_document(LEAVE_POLICY, "policy.txt")
    engine.load_document(LUNCH_MENU, "menu.txt")

    policy = engine.retrieve("paid vacation days and sick days", k=2)
    menu = engine.retrieve("what pasta is served on tuesday", k=2)

    assert policy[0]["metadata"]["source"] == "policy.txt"
    assert menu[0]["metadata"]["source"] == "menu.txt"


def test_low_relevance_matches_are_filtered_out(engine):
    engine.load_document(LEAVE_POLICY, "policy.txt")

    assert engine.retrieve("zebra quantum astrophysics volcano", k=3) == []


def test_empty_document_is_rejected(engine):
    with pytest.raises(ValueError, match="no usable text"):
        engine.load_document("   \n  ", "empty.txt")
