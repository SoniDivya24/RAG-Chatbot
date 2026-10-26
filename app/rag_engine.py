import hashlib

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.embeddings import CachedEmbedder
from app.vector_store import LocalVectorStore

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
RETRIEVAL_K = 5

# Chunks scoring below this cosine similarity are treated as noise, not real
# matches: a vector search always returns the top-k closest chunks even when none of
# them are actually relevant (e.g. an off-topic question with documents
# uploaded), and those shouldn't be sent to the LLM as context or shown to the
# user as "sources" for an answer they didn't actually inform.
MIN_RELEVANCE_SCORE = 0.62


class RagEngine:
    """Owns the full "document -> chunks -> embeddings -> vector store ->
    retrieval" pipeline. Every uploaded document is added to the same
    persistent store, so retrieval always searches across the full library,
    not just one document.
    """

    def __init__(
        self,
        store: LocalVectorStore | None = None,
        embedder: CachedEmbedder | None = None,
    ) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        # Both are injectable so tests can use a throwaway data folder and a
        # fake embedder; the app uses the defaults (local `data/` + Gemini).
        self.store = store or LocalVectorStore()
        self.embedder = embedder or CachedEmbedder()

    def chunk_text(self, text: str) -> list[str]:
        chunks = self.splitter.split_text(text)
        if not chunks:
            raise ValueError("Document produced no usable text - is the file empty?")
        return chunks

    def embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        vectors = self.embedder.embed_documents(chunks)
        self._assert_valid_embeddings(vectors)
        return vectors

    def embed_query(self, question: str) -> list[float]:
        vector = self.embedder.embed_query(question)
        self._assert_valid_embeddings([vector])
        return vector

    def load_document(self, text: str, source_name: str) -> dict:
        """Chunk, embed, and persist a new document alongside any already
        stored - unless a document with identical content already exists, in
        which case skip re-indexing entirely (no wasted embedding calls or
        duplicate storage) and return the existing one instead.
        """
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing = self.store.find_by_content_hash(content_hash)
        if existing is not None:
            return {
                "id": existing["id"],
                "source_name": existing["source_name"],
                "chunk_count": existing["chunk_count"],
                "duplicate": True,
            }

        chunks = self.chunk_text(text)
        vectors = self.embed_chunks(chunks)
        doc = self.store.add_document(source_name, chunks, vectors, content_hash)
        return {
            "id": doc["id"],
            "source_name": source_name,
            "chunk_count": len(chunks),
            "duplicate": False,
        }

    def retrieve(self, question: str, k: int = RETRIEVAL_K) -> list[dict]:
        """Embed the question and return the top-k most relevant chunks across
        all documents, filtered to ones actually relevant enough to matter."""
        query_vector = self.embed_query(question)
        results = self.store.similarity_search(query_vector, k)
        return [r for r in results if r["score"] >= MIN_RELEVANCE_SCORE]

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
