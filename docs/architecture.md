# Architecture

## Folder Structure (planned)

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
├── render.yaml                 # Render service config (build/start commands, env)
├── app/
│   ├── main.py                 # FastAPI app: routes, static file mount, startup checks
│   ├── config.py               # env var loading + validation
│   ├── supabase_client.py      # lazy Supabase client (service_role key, server-only)
│   ├── text_extract.py         # .txt/.md/.pdf -> plain text
│   ├── vector_store.py         # Supabase/pgvector CRUD + similarity search
│   ├── rag_engine.py           # chunk -> embed -> store -> retrieve pipeline
│   └── chat_session.py         # history + retrieval -> single Gemini call
├── static/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── supabase/
    └── schema.sql              # documents/chunks tables + match_chunks() RPC, idempotent
```

## Core Pipeline (what we're building)

```
Upload (.txt/.md/.pdf)
  → extract_text()                              (app/text_extract.py)
  → RecursiveCharacterTextSplitter, chunk_size=800/overlap=150
  → embeddings.embed_documents()
  → store in Supabase `chunks` table (+ `documents` row)   (app/vector_store.py)

User question
  → embeddings.embed_query()
  → match_chunks() RPC (cosine similarity via pgvector `<=>`)
  → top-k relevant chunks + conversation history
  → grounded system prompt ("use CONTEXT, say you don't know if it's not there")
  → ChatGoogleGenerativeAI.invoke()
  → { reply, sources: [{ text, score, source }] }
```

Conversation history is stateless server-side (each `/api/chat` call receives the full
history from the client, stored in browser `localStorage`) - same reasoning as the
Colab notebook: no shared memory between requests without a session store, and we
don't need one for this scope.
