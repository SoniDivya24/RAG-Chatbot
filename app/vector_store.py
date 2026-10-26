import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from chromadb.config import Settings

from app import config

COLLECTION = "chunks"
ADD_BATCH_SIZE = 500


class LocalVectorStore:
    """Persistent, local vector store: Chroma (cosine) for the chunks plus a
    small JSON registry for the documents. Chunks from every uploaded
    document live in one collection and are searched together, so retrieval
    spans all documents, not just the most recent one.

    Everything sits under one folder (default `data/`, gitignored). There is
    no server and no cloud dependency; delete the folder to reset.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or config.DATA_DIR)
        self.path.mkdir(parents=True, exist_ok=True)
        self._registry_path = self.path / "documents.json"
        self._lock = threading.Lock()
        # Telemetry off: a local-only app shouldn't phone home.
        self._client = chromadb.PersistentClient(
            path=str(self.path / "index"), settings=Settings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            COLLECTION, configuration={"hnsw": {"space": "cosine"}}
        )

    # -- document registry --------------------------------------------

    def _read_registry(self) -> dict[str, dict]:
        if not self._registry_path.exists():
            return {}
        return json.loads(self._registry_path.read_text())

    def _write_registry(self, registry: dict[str, dict]) -> None:
        # Write-then-replace so a crash mid-write can't corrupt the registry.
        tmp = self._registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(registry, indent=2))
        os.replace(tmp, self._registry_path)

    def find_by_content_hash(self, content_hash: str) -> dict | None:
        with self._lock:
            for doc in self._read_registry().values():
                if doc["content_hash"] == content_hash:
                    return self._public(doc)
        return None

    def add_document(
        self,
        source_name: str,
        chunk_texts: list[str],
        embedding_vectors: list[list[float]],
        content_hash: str,
    ) -> dict:
        doc = {
            "id": str(uuid.uuid4()),
            "source_name": source_name,
            "chunk_count": len(chunk_texts),
            "content_hash": content_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            for i in range(0, len(chunk_texts), ADD_BATCH_SIZE):
                end = min(i + ADD_BATCH_SIZE, len(chunk_texts))
                self._collection.add(
                    ids=[f"{doc['id']}:{n}" for n in range(i, end)],
                    documents=chunk_texts[i:end],
                    embeddings=embedding_vectors[i:end],
                    metadatas=[
                        {
                            "document_id": doc["id"],
                            "chunk_index": n,
                            "source": source_name,
                        }
                        for n in range(i, end)
                    ],
                )
        except Exception as exc:
            # Roll back the partial insert so a failed upload doesn't leave
            # orphaned chunks with no registry entry.
            self._collection.delete(where={"document_id": doc["id"]})
            raise RuntimeError(f"Failed to save chunks: {exc}") from exc

        with self._lock:
            registry = self._read_registry()
            registry[doc["id"]] = doc
            self._write_registry(registry)
        return self._public(doc)

    def list_documents(self) -> list[dict]:
        with self._lock:
            docs = list(self._read_registry().values())
        docs.sort(key=lambda d: d["created_at"], reverse=True)
        return [self._public(d) for d in docs]

    def delete_document(self, document_id: str) -> None:
        self._collection.delete(where={"document_id": document_id})
        with self._lock:
            registry = self._read_registry()
            if registry.pop(document_id, None) is not None:
                self._write_registry(registry)

    def count_chunks(self) -> int:
        return self._collection.count()

    def similarity_search(self, query_embedding: list[float], k: int = 5) -> list[dict]:
        if self._collection.count() == 0:
            return []
        res = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, self._collection.count()),
        )
        return [
            {
                "text": text,
                "score": 1 - distance,  # cosine distance -> similarity
                "metadata": {
                    "source": meta["source"],
                    "document_id": meta["document_id"],
                    "chunk_index": meta["chunk_index"],
                },
            }
            for text, meta, distance in zip(
                res["documents"][0], res["metadatas"][0], res["distances"][0]
            )
        ]

    @staticmethod
    def _public(doc: dict) -> dict:
        """The shape callers see (no internal content hash)."""
        return {
            "id": doc["id"],
            "source_name": doc["source_name"],
            "chunk_count": doc["chunk_count"],
            "created_at": doc["created_at"],
        }
