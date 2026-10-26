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

## Phase 7 - Deployment (Render) - **superseded 2026-10-26** (see Part 2; the app is going local-only)
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

## Part 2 - Local-only, multi-mode RAG (direction change, 2026-10-26)

Phases 0-8 above built and shipped the original app (Supabase + Render). The user then clarified
that three extra document scenarios (a plain-text report, a long structured report, a visual
report full of tables/charts/footnotes) were meant to be built **in this app**, which should also
become **local-only**. The sibling repos `../RAG-GPO-Annual-Report`, `../RAG-World-Bank-Economic-Report`
and `../RAG-iMac-Environmental-Report` hold working prototypes of the three techniques (about
2,200 lines) - **port from them, read-only; the user manages those repos**. Phase 7 (Render) is
superseded and is retired in Phase 9.

**Product shape (agreed with the user):** one app with a **mode switch** - a segmented control in the
UI to flip between the **normal RAG** and the **three scenario RAGs** in one component. Working labels:
**Standard** (today's behaviour), **Report** (plain-text report), **Long document** (hierarchical,
section-aware), **Visual document** (tables, charts, footnotes). Each mode has its **own library and
index** and its own ingestion + retrieval pipeline; uploads go to the selected mode; chat queries that
mode's library only; history is kept per mode. Modes are chosen explicitly (no auto-detection for now).

**Stack for Part 2:** Chroma on local disk under `data/` (gitignored) replaces Supabase; the Render
config goes; Gemini stays for chat, embeddings and chart vision, with an **on-disk embedding cache** so
the same text is never embedded twice (the free tier caps embeddings at ~1000/day). The three reference
PDFs are **built-in samples, gitignored** (`samples/`), loadable with one click per mode.

### Phase 9 - Local-only foundation
- **Goal:** the existing app runs entirely locally, nothing else changes for the user.
- **Build:** a local vector store (Chroma + a small document registry) behind the same interface the
  engine uses today; keep list / delete / duplicate detection by content hash; add the embedding disk
  cache; remove `render.yaml`, `supabase/`, `app/supabase_client.py`, the Supabase MCP config and
  dependencies, and the Supabase/Render docs; update tests and `setup.md`. Existing cloud data and the
  Render service are **not** touched by this work - shutting them down is the user's call.
- **Done when:** upload / chat / list / delete / dedup work against the local store, tests pass, and the
  app starts with only `GOOGLE_API_KEY` set.
- **Needed from you:** nothing; later, whether to decommission the Supabase project and Render service.

### Phase 10 - Pluggable pipeline & mode plumbing (backend)
- **Goal:** a mode is a pluggable profile: how a document is extracted/chunked/indexed and how context
  is assembled; Standard is the first profile.
- **Build:** a `Profile` interface (extract -> chunks with metadata -> index -> retrieve -> assemble
  context), one Chroma collection and registry per mode, a rich chunk record (page, section/heading
  path, element kind, parent id), `mode` accepted by `/api/upload`, `/api/documents`, `/api/chat`,
  `/api/status`, sources returned with that metadata. Standard behaves exactly as before.
- **Needed from you:** nothing.

### Phase 11 - Mode switch in the UI
- **Goal:** the segmented control that moves between Standard and the three scenario modes.
- **Build:** the control in the masthead (see [frontend.md](frontend.md)), per-mode document list /
  upload target / chat history / empty state, example-question chips per mode, a Sources panel that
  shows page, section and element type. Verified in headless Chromium.
- **Needed from you:** a look/feel review; final labels for the four segments.

### Phase 12 - Report mode (port of the GPO prototype)
- **Build:** per-page extraction with running-head stripping, page-tagged chunks, relevance floor,
  page-cited grounded prompt with exact refusal. Eval: 3 core + extended + refusal questions.
- **As built:** the prototype hard-coded GPO's header patterns; the port detects page furniture generically
  (a line repeating in the head/foot zone of >=10% of pages, number-insensitive) and reproduces the prototype's
  cleaning *exactly* on the GPO report (70/70 pages, 263/263 chunks identical), so the prototype's embeddings
  were imported (`scripts/import_cache.py`) and indexing the sample costs no embedding calls. New per-profile
  settings: temperature, refusal wording, drop-sources-on-refusal. Upload cap raised 4 -> 25 MB (the reference
  PDFs are 4-7 MB). The 15-question set lives in `eval/questions/report.json`; `eval/run_eval.py --mode report`
  writes `docs/results/report.md`.

### Phase 13 - Visual document mode (port of the iMac prototype)
- **Build:** PyMuPDF geometry for tables (rebuilt under header bars), footnote markers linked to
  endnotes, call-out grouping, chart description via Gemini vision (cached), element-typed chunks.
  Eval: the 21-question set, reported per content type.
- **As built:** the prototype's constants (24pt titles, 11pt headings, a 735pt footer, endnotes on pp11-12,
  "the chart is on p2") are derived per document instead (`layout.py`), as ratios of the body text size, so
  uploads of other PDFs scale rather than lose text; charts are found by their coloured stacked bars (table
  stripes are grey), so the prototype's page-2 special case is gone. On the iMac report the derived layout equals
  the old constants and the chunks equal the prototype's. The chart prompt is generic (the prototype's was
  specific to its waterfall chart) and still scores 2/2 on the chart questions. `eval/run_eval.py` gained a
  per-content-type table and `--label`, so one document can be run through two modes
  (`docs/results/standard-on-imac.md` vs `visual.md`).

### Phase 14 - Long document mode (port of the World Bank prototype)  *(done - see progress.md)*
- **Build:** font-based structure -> section hierarchy, parent/child chunks, region/chapter filters
  (derived from the document's own headings rather than a hard-coded list), context assembly with a
  token budget, table-aware chunks. Eval: 3 core + extended + refusals. Needs the ~1,000-embedding
  index: reuse the prototype's embedding cache, and expect to spread any remainder over the daily cap.
- **As built:** the prototype's structure recovery and query vocabulary are tuned to the reference report (fonts,
  chapters, regions, country aliases), so they ship as a *preset* chosen when the document identifies itself as that
  report; any other long PDF gets a generic font-size outline (headings by type scale, chapters from "Chapter N"
  headings, page sections if there are none). Everything else - section-bounded chunks, parent sidecars, context
  assembly, filters with an unfiltered fallback, the canned bad-chapter reply - is generic. The prototype had never
  run live: the first live run exposed a mid-table column-header problem (fixed by spelling out the rows under it) and
  two evaluation bugs of my own (a judge that matched characters; retrieval metrics that skipped the filter).

### Phase 15 - Samples & evaluation
- **Build:** `samples/` (gitignored PDFs) with a "Load sample" action per mode and pre-wired example
  questions; the prototypes' eval sets as `eval/` regression tests with a results table per mode.

### Phase 16 - Docs & demo video
- **Build:** README refresh (modes, local setup, how to load samples), `docs/` brought up to date, and a
  revised `demo-video/script.md` showing Standard plus the three scenarios (review with the user before
  recording). Submission: repo URL + the video; no hosting.

**Order and risk:** 9 and 10 are prerequisites; then 12 (simplest) -> 13 -> 14 (largest, quota-bound).
Phase 11 can start as soon as 10 exposes `mode`. Each phase is verified live before being marked Done.

Current phase-by-phase status lives in [progress.md](progress.md). Decision/reasoning
history lives in `.claude/status-log.md` (local only, gitignored). This file stays
focused on the plan itself.
