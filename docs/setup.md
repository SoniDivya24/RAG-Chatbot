# Setup

## Setup Checklist (things we need from you / to configure)

- [ ] **Gemini API key** - from https://aistudio.google.com/app/apikey → `GOOGLE_API_KEY`
- [ ] **Supabase project** - new project at https://supabase.com →
  - `SUPABASE_URL` (Project Settings → API)
  - `SUPABASE_SERVICE_ROLE_KEY` (Project Settings → API - **secret, server-only, never sent to browser**)
  - Run `supabase/schema.sql` in the SQL Editor once `pgvector` extension is enabled
- [ ] **Render account** - for deployment; env vars set in Render dashboard (encrypted)
- [ ] **.env.local** - created locally (see Environment Variables below), gitignored,
  holds real keys - there is no committed `.env.example` template; this list is the
  reference for what to put in it
- [ ] **.gitignore** - `.venv/`, `__pycache__/`, `.env.local`, `.env`
- [ ] **requirements.txt** - dependencies from [stack.md](stack.md)
- [ ] **.claude/** - project-level Claude Code config (added as needed; not blocking)

## Environment Variables

```
# Required
GOOGLE_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Optional (defaults shown)
CHAT_MODEL=gemini-3.1-flash-lite
EMBEDDING_MODEL=models/gemini-embedding-001
PORT=8000
```
