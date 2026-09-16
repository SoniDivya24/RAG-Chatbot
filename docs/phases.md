# Development Phases

Each phase lists its goal, what gets built, and - critically - what input/clarification
is needed from you before it can start or finish. Phases are sequential but Phase 0-2
need nothing from you and can run immediately.

**Standing rules:**
- The moment a phase starts or finishes, update its status in [progress.md](progress.md)
  - that file (not this one) is what tells a new session where to pick up.
- After each phase is completed, also update `README.md` with what was built in that
  phase (setup steps, how to run it, what's working) - so the README stays an accurate,
  current account of the project rather than a stale one-liner.

## Phase 0 - Project Scaffolding
- **Goal:** repo skeleton in place, nothing functional yet.
- **Build:** folder structure from [architecture.md](architecture.md), `requirements.txt`,
  `.env.local` (gitignored, blank placeholders), `supabase/schema.sql` (written against
  the planned schema, not yet run anywhere), empty `static/` frontend shell, `render.yaml`
  skeleton.
- **Needed from you:** nothing - nothing here touches a real API or database.

## Phase 1 - Backend Core & Gemini Connectivity
- **Goal:** FastAPI app boots, config validation works, a basic Gemini chat call succeeds
  (mirrors Colab Sections 2-4: configure LLM, first call, basic chatbot).
- **Build:** `app/config.py`, `app/main.py` with a `/api/status` health route, a smoke
  test that calls `ChatGoogleGenerativeAI`.
- **Needed from you: `GOOGLE_API_KEY`** - this phase can't be verified end-to-end
  without it (code can still be written, just not run).

## Phase 2 - Document Ingestion Pipeline
- **Goal:** upload → extract → chunk → embed works, output verified locally (no
  persistence yet - can print/inspect in-memory).
- **Build:** `app/text_extract.py` (.txt/.md/.pdf via `pypdf`), chunking via
  `RecursiveCharacterTextSplitter` (chunk_size=800/overlap=150), embedding via
  `GoogleGenerativeAIEmbeddings`.
- **Needed from you:** same `GOOGLE_API_KEY` as Phase 1 (embeddings use the same key);
  a couple of sample documents (.txt/.md/.pdf) to test extraction against, if you have
  specific ones in mind - otherwise I'll use generic test files.

## Phase 3 - Vector Store & Persistence (Supabase)
- **Goal:** chunks + embeddings persist across restarts; similarity search works via
  `pgvector`.
- **Build:** `app/supabase_client.py`, `app/vector_store.py`, `app/rag_engine.py`
  (load/retrieve), running `supabase/schema.sql` against a real project.
- **Needed from you:** a **Supabase project** created, with `SUPABASE_URL` and
  `SUPABASE_SERVICE_ROLE_KEY` from Project Settings → API, and confirmation the
  `pgvector` extension is enabled (schema.sql also asserts this) so we can run the
  schema once and verify the `match_chunks` RPC.

## Phase 4 - Chat Endpoint & RAG Wiring
- **Goal:** full pipeline live - `/api/upload`, `/api/documents`, `/api/chat`,
  `/api/status` all working together, grounded answers with sources.
- **Build:** `app/chat_session.py` (history + retrieval + grounded prompt), route
  wiring in `app/main.py`, rate limiting (`slowapi`).
- **Needed from you:** nothing new - depends only on Phases 1-3 being done.

## Phase 5 - Frontend
- **Goal:** working UI per [frontend.md](frontend.md) (two-panel layout, expandable
  per-answer source snippets with score + chunk text).
- **Build:** `static/index.html`, `static/app.js`, `static/style.css`.
- **Needed from you:** nothing blocking; open to visual/UX feedback once there's
  something to look at.

## Phase 6 - Local End-to-End Verification
- **Goal:** confirm the whole system works as a user would experience it, before
  deploying anywhere.
- **Build:** nothing new - manual test pass (upload real docs, ask in-document and
  out-of-document questions, confirm grounding/"don't know" behavior, confirm source
  snippets match what was retrieved).
- **Needed from you:** a look/feel review - does the chat experience feel right, are
  there edge cases you want tested that I wouldn't think to try.

## Phase 7 - Deployment (Render)
- **Goal:** live, publicly reachable demo.
- **Build:** finalize `render.yaml`, connect the GitHub repo to a Render web service,
  set env vars in the Render dashboard.
- **Needed from you:** a **Render account**, and this repo pushed to a GitHub remote
  you control (Render deploys from a connected repo) - I'll need you to either share
  the repo URL/confirm it's pushed, or grant/complete the Render↔GitHub connection
  yourself since that's an account-level action.

## Phase 8 - Creative Extensions (optional, post-MVP)
- **Goal:** pick from [backlog.md](backlog.md) based on remaining time/interest, once
  the core system (Phases 0-7) is solid.
- **Needed from you:** which backlog item(s) to prioritize, if any.

Current phase-by-phase status lives in [progress.md](progress.md). Decision/reasoning
history lives in `.claude/status-log.md` (local only, gitignored). This file stays
focused on the plan itself.
