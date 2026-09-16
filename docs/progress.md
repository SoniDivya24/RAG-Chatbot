# Progress

Tracks the current status of each phase from [phases.md](phases.md). This is the file
to check (and update) to know exactly where development left off and what to pick up
next — update it the moment a phase starts or finishes, don't batch it for later.

| Phase | Status | Notes |
|---|---|---|
| 0 — Project Scaffolding | Done | Skeleton created: app/, static/, supabase/schema.sql, requirements.txt, .env.local, render.yaml |
| 1 — Backend Core & Gemini Connectivity | Done | `app/config.py`, `app/main.py` (`/api/status`), Gemini smoke test all verified live |
| 2 — Document Ingestion Pipeline | Done | `text_extract.py` (.txt/.md/.pdf) + `rag_engine.py` (chunk/embed) verified live, 3072-dim confirmed |
| 3 — Vector Store & Persistence (Supabase) | Done | Schema applied via Supabase MCP, RLS+search_path hardened, load/retrieve/delete verified live |
| 4 — Chat Endpoint & RAG Wiring | Done | All routes wired + verified live (upload/chat/documents/delete), grounding confirmed, 14 tests pass |
| 5 — Frontend | Done | Two-panel UI + expandable sources, verified in a real headless-Chromium browser session |
| 6 — Local End-to-End Verification | Done | Full pass via headless browser; found + fixed a mobile CSS bug. Open: user's own look/feel review, whenever convenient |
| 7 — Deployment (Render) | Not started | Next up. Needs Render account + pushed repo |
| 8 — Creative Extensions | Not started | Optional, post-MVP |

**Status values:** `Not started` / `In progress` / `Blocked (<reason>)` / `Done`.

**Resuming in a new session:** read this table first — the first non-`Done` phase,
top to bottom, is where to pick up. Cross-check any `Blocked` note against
[phases.md](phases.md) for what's needed to unblock it.
