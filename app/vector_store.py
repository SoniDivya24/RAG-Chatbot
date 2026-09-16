from app.supabase_client import get_supabase

INSERT_BATCH_SIZE = 200  # keep individual PostgREST payloads small


class SupabaseVectorStore:
    """Persistent vector store backed by Supabase Postgres + pgvector. Chunks
    from every uploaded document are kept in one `chunks` table and searched
    together, so retrieval spans all documents ever uploaded, not just the
    most recent one.
    """

    def find_by_content_hash(self, content_hash: str) -> dict | None:
        supabase = get_supabase()
        res = (
            supabase.table("documents")
            .select("id, source_name, chunk_count, created_at")
            .eq("content_hash", content_hash)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def add_document(
        self,
        source_name: str,
        chunk_texts: list[str],
        embedding_vectors: list[list[float]],
        content_hash: str,
    ) -> dict:
        supabase = get_supabase()
        doc_res = (
            supabase.table("documents")
            .insert(
                {
                    "source_name": source_name,
                    "chunk_count": len(chunk_texts),
                    "content_hash": content_hash,
                }
            )
            .execute()
        )
        doc = doc_res.data[0]

        rows = [
            {
                "document_id": doc["id"],
                "chunk_index": i,
                "content": content,
                "embedding": embedding_vectors[i],
            }
            for i, content in enumerate(chunk_texts)
        ]

        for i in range(0, len(rows), INSERT_BATCH_SIZE):
            batch = rows[i : i + INSERT_BATCH_SIZE]
            try:
                supabase.table("chunks").insert(batch).execute()
            except Exception as exc:
                # Roll back the partial insert so a failed upload doesn't leave
                # an orphaned documents row with no (or partial) chunks.
                supabase.table("documents").delete().eq("id", doc["id"]).execute()
                raise RuntimeError(f"Failed to save chunks: {exc}") from exc

        return doc

    def list_documents(self) -> list[dict]:
        supabase = get_supabase()
        res = (
            supabase.table("documents")
            .select("id, source_name, chunk_count, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return res.data

    def delete_document(self, document_id: str) -> None:
        supabase = get_supabase()
        supabase.table("documents").delete().eq("id", document_id).execute()

    def count_chunks(self) -> int:
        supabase = get_supabase()
        res = supabase.table("chunks").select("id", count="exact").execute()
        return res.count or 0

    def similarity_search(self, query_embedding: list[float], k: int = 5) -> list[dict]:
        supabase = get_supabase()
        res = supabase.rpc(
            "match_chunks", {"query_embedding": query_embedding, "match_count": k}
        ).execute()
        return [
            {
                "text": row["content"],
                "score": row["similarity"],
                "metadata": {
                    "source": row["source_name"],
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                },
            }
            for row in res.data
        ]
