# Setup

## Setup Checklist (things we need from you / to configure)

- [ ] **Gemini API key** - from https://aistudio.google.com/app/apikey → `GOOGLE_API_KEY`
- [ ] **.env.local** - created locally (see Environment Variables below), gitignored,
  holds the key - there is no committed `.env.example` template; this list is the
  reference for what to put in it
- [ ] **.gitignore** - `.venv/`, `__pycache__/`, `.env.local`, `.env`, `data/`, `samples/`
- [ ] **requirements.txt** - dependencies from [stack.md](stack.md)
- [ ] **.claude/** - project-level Claude Code config (added as needed; not blocking)

No database, no Supabase project, no hosting account: everything the app stores lives in `data/`.

## Environment Variables

```
# Required
GOOGLE_API_KEY=

# Optional (defaults shown)
CHAT_MODEL=gemini-3.1-flash-lite
EMBEDDING_MODEL=models/gemini-embedding-001
PORT=8000
DATA_DIR=            # defaults to ./data (modes/<mode>/ stores + embedding_cache.sqlite + vision_cache/)
LLM_TIMEOUT=90        # seconds before a chat call is abandoned
VISION_TIMEOUT=150    # chart-description (image) calls
EMBEDDING_TIMEOUT=60  # embedding calls (enforced by the app; the library's own option is a no-op)
```

## Part 2 changes (local-only, 2026-10-26 - Phase 9)

- **Removed:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, the Supabase project/schema step, the Render
  account/deploy step, and the Supabase MCP (`.mcp.json`, `SUPABASE_ACCESS_TOKEN`). Nothing is deployed.
- **Added:** `data/` (gitignored: Chroma index, parent stores, embedding cache, vision cache) and
  `samples/` (gitignored: the three reference PDFs - copy them in from
  `~/Desktop/ProjectData/RAG-Projects/GPO Annual Report/drive-download-20261022T103331Z-1-001/`).
- **Still required:** `GOOGLE_API_KEY` (and optionally `CHAT_MODEL`, `EMBEDDING_MODEL`).
- **Install quirk:** `pip install pymupdf` may attempt a source build and fail with an SSL error; use
  `--only-binary=:all:`. Import it as `pymupdf`.
- **Free-tier limit:** ~1000 Gemini embedding requests/day; the embedding cache avoids repeats.
