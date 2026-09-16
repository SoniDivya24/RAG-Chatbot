# RAG-Chatbot

A Retrieval-Augmented Generation (RAG) chatbot: upload documents, ask questions, get
answers grounded in what was actually uploaded — with sources shown for every answer.

**Live demo:** https://rag-chatbot-4p6g.onrender.com
(free tier — spins down after 15 min idle, first request after that takes ~1 min to wake up)

**Status:** see [docs/progress.md](docs/progress.md) for current phase-by-phase status.

## Stack

Python + FastAPI, LangChain + Google Gemini (chat + embeddings), Supabase
(Postgres + pgvector) as the vector store, vanilla HTML/CSS/JS frontend, deployed on
Render.

See [docs/](docs/) for full planning detail (stack, architecture, setup, frontend,
phases, backlog).

## What's working

- **Full backend API works end-to-end.** `app/main.py` exposes:
  - `GET /api/status` — health + live document/chunk counts
  - `POST /api/upload` — multi-file upload (`.txt`/`.md`/`.pdf`), per-file validation
    and error reporting
  - `GET /api/documents` / `DELETE /api/documents/{id}` — list/remove uploaded docs
  - `POST /api/chat` — grounded Q&A with conversation history, returns
    `{ reply, sources: [{ text, score, source }] }`
  - Rate limited (`slowapi`: 10/min upload, 20/min chat), consistent `{"error": ...}`
    JSON error responses, serves `static/` at `/`.
  - Verified live: uploads index correctly, grounded answers cite real retrieved
    text, out-of-scope questions are correctly refused (not answered from general
    knowledge) even when retrieval still returns low-score chunks, conversation
    history/memory works across turns, validation and unsupported-file-type
    rejection both work, delete cascades cleanly.
- **Gemini connectivity confirmed.** `app/config.py` loads `.env.local` and validates
  required keys lazily (only what the current feature needs). `tests/test_gemini_smoke.py`
  makes a real call to `ChatGoogleGenerativeAI` and passes.
- **Document ingestion (extract + chunk + embed) confirmed.** `app/text_extract.py`
  pulls plain text out of `.txt`/`.md`/`.pdf` files; `app/rag_engine.py`'s `RagEngine`
  splits it (`RecursiveCharacterTextSplitter`, 800/150) and embeds it via
  `GoogleGenerativeAIEmbeddings` — verified live, 3072-dim vectors matching the
  Supabase schema.
- **Persistence + retrieval confirmed, live against Supabase.** `app/supabase_client.py`
  + `app/vector_store.py` (`SupabaseVectorStore`) store chunks in Postgres/pgvector and
  search them via the `match_chunks` RPC. `RagEngine.load_document`/`retrieve`/
  `delete_document` verified end-to-end: a real document was loaded, retrieved by
  similarity search, and deleted. RLS is enabled on both tables (no policies — the app
  only ever accesses them via the `service_role` key, which bypasses RLS).
- **Frontend works end-to-end, verified in a real browser.** Two-panel layout
  (`static/index.html`/`app.js`/`style.css`): sidebar for upload + document list +
  status, main panel for chat. Each assistant reply has an expandable **Sources**
  section showing the retrieved chunk's source filename, similarity score, and
  actual text — so the RAG grounding is visually verifiable, not just claimed.
  Chat history persists in `localStorage`. Verified with a headless-Chromium
  session: upload → shows in document list → chat reply → sources expand with
  real content — zero console errors.
- **End-to-end verification pass complete.** Multi-document upload, cross-document
  grounded retrieval, out-of-scope refusal, delete-via-UI, unsupported-file
  rejection, history persistence across reloads, and clear-conversation all
  verified via a real headless-browser session. A mobile-layout bug (document
  list collapsing to invisible on narrow viewports) was found and fixed.
- **Deployed and verified live on Render**: https://rag-chatbot-4p6g.onrender.com
  — status, upload, grounded chat, out-of-scope refusal, and delete all confirmed
  working against the actual deployed instance, not just locally.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Fill in .env.local with GOOGLE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
# — see docs/setup.md for the full list of variables. Also run supabase/schema.sql
# against your Supabase project (SQL Editor, or via the Supabase MCP server) first.

uvicorn app.main:app --reload --port 8000
# -> open http://localhost:8000 for the chat UI, or
# -> http://localhost:8000/api/status should return {"status": "ok", ...}
```

## Running tests

```bash
pytest
# 14 tests, most making real network calls (Gemini + Supabase) — needs GOOGLE_API_KEY,
# SUPABASE_URL, and SUPABASE_SERVICE_ROLE_KEY set, and the schema already applied.
```

This will keep getting filled in with real, verified instructions as each phase completes.
