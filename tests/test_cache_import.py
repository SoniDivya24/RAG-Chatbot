"""Offline tests for seeding the embedding cache from another project's vectors."""

import json

import chromadb
import pytest
from chromadb.config import Settings

from app.cache_import import import_chroma, import_json_cache
from tests.fakes import fake_vector


def _make_index(path, collections):
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    for name, texts in collections.items():
        col = client.create_collection(name, configuration={"hnsw": {"space": "cosine"}})
        col.add(
            ids=[f"{name}-{i}" for i in range(len(texts))],
            documents=texts,
            embeddings=[fake_vector(t) for t in texts],
        )


def test_chroma_import_makes_those_texts_free_to_embed(tmp_path, fake_embedder):
    _make_index(tmp_path / "proto", {"only": ["alpha beta", "gamma delta"]})

    stored = import_chroma(tmp_path / "proto", fake_embedder)
    vectors = fake_embedder.embed_documents(["gamma delta", "alpha beta"])

    assert stored == 2
    assert fake_embedder.calls["texts"] == 0  # nothing was sent to the "API"
    assert vectors[0] == pytest.approx(fake_vector("gamma delta"), abs=1e-6)


def test_chroma_import_never_modifies_the_source(tmp_path, fake_embedder):
    _make_index(tmp_path / "proto", {"only": ["alpha beta"]})
    before = {p.name: p.stat().st_mtime_ns for p in (tmp_path / "proto").rglob("*") if p.is_file()}

    import_chroma(tmp_path / "proto", fake_embedder)

    after = {p.name: p.stat().st_mtime_ns for p in (tmp_path / "proto").rglob("*") if p.is_file()}
    assert before == after


def test_chroma_import_needs_a_collection_name_when_ambiguous(tmp_path, fake_embedder):
    _make_index(tmp_path / "proto", {"one": ["alpha"], "two": ["beta"]})

    with pytest.raises(ValueError, match="Pass a collection name"):
        import_chroma(tmp_path / "proto", fake_embedder)
    assert import_chroma(tmp_path / "proto", fake_embedder, collection="two") == 1


def test_missing_index_is_a_clear_error(tmp_path, fake_embedder):
    with pytest.raises(FileNotFoundError):
        import_chroma(tmp_path / "nope", fake_embedder)


def test_json_import_uses_the_shared_key_scheme(tmp_path, fake_embedder):
    key = fake_embedder._key("alpha beta")
    (tmp_path / "cache.json").write_text(json.dumps({key: fake_vector("alpha beta")}))

    assert import_json_cache(tmp_path / "cache.json", fake_embedder) == 1
    fake_embedder.embed_documents(["alpha beta"])
    assert fake_embedder.calls["texts"] == 0
