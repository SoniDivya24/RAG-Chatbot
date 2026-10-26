"""Test isolation: point the app's data folder at a throwaway directory
*before* `app.config` is imported, so no test (offline or live) ever touches
the real library under `data/`.
"""

import os
import tempfile
from pathlib import Path

import pytest

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="rag-chatbot-tests-")
os.environ["DATA_DIR"] = _TEST_DATA_DIR

# app.main requires GOOGLE_API_KEY at import. Load .env.local first so a real
# key (needed by the live smoke tests) wins; only if there is none, use a dummy
# so the offline tests can still import the app. Offline tests never call Gemini.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
os.environ.setdefault("GOOGLE_API_KEY", "offline-test-key")

from tests.fakes import fake_vector  # noqa: E402  (after DATA_DIR is set)


@pytest.fixture
def fake_embedder(tmp_path):
    """A CachedEmbedder wired to the fake vectors, with a counter of API-style
    calls so tests can assert what hit the (fake) network."""
    from app.embeddings import CachedEmbedder

    calls = {"documents": 0, "texts": 0, "queries": 0}

    def embed_documents(texts):
        calls["documents"] += 1
        calls["texts"] += len(texts)
        return [fake_vector(t) for t in texts]

    def embed_query(text):
        calls["queries"] += 1
        return fake_vector(text)

    embedder = CachedEmbedder(
        cache_path=tmp_path / "cache.sqlite",
        embed_documents_fn=embed_documents,
        embed_query_fn=embed_query,
        sleep=lambda _s: None,
    )
    embedder.calls = calls
    return embedder
