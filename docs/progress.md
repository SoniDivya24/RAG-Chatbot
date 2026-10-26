# Progress

Tracks the current status of each phase from [phases.md](phases.md). This is the file
to check (and update) to know exactly where development left off and what to pick up
next - update it the moment a phase starts or finishes, don't batch it for later.

| Phase | Status | Notes |
|---|---|---|
| 0 - Project Scaffolding | Done | Skeleton created: app/, static/, supabase/schema.sql, requirements.txt, .env.local, render.yaml |
| 1 - Backend Core & Gemini Connectivity | Done | `app/config.py`, `app/main.py` (`/api/status`), Gemini smoke test all verified live |
| 2 - Document Ingestion Pipeline | Done | `text_extract.py` (.txt/.md/.pdf) + `rag_engine.py` (chunk/embed) verified live, 3072-dim confirmed |
| 3 - Vector Store & Persistence (Supabase) | Done | Schema applied via Supabase MCP, RLS+search_path hardened, load/retrieve/delete verified live |
| 4 - Chat Endpoint & RAG Wiring | Done | All routes wired + verified live (upload/chat/documents/delete), grounding confirmed, 14 tests pass |
| 5 - Frontend | Done | Two-panel UI + expandable sources, verified in a real headless-Chromium browser session |
| 6 - Local End-to-End Verification | Done | Full pass via headless browser; found + fixed a mobile CSS bug. Open: user's own look/feel review, whenever convenient |
| 7 - Deployment (Render) | Done | Live at https://rag-chatbot-4p6g.onrender.com, tracking `main` (switched from `dev`). Verified (status/upload/chat/grounding/delete) |
| 8 - Creative Extensions | Superseded | Replaced by Part 2 below |
| 9 - Local-only foundation | Done | `app/vector_store.py` (Chroma cosine + JSON registry in `data/`), `app/embeddings.py` (SQLite cache, paced batches, retries, fails fast on the daily quota), engine/config/main updated; `render.yaml`, `supabase/`, `app/supabase_client.py` and the `supabase` dependency removed. 37 tests pass (26 offline + live Gemini; tests use a throwaway data folder). Verified on a real server: upload, grounded chat, **restart keeps the library**, duplicate skipped, delete. The cloud Supabase project and Render service were not touched - retiring them is the user's call |
| 10 - Pluggable pipeline & mode plumbing | Done | `app/profiles/` (`Profile` interface: extract / chunk / fingerprint / format_context / source_payload; Standard = the original behaviour; Report / Long document / Visual document registered as **unavailable** placeholders until Phases 12-14), `app/modes.py` (one engine + store + chat session per mode under `data/modes/<mode>/`, shared embedding cache), chunk metadata + `where` filter in the store, every route takes `mode` (default Standard; unknown -> 400, unavailable -> 501), `GET /api/modes`, sources carry page/section/kind when known. 56 tests pass (offline + live). Verified on a real server; the existing UI (sends no mode) works unchanged |
| 11 - Mode switch in the UI | Done | Built 2026-10-26: mode bar with the segmented control (from `/api/modes`), per-mode library/upload/history/empty state/help, example-question chips, mode tag on answers, page/section/kind tags in Sources, URL-hash + keyboard support, mobile scroll. Verified in a real headless Chromium against a live server (37 checks, 3 consecutive clean runs): switching, disabled modes, per-mode library/history isolation, mode tags, source tags, hash/keyboard, legacy-thread migration, no console errors, mobile 2x2 layout with no overflow. Backend suite: 57 tests pass. Not yet exercisable end to end: switching *into* a scenario mode (they're unavailable until Phases 12-14), so those paths were checked with network mocks |
| 12 - Report mode (GPO port) | Not started | **Next.** Port `../RAG-GPO-Annual-Report` as the Report profile |
| 13 - Visual document mode (iMac port) | Not started | |
| 14 - Long document mode (World Bank port) | Not started | |
| 15 - Samples & evaluation | Not started | `samples/` gitignored PDFs; eval sets as regression tests |
| 16 - Docs & demo video | Not started | Revised video script to review before recording |

**Direction change (2026-10-26):** the app is becoming **local-only** (no Supabase, no Render) and gains
a **mode switch** between the normal RAG and three scenario RAGs (plain-text report, long structured
document, visual document). Details and rationale: Part 2 of [phases.md](phases.md). Phase 7's deployed
Render app still exists until the user retires it.

**Post-MVP polish (post-Phase 7, ongoing as needed):** full UI redesign (themeable
accent colors, popover theme switcher, blue-grey masthead, floating toast errors,
multiline composer), document dedup by content hash, relevance-score filtering on
retrieved chunks (`MIN_RELEVANCE_SCORE`), password-protected PDF handling, and a
grounding fix for off-topic questions (documents present but nothing relevant
retrieved could fall back to the model's general knowledge instead of declining -
fixed in `app/chat_session.py` by giving the model an explicit small-talk-vs-real-
question branch instead of a single blanket instruction).

**Status values:** `Not started` / `In progress` / `Blocked (<reason>)` / `Done`.

**Resuming in a new session:** read this table first - the first non-`Done` phase,
top to bottom, is where to pick up. Cross-check any `Blocked` note against
[phases.md](phases.md) for what's needed to unblock it.
