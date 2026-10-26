# Open Decisions & Backlog

## Open Decisions / To Revisit

- Whether Render's cold-start (~1 min after 15 min idle) is acceptable for demo purposes,
  or whether we need a keep-alive ping - revisit if it becomes a real issue.
- Streaming responses - notebook lists it as a "natural next step," not required for v1.

## Part 2 backlog (added 2026-10-26)

- **Embedding provider setting** - local sentence-transformers embeddings (no quota, offline) as an
  alternative to Gemini; needs re-embedding and a per-provider index. Do this if the daily cap keeps
  blocking, or so a fresh clone can build the samples without waiting.
- **Groq as an extra chat provider** (the user offered a key). Groq reliably serves chat models; its
  embeddings endpoint (`nomic-embed-text`) appears in third-party docs but was **not confirmed** from
  official pages - verify with the model list before relying on it. Not needed while Gemini works.
- **Auto-detect the mode** from an upload's shape (page count, heading depth, tables/images) instead of
  the explicit switch.
- **Compare view** (run a question through two modes side by side), as in the iMac prototype.
- **Reranker / hybrid search** per mode, only if measured to help (it hurt on table chunks).
- **Ship pre-built sample indexes** so a fresh clone needn't re-embed.

## Creative Extensions (backlog, after core pipeline works)

- Support more file types (`.docx`, `.csv`)
- Streaming token responses
- Simple auth (so uploaded documents aren't public to anyone with the URL)
- Highlight which part of a source snippet most closely matched the question
