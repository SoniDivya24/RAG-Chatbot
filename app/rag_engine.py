from typing import Any

from app.embeddings import CachedEmbedder
from app.profiles import Profile, StandardProfile
from app.vector_store import LocalVectorStore


class RagEngine:
    """Owns the full "document -> chunks -> embeddings -> vector store ->
    retrieval" pipeline for one mode. Every uploaded document is added to that
    mode's persistent store, so retrieval always searches across the mode's
    full library, not just one document.

    The document-specific parts (how a file is read and chunked, the relevance
    floor, how hits become context and sources) come from the `profile`; the
    engine itself is generic.
    """

    def __init__(
        self,
        profile: Profile | None = None,
        store: LocalVectorStore | None = None,
        embedder: CachedEmbedder | None = None,
    ) -> None:
        self.profile = profile or StandardProfile()
        # Both are injectable so tests can use a throwaway data folder and a
        # fake embedder; the app uses the defaults (local `data/` + Gemini).
        self.store = store or LocalVectorStore()
        self.embedder = embedder or CachedEmbedder()
        self.last_filter_notes: list[str] = []

    # -- helpers kept for callers that work with plain text -----------

    def chunk_text(self, text: str) -> list[str]:
        return [chunk.text for chunk in self.profile.chunk(text)]

    def embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        vectors = self.embedder.embed_documents(chunks)
        self._assert_valid_embeddings(vectors)
        return vectors

    def embed_query(self, question: str) -> list[float]:
        vector = self.embedder.embed_query(question)
        self._assert_valid_embeddings([vector])
        return vector

    # -- loading ------------------------------------------------------

    def load_file(self, content: bytes, filename: str) -> dict:
        """Read an uploaded file with this mode's profile, then index it."""
        extracted = self.profile.extract(content, filename)
        content_hash = self.profile.fingerprint(content, extracted)
        return self._index(extracted, filename, content_hash)

    def load_document(self, text: str, source_name: str) -> dict:
        """Index already-extracted text (the Standard pipeline's input)."""
        content_hash = self.profile.fingerprint(text.encode("utf-8"), text)
        return self._index(text, source_name, content_hash)

    def _index(self, extracted: Any, source_name: str, content_hash: str) -> dict:
        """Chunk, embed, and persist a new document alongside any already
        stored - unless a document with identical content already exists, in
        which case skip re-indexing entirely (no wasted embedding calls or
        duplicate storage) and return the existing one instead.
        """
        existing = self.store.find_by_content_hash(content_hash)
        if existing is not None:
            return {
                "id": existing["id"],
                "source_name": existing["source_name"],
                "chunk_count": existing["chunk_count"],
                "duplicate": True,
            }

        chunks = self.profile.chunk(extracted)
        vectors = self.embed_chunks([c.embed_text or c.text for c in chunks])
        doc = self.store.add_document(
            source_name,
            [c.text for c in chunks],
            vectors,
            content_hash,
            chunk_metadatas=[c.metadata for c in chunks],
            sidecars=self.profile.sidecars(extracted),
        )
        return {
            "id": doc["id"],
            "source_name": source_name,
            "chunk_count": len(chunks),
            "duplicate": False,
        }

    # -- retrieval ----------------------------------------------------

    def retrieve(self, question: str, k: int | None = None, where: dict | None = None) -> list[dict]:
        """Embed the question and return the top-k most relevant chunks across
        all documents, filtered to ones actually relevant enough to matter.

        The mode may narrow the search with a metadata filter (e.g. a region the question names).
        A wrong filter would hide the answer, so if it leaves nothing relevant the search is
        retried unfiltered. `last_filter_notes` says what was applied (for evaluation)."""
        query_vector = self.embed_query(question)
        notes: list[str] = []
        if where is None:
            where, notes = self.profile.query_filter(question, self.store)
        top_k = k or self.profile.retrieval_k
        results = [
            r
            for r in self.store.similarity_search(query_vector, top_k, where)
            if r["score"] >= self.profile.min_score
        ]
        if where and not results:
            notes = [*notes, "filter matched nothing relevant: retried unfiltered"]
            results = [
                r
                for r in self.store.similarity_search(query_vector, top_k)
                if r["score"] >= self.profile.min_score
            ]
        self.last_filter_notes = notes
        return results

    def has_documents(self) -> bool:
        return self.count_chunks() > 0

    def list_documents(self) -> list[dict]:
        return self.store.list_documents()

    def delete_document(self, document_id: str) -> None:
        self.store.delete_document(document_id)

    def count_chunks(self) -> int:
        return self.store.count_chunks()

    @staticmethod
    def _assert_valid_embeddings(vectors: list[list[float]]) -> None:
        # langchain-google-genai can swallow embedding API errors (invalid key,
        # quota, bad model name) and resolve with empty vectors instead of
        # raising - fail loudly here rather than let that turn into silent,
        # meaningless similarity scores downstream (the embedder leaves such
        # vectors empty rather than caching them).
        if any(not v for v in vectors):
            raise RuntimeError(
                "Embedding request failed (returned empty vectors). Check that "
                "GOOGLE_API_KEY is valid and EMBEDDING_MODEL is correct for your "
                "key, then try again."
            )
