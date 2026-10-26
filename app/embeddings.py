import hashlib
import sqlite3
import threading
import time
from array import array
from pathlib import Path
from typing import Callable

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app import config

# Gemini's free tier allows roughly 100 embedding requests per minute (one per
# text) and about 1000 per day. Texts are embedded in small paced batches and
# every vector is cached on disk, so a text is never embedded twice - which is
# what lets a failed upload resume for free and keeps re-indexing cheap.
BATCH_SIZE = 40
PACE_SECONDS = 60 * BATCH_SIZE / 90
RETRY_WAIT_SECONDS = 30
MAX_TRIES = 6

QUERY_PREFIX = "query:"


class EmbeddingQuotaExhausted(RuntimeError):
    """The daily embedding quota is used up; retrying today can't help."""


class CachedEmbedder:
    """Gemini embeddings behind a SQLite cache of float32 vectors.

    The cache key is sha256("<model>\\n<text>") - the same scheme the prototype
    repos used - so their cached vectors stay compatible. Queries are cached
    too, under a prefix, since they are embedded with a different task type.
    """

    def __init__(
        self,
        cache_path: Path | None = None,
        embed_documents_fn: Callable[[list[str]], list[list[float]]] | None = None,
        embed_query_fn: Callable[[str], list[float]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache_path = Path(cache_path or config.DATA_DIR / "embedding_cache.sqlite")
        self._embed_documents_fn = embed_documents_fn
        self._embed_query_fn = embed_query_fn
        self._sleep = sleep
        self._client: GoogleGenerativeAIEmbeddings | None = None
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None

    # -- cache ---------------------------------------------------------

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self.cache_path, check_same_thread=False)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, vector BLOB NOT NULL)"
            )
            self._db.commit()
        return self._db

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(f"{config.EMBEDDING_MODEL}\n{text}".encode()).hexdigest()

    def _get_many(self, keys: list[str]) -> dict[str, list[float]]:
        found: dict[str, list[float]] = {}
        with self._lock:
            for i in range(0, len(keys), 500):
                chunk = keys[i : i + 500]
                marks = ",".join("?" * len(chunk))
                for key, blob in self.db.execute(
                    f"SELECT key, vector FROM embeddings WHERE key IN ({marks})", chunk
                ):
                    vec = array("f")
                    vec.frombytes(blob)
                    found[key] = vec.tolist()
        return found

    def _put_many(self, items: dict[str, list[float]]) -> None:
        with self._lock:
            self.db.executemany(
                "INSERT OR REPLACE INTO embeddings (key, vector) VALUES (?, ?)",
                [(k, array("f", v).tobytes()) for k, v in items.items()],
            )
            self.db.commit()

    def cache_size(self) -> int:
        with self._lock:
            return self.db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    # -- Gemini --------------------------------------------------------

    @property
    def client(self) -> GoogleGenerativeAIEmbeddings:
        # Lazy so importing the app (and cache-only paths) don't need a key.
        if self._client is None:
            config.require("GOOGLE_API_KEY")
            self._client = GoogleGenerativeAIEmbeddings(model=config.EMBEDDING_MODEL)
        return self._client

    def _call_documents(self, texts: list[str]) -> list[list[float]]:
        if self._embed_documents_fn is not None:
            return self._embed_documents_fn(texts)
        return self.client.embed_documents(texts)

    def _call_query(self, text: str) -> list[float]:
        if self._embed_query_fn is not None:
            return self._embed_query_fn(text)
        return self.client.embed_query(text)

    def _with_retry(self, fn, *args):
        for attempt in range(MAX_TRIES):
            try:
                return fn(*args)
            except Exception as exc:
                msg = str(exc)
                if "PerDay" in msg:
                    raise EmbeddingQuotaExhausted(
                        "Gemini's daily embedding quota is used up. Already-embedded text is "
                        "cached, so retry after the quota resets and only the remainder is sent."
                    ) from exc
                rate_limited = "RESOURCE_EXHAUSTED" in msg or "429" in msg
                if not rate_limited or attempt == MAX_TRIES - 1:
                    raise
                self._sleep(RETRY_WAIT_SECONDS)

    # -- public API ----------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        keys = [self._key(t) for t in texts]
        cached = self._get_many(list(dict.fromkeys(keys)))
        todo = list(dict.fromkeys(t for t, k in zip(texts, keys) if k not in cached))

        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i : i + BATCH_SIZE]
            vectors = self._with_retry(self._call_documents, batch)
            fresh = {self._key(t): v for t, v in zip(batch, vectors) if v}
            if fresh:
                self._put_many(fresh)
                cached.update(fresh)
            if i + BATCH_SIZE < len(todo):
                self._sleep(PACE_SECONDS)

        # A missing/empty vector means the API call silently failed (langchain
        # can swallow embedding errors); surface it as empty so the caller's
        # validation fails loudly instead of storing meaningless vectors.
        return [cached.get(k, []) for k in keys]

    def embed_query(self, text: str) -> list[float]:
        key = self._key(QUERY_PREFIX + text)
        hit = self._get_many([key])
        if key in hit:
            return hit[key]
        vector = self._with_retry(self._call_query, text)
        if vector:
            self._put_many({key: vector})
        return vector
