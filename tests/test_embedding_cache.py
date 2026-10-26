"""Offline tests for the embedding cache: what hits the (fake) API, what is
served from disk, and how quota errors are handled."""

import pytest

from app.embeddings import BATCH_SIZE, RETRY_WAIT_SECONDS, CachedEmbedder, EmbeddingQuotaExhausted
from tests.fakes import fake_vector


def test_cached_texts_are_not_embedded_again(fake_embedder):
    first = fake_embedder.embed_documents(["alpha", "beta"])
    assert fake_embedder.calls["texts"] == 2

    second = fake_embedder.embed_documents(["beta", "alpha"])

    assert fake_embedder.calls["texts"] == 2  # nothing new was sent
    assert second == [first[1], first[0]]  # order follows the request, not the cache


def test_duplicates_in_one_request_are_sent_once(fake_embedder):
    vectors = fake_embedder.embed_documents(["alpha", "alpha", "beta", "alpha"])

    assert fake_embedder.calls["texts"] == 2
    assert vectors[0] == vectors[1] == vectors[3] == fake_vector("alpha")


def test_cache_persists_across_instances(tmp_path):
    calls = []

    def fn(texts):
        calls.append(list(texts))
        return [fake_vector(t) for t in texts]

    path = tmp_path / "cache.sqlite"
    CachedEmbedder(path, embed_documents_fn=fn, sleep=lambda _s: None).embed_documents(["alpha"])
    again = CachedEmbedder(path, embed_documents_fn=fn, sleep=lambda _s: None)

    assert again.embed_documents(["alpha"])[0] == pytest.approx(fake_vector("alpha"), abs=1e-6)
    assert calls == [["alpha"]]  # the second instance read it from disk
    assert again.cache_size() == 1


def test_queries_are_cached_separately_from_documents(fake_embedder):
    fake_embedder.embed_documents(["alpha"])
    fake_embedder.embed_query("alpha")
    fake_embedder.embed_query("alpha")

    assert fake_embedder.calls["queries"] == 1  # second query came from the cache
    assert fake_embedder.cache_size() == 2  # one document entry + one query entry


def test_large_requests_are_sent_in_batches(fake_embedder):
    texts = [f"text number {n}" for n in range(BATCH_SIZE + 5)]

    vectors = fake_embedder.embed_documents(texts)

    assert fake_embedder.calls["documents"] == 2
    assert len(vectors) == len(texts)


def test_rate_limit_is_retried_after_waiting(tmp_path):
    attempts = {"n": 0}
    waits = []

    def flaky(texts):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: slow down")
        return [fake_vector(t) for t in texts]

    embedder = CachedEmbedder(tmp_path / "c.sqlite", embed_documents_fn=flaky, sleep=waits.append)

    assert len(embedder.embed_documents(["alpha"])[0]) > 0
    assert attempts["n"] == 2
    assert waits == [RETRY_WAIT_SECONDS]


def test_daily_quota_fails_fast_and_keeps_progress(tmp_path):
    state = {"n": 0}

    def quota_after_first_batch(texts):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("429 RESOURCE_EXHAUSTED ... EmbedContentRequestsPerDayPerProjectPerModel")
        return [fake_vector(t) for t in texts]

    embedder = CachedEmbedder(
        tmp_path / "c.sqlite", embed_documents_fn=quota_after_first_batch, sleep=lambda _s: None
    )
    texts = [f"text number {n}" for n in range(BATCH_SIZE + 5)]

    with pytest.raises(EmbeddingQuotaExhausted):
        embedder.embed_documents(texts)

    assert state["n"] == 2  # no retry loop on a daily cap
    assert embedder.cache_size() == BATCH_SIZE  # the first batch survived for next time


def test_non_quota_errors_propagate(tmp_path):
    def broken(texts):
        raise RuntimeError("API key not valid")

    embedder = CachedEmbedder(tmp_path / "c.sqlite", embed_documents_fn=broken, sleep=lambda _s: None)

    with pytest.raises(RuntimeError, match="API key not valid"):
        embedder.embed_documents(["alpha"])


def test_empty_vectors_are_not_cached(tmp_path):
    embedder = CachedEmbedder(
        tmp_path / "c.sqlite",
        embed_documents_fn=lambda texts: [[] for _ in texts],  # a silently failed API call
        sleep=lambda _s: None,
    )

    assert embedder.embed_documents(["alpha"]) == [[]]
    assert embedder.cache_size() == 0


# ---- a stalled embedding call must fail, not hang forever ------------------------------------


def test_a_stalled_call_times_out_instead_of_hanging(tmp_path, monkeypatch):
    import threading
    import time

    from app.embeddings import EmbeddingTimeout

    monkeypatch.setattr("app.embeddings.config.EMBEDDING_TIMEOUT", 0.2)
    release = threading.Event()
    calls = []

    def stalls(texts):
        calls.append(1)
        release.wait(5)  # never answers within the limit
        return [fake_vector(t) for t in texts]

    embedder = CachedEmbedder(tmp_path / "c.sqlite", embed_documents_fn=stalls, sleep=lambda _s: None)
    started = time.time()

    with pytest.raises(EmbeddingTimeout, match="didn't answer within 0.2 seconds"):
        embedder.embed_documents(["alpha"])

    release.set()
    assert time.time() - started < 2  # bounded: ~2 attempts x 0.2s, not 5s+
    assert len(calls) == 2  # one retry for a transient stall, then a clear failure
    assert embedder.cache_size() == 0


def test_a_single_stall_is_retried_and_succeeds(tmp_path, monkeypatch):
    import threading

    monkeypatch.setattr("app.embeddings.config.EMBEDDING_TIMEOUT", 0.2)
    release = threading.Event()
    attempts = {"n": 0}

    def stalls_once(texts):
        attempts["n"] += 1
        if attempts["n"] == 1:
            release.wait(5)
        return [fake_vector(t) for t in texts]

    embedder = CachedEmbedder(tmp_path / "c.sqlite", embed_documents_fn=stalls_once, sleep=lambda _s: None)

    assert embedder.embed_documents(["alpha"])[0] == pytest.approx(fake_vector("alpha"), abs=1e-6)
    release.set()
    assert attempts["n"] == 2
