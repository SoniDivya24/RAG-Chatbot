"""Offline tests for the local vector store (Chroma + JSON registry): no API
calls, a throwaway folder per test."""

import pytest

from app.vector_store import LocalVectorStore

A = [1.0, 0.0, 0.0]
B = [0.0, 1.0, 0.0]


def test_add_list_count_and_search_order(tmp_path):
    store = LocalVectorStore(tmp_path)
    doc = store.add_document("notes.txt", ["alpha", "beta"], [A, B], "hash-1")

    assert doc["source_name"] == "notes.txt"
    assert doc["chunk_count"] == 2
    assert "content_hash" not in doc  # internal detail stays internal
    assert store.count_chunks() == 2
    assert [d["id"] for d in store.list_documents()] == [doc["id"]]

    results = store.similarity_search(A, k=2)
    assert [r["text"] for r in results] == ["alpha", "beta"]
    assert results[0]["score"] == pytest.approx(1.0, abs=1e-4)
    assert results[1]["score"] == pytest.approx(0.0, abs=1e-4)
    assert results[0]["metadata"] == {
        "source": "notes.txt",
        "document_id": doc["id"],
        "chunk_index": 0,
    }


def test_search_on_empty_store_returns_nothing(tmp_path):
    assert LocalVectorStore(tmp_path).similarity_search(A, k=5) == []


def test_search_spans_all_documents_and_k_is_capped(tmp_path):
    store = LocalVectorStore(tmp_path)
    store.add_document("one.txt", ["alpha"], [A], "h1")
    store.add_document("two.txt", ["beta"], [B], "h2")

    results = store.similarity_search(B, k=10)  # k larger than what's stored
    assert [r["metadata"]["source"] for r in results] == ["two.txt", "one.txt"]


def test_find_by_content_hash(tmp_path):
    store = LocalVectorStore(tmp_path)
    doc = store.add_document("a.txt", ["alpha"], [A], "same-hash")

    assert store.find_by_content_hash("same-hash")["id"] == doc["id"]
    assert store.find_by_content_hash("other") is None


def test_delete_removes_chunks_and_registry_entry(tmp_path):
    store = LocalVectorStore(tmp_path)
    keep = store.add_document("keep.txt", ["alpha"], [A], "h1")
    drop = store.add_document("drop.txt", ["beta", "gamma"], [B, B], "h2")

    store.delete_document(drop["id"])

    assert store.count_chunks() == 1
    assert [d["id"] for d in store.list_documents()] == [keep["id"]]
    assert store.find_by_content_hash("h2") is None
    store.delete_document(drop["id"])  # deleting twice is harmless


def test_library_survives_a_restart(tmp_path):
    first = LocalVectorStore(tmp_path)
    doc = first.add_document("persist.txt", ["alpha"], [A], "h1")

    second = LocalVectorStore(tmp_path)  # a fresh process opening the same folder

    assert second.count_chunks() == 1
    assert second.list_documents()[0]["id"] == doc["id"]
    assert second.similarity_search(A, k=1)[0]["text"] == "alpha"


def test_failed_insert_leaves_nothing_behind(tmp_path):
    store = LocalVectorStore(tmp_path)

    with pytest.raises(RuntimeError, match="Failed to save chunks"):
        # Two chunks but one vector: the insert must fail and roll back.
        store.add_document("bad.txt", ["alpha", "beta"], [A], "h-bad")

    assert store.count_chunks() == 0
    assert store.list_documents() == []
