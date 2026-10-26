# Architecture

## Folder Structure (current - local-only since Phase 9)

```
RAG-Chatbot/
├── .claude/                    # Claude Code project config (gitignored, local only)
│   ├── settings.json           # project-level permissions
│   ├── status-log.md           # local chronological decision/progress history
│   ├── commands/                # custom slash commands (e.g. /run-dev)
│   └── agents/                  # custom subagents (empty for now)
├── docs/                        # planning detail, split by concern
│   ├── stack.md
│   ├── architecture.md          # this file
│   ├── setup.md
│   ├── frontend.md
│   ├── phases.md
│   └── backlog.md
├── .env.local                  # real secrets, gitignored, never committed (no .env.example template)
├── .gitignore
├── CLAUDE.md                   # project overview, points to README.md
├── README.md                    # project overview + index into docs/
├── requirements.txt
├── app/
│   ├── main.py                 # FastAPI app: routes, static file mount, startup checks
│   ├── config.py               # env var loading + validation
│   ├── embeddings.py           # Gemini embeddings behind a SQLite cache (paced, retries, daily-quota aware)
│   ├── profiles/               # one Profile per mode: base.py (Chunk, Profile, UnavailableProfile), standard.py
│   ├── modes.py                # registry: profile + engine + chat session + store per mode (data/modes/<mode>/)
│   ├── text_extract.py         # .txt/.md/.pdf -> plain text
│   ├── vector_store.py         # local Chroma (cosine) + JSON document registry: CRUD + similarity search
│   ├── rag_engine.py           # chunk -> embed -> store -> retrieve pipeline
│   └── chat_session.py         # history + retrieval -> single Gemini call
├── static/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── data/                       # gitignored: modes/<mode>/{index/ (Chroma), documents.json}, embedding_cache.sqlite
└── samples/                    # gitignored: reference PDFs (Part 2)
```

## Core Pipeline (what we're building)

```
Upload (.txt/.md/.pdf)
  → extract_text()                              (app/text_extract.py)
  → RecursiveCharacterTextSplitter, chunk_size=800/overlap=150
  → CachedEmbedder.embed_documents()            (app/embeddings.py: disk cache, paced batches)
  → store in local Chroma collection (+ documents.json entry)   (app/vector_store.py)

User question
  → embeddings.embed_query()
  → Chroma similarity search (cosine; score = 1 - distance)
  → top-k relevant chunks + conversation history
  → grounded system prompt ("use CONTEXT, say you don't know if it's not there")
  → ChatGoogleGenerativeAI.invoke()
  → { reply, sources: [{ text, score, source }] }
```

Conversation history is stateless server-side (each `/api/chat` call receives the full
history from the client, stored in browser `localStorage`) - same reasoning as the
Colab notebook: no shared memory between requests without a session store, and we
don't need one for this scope.

---

## Target architecture - local-only, multi-mode (Part 2; the plumbing - profiles, per-mode libraries, `mode` in the API - landed in Phase 10)

```
                         mode switch (UI)  ->  mode = standard | report | long | visual
Upload (.txt/.md/.pdf)
  -> Profile[mode].extract()      Standard: text   Report: pages   Long: font structure   Visual: tables/footnotes/charts
  -> Profile[mode].chunk()        chunks carry metadata: page, section/heading path, element kind, parent id
  -> embeddings (Gemini, on-disk cache)
  -> local Chroma collection `mode`  (+ parent store for Long)  +  document registry (hash, name, chunk count)

Question (+ mode)
  -> Profile[mode].retrieve()     filters (region/chapter/kind), relevance floor
  -> Profile[mode].assemble_context()   Standard/Report: top chunks   Long: parents, dedupe, order, token budget
  -> grounded prompt (page / section citations, exact refusal) -> Gemini
  -> { reply, sources: [{ text, score, source, page, section, kind }] }
```

- **One library per mode.** Each mode owns its Chroma collection and registry, so a plain upload can't
  pollute the structured index and each mode can be reset independently. Per-mode chat history in the
  browser.
- **Profiles are the unit of reuse.** The prototypes in `../RAG-GPO-Annual-Report`,
  `../RAG-World-Bank-Economic-Report` and `../RAG-iMac-Environmental-Report` map one-to-one onto the
  Report, Long document and Visual document profiles; their evals become this repo's regression tests.
- **Planned layout (changes from today):** `app/vector_store.py` -> Chroma-backed; new `app/profiles/`
  (`base.py`, `standard.py`, `report.py`, `long_document.py`, `visual.py`), `app/embeddings.py` (provider
  + disk cache), `samples/` and `data/` (gitignored); `supabase/`, `app/supabase_client.py` and
  `render.yaml` removed in Phase 9.
- **Quota reality:** Gemini's free embedding tier caps at ~1000 requests/day; the three samples total
  ~1,300 chunks. The embedding cache (and reusing the prototypes' caches) keeps re-indexing free.
