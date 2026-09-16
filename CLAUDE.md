# RAG-Chatbot

A RAG (Retrieval-Augmented Generation) chatbot: document upload → parsing → chunking →
embeddings → retrieval → grounded LLM answers.

**Read `README.md` first** — it links into the full plan (stack, folder structure,
setup, frontend, phases, backlog), each split into its own file under `docs/` for
readability. Keep those files up to date as decisions change; don't let them go stale.
(There is no `PLANNING.md` and no `docs/README.md`/`docs/index.md` — the root `README.md`
is the single entry point, to avoid two README-like files existing at once.)

**Then read `docs/progress.md`** — it's the single source of truth for exactly where
development left off: a status (`Not started` / `In progress` / `Blocked` / `Done`) per
phase from `docs/phases.md`. The first non-`Done` row is where to pick up. Update this
file's status the moment a phase starts or finishes — don't batch it for later.

**Standing rule for this file:** update `CLAUDE.md` itself, in the same turn, whenever
anything changes that a fresh session would need to know to not miss context — a new
top-level file/folder, a change to what's in `.claude/`, a stack/tooling decision, a new
standing rule from the user. Don't batch it for later; if it's worth remembering, it's
worth writing down immediately.

Quick summary (see `README.md` for full detail and rationale):
- Python + FastAPI backend, LangChain + Google Gemini (chat + embeddings)
- Supabase (Postgres + pgvector) as the persistent vector store
- Vanilla HTML/CSS/JS frontend served as static files by FastAPI
- Deployed to Render (free tier)

## `.mcp.json` — Supabase MCP server

Also gitignored, local-only, same reasoning as `.claude/`. Configures the official
Supabase MCP server (`@supabase/mcp-server-supabase`), scoped to this one project via
`--project-ref`, so Claude Code can run migrations/queries against Supabase directly
(used in Phase 3 to apply `supabase/schema.sql` and check advisors) instead of asking
you to paste SQL into the dashboard by hand. Its `SUPABASE_ACCESS_TOKEN` is not
hardcoded in the file — it's expanded from the environment at launch. That value lives
in `.claude/settings.json`'s `env` block (also gitignored, also local-only), not
`.env.local` — `.env.local` is for the *app's* runtime config, this token is only for
Claude Code's own tooling and was kept separate on purpose.

## `.claude/` folder — how it's organized

The `.claude/` directory is this project's local Claude Code configuration. It is
**gitignored on purpose** (see `.gitignore`) — it's machine-local tooling config, not
project source, and may contain permission grants specific to this developer's setup.
Nothing in it should ever be assumed to exist in a fresh clone of this repo; if a
teammate needs the same setup, they recreate `.claude/` themselves (this file documents
what to put in it).

```
.claude/
├── settings.json     # Permission allowlist/denylist for this project
├── status-log.md     # Local-only chronological decision/progress history
├── commands/         # Custom slash commands, one Markdown file per command
│   └── run-dev.md    # /run-dev — starts the FastAPI dev server (uvicorn, auto-reload)
└── agents/            # Custom subagents (empty for now — add project-specific
                        # subagents here if a task needs a dedicated agent, e.g. a
                        # "rag-eval" agent for testing retrieval quality later)
```

**How the pieces link together:**

- **`status-log.md`** is the chronological history of decisions and progress — every
  time something is decided or a phase completes, append an entry here. Kept separate
  from `docs/` on purpose: `docs/` is committed and stays a clean, current statement of
  the plan; this log is local-only and can be as verbose/historical as needed without
  cluttering the committed docs.
- **`settings.json`** scopes what Claude Code can run here without a permission prompt:
  Python/pip/uvicorn/pytest, and read-only git (`status`, `diff`, `log`). It explicitly
  denies force-push and hard-reset so those always require confirmation. This is
  intentionally narrow — expand it here (not globally) as the project's real commands
  become clear (e.g. once we add a test runner or a lint command).
- **`commands/`** holds project-specific slash commands invoked as `/run-dev`. Each file
  is a Markdown prompt with YAML frontmatter (`description`). Add a new file here
  whenever a multi-step local workflow (start server, run migrations, seed test data)
  is worth turning into a one-word command instead of re-explaining it every session.
- **`agents/`** is currently empty. It's the place for a custom subagent definition
  (Markdown + frontmatter, same shape as commands) if a recurring task needs one — e.g.
  a subagent whose only job is running retrieval-quality checks against
  `supabase/schema.sql` test data. Nothing needs one yet.
- This `CLAUDE.md` at the project root is what every Claude Code session reads
  automatically on startup — it's the entry point that explains what `.claude/`
  contains and why, since `.claude/` itself is invisible to git and therefore invisible
  to anyone who hasn't read this file.

**Rule going forward:** any time something is added to `.claude/` (a new command, a new
agent, a settings.json change), update the description above in the same turn — this
section should always match what's actually in the folder.
