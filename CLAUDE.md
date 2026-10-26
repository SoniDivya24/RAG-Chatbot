# RAG-Chatbot

**Location:** `~/Desktop/ProjectWork/RAG-Projects/RAG-Chatbot` (moved there from
`~/Desktop/ProjectWork/RAG-Chatbot` on 2026-10-22). `RAG-Projects/` is the parent folder
for this and the other RAG-related repos. Run Claude Code from this folder; the `.venv`
was rebuilt at the new path (virtualenvs hold absolute paths and break when moved).

## Direction change (2026-10-26, from the user) - read this first

Two things changed, and the "Quick summary" below is **partly out of date until they land**:

1. **The three scenarios belong in this system.** The sibling repos (`../RAG-GPO-Annual-Report`
   = plain-text report Q&A, `../RAG-World-Bank-Economic-Report` = long structured report with
   hierarchical chunking + context management, `../RAG-iMac-Environmental-Report` = facts in tables,
   charts and footnotes) were built as separate projects by mistake. They are now **reference
   implementations to port into `RAG-Chatbot`** as document profiles in one pipeline; their evals and
   sample questions become this app's regression tests. Don't extend them further.
2. **Local-only.** Remove the Supabase (pgvector) dependency and the Render deployment; store the index
   locally (Chroma under `data/`, gitignored, as in the siblings). Models stay on the Gemini API unless
   the user decides otherwise. (Note: the app deployed to Render, not Vercel.)

**Decisions made (2026-10-26):**
- **One component, a mode switch.** A segmented control in the UI flips between the normal RAG and the
  three scenario RAGs (working labels: Standard / Report / Long document / Visual document). The user
  picks the mode explicitly (no auto-detection yet). Each mode has its **own library, index and chat
  history**; uploads go to the selected mode.
- **Models:** Gemini stays for chat, embeddings and chart vision; embeddings get an **on-disk cache**
  (the free tier caps at ~1000/day). The user offered a **Groq key** - not needed now; a backlog item.
  (Groq chat is reliable; its embeddings endpoint is unconfirmed - verify before relying on it.)
- **Sample PDFs:** built-in samples, **gitignored** under `samples/` (originals in
  `~/Desktop/ProjectData/RAG-Projects/GPO Annual Report/drive-download-20261022T103331Z-1-001/`).
- **The three scenario repos:** the user manages them; don't touch them, only read them to port code.
- **Plan and status:** Part 2 of `docs/phases.md` (Phases 9-16) and `docs/progress.md`. **Phase 9
  (local-only foundation) is Done; Phase 10 (pluggable pipeline + `mode` plumbing) is next.**

## Sibling repos (see `../CLAUDE.md` for the full registry)

Other RAG repos live next to this one under `~/Desktop/ProjectWork/RAG-Projects/`, currently
`../RAG-GPO-Annual-Report`, `../RAG-World-Bank-Economic-Report` and `../RAG-iMac-Environmental-Report`. They're added to this project's `permissions.additionalDirectories`
in `.claude/settings.json`, so they can be read for reference (their `CLAUDE.md` →
`README.md` → `docs/progress.md` → `docs/`). Read-only unless the user asks otherwise. When
a repo is added/renamed/moved, update `../CLAUDE.md`, this section and that setting together.

A RAG (Retrieval-Augmented Generation) chatbot: document upload → parsing → chunking →
embeddings → retrieval → grounded LLM answers.

**Read `README.md` first** - it links into the full plan (stack, folder structure,
setup, frontend, phases, backlog), each split into its own file under `docs/` for
readability. Keep those files up to date as decisions change; don't let them go stale.
(There is no `PLANNING.md` and no `docs/README.md`/`docs/index.md` - the root `README.md`
is the single entry point, to avoid two README-like files existing at once.)

**Then read `docs/progress.md`** - it's the single source of truth for exactly where
development left off: a status (`Not started` / `In progress` / `Blocked` / `Done`) per
phase from `docs/phases.md`. The first non-`Done` row is where to pick up. Update this
file's status the moment a phase starts or finishes - don't batch it for later.

**Standing rule for this file:** update `CLAUDE.md` itself, in the same turn, whenever
anything changes that a fresh session would need to know to not miss context - a new
top-level file/folder, a change to what's in `.claude/`, a stack/tooling decision, a new
standing rule from the user. Don't batch it for later; if it's worth remembering, it's
worth writing down immediately.

Quick summary (see `README.md` for full detail and rationale):
- Python + FastAPI backend, LangChain + Google Gemini (chat + embeddings)
- **Local-only storage (since Phase 9, 2026-10-26):** Chroma index + `documents.json` registry + SQLite
  embedding cache, all under the gitignored `data/` folder (`DATA_DIR` overrides it). No Supabase, no
  hosting. `GOOGLE_API_KEY` is the only credential. Tests use a throwaway data folder (`tests/conftest.py`).
- Vanilla HTML/CSS/JS frontend served as static files by FastAPI
- Next: a mode switch + three scenario pipelines (Phases 10-16, see `docs/phases.md` Part 2)

## `.mcp.json` - Supabase MCP server (**obsolete since Phase 9** - the app no longer uses Supabase; the file and the `SUPABASE_ACCESS_TOKEN` in `.claude/settings.json` are leftovers the user can delete whenever they like, along with the cloud project)

Also gitignored, local-only, same reasoning as `.claude/`. Configures the official
Supabase MCP server (`@supabase/mcp-server-supabase`), scoped to this one project via
`--project-ref`, so Claude Code can run migrations/queries against Supabase directly
(used in Phase 3 to apply `supabase/schema.sql` and check advisors) instead of asking
you to paste SQL into the dashboard by hand. Its `SUPABASE_ACCESS_TOKEN` is not
hardcoded in the file - it's expanded from the environment at launch. That value lives
in `.claude/settings.json`'s `env` block (also gitignored, also local-only), not
`.env.local` - `.env.local` is for the *app's* runtime config, this token is only for
Claude Code's own tooling and was kept separate on purpose.

## `.claude/` folder - how it's organized

The `.claude/` directory is this project's local Claude Code configuration. It is
**gitignored on purpose** (see `.gitignore`) - it's machine-local tooling config, not
project source, and may contain permission grants specific to this developer's setup.
Nothing in it should ever be assumed to exist in a fresh clone of this repo; if a
teammate needs the same setup, they recreate `.claude/` themselves (this file documents
what to put in it).

```
.claude/
├── settings.json     # Permission allowlist/denylist for this project
├── status-log.md     # Local-only chronological decision/progress history
├── commands/         # Custom slash commands, one Markdown file per command
│   └── run-dev.md    # /run-dev - starts the FastAPI dev server (uvicorn, auto-reload)
└── agents/            # Custom subagents (empty for now - add project-specific
                        # subagents here if a task needs a dedicated agent, e.g. a
                        # "rag-eval" agent for testing retrieval quality later)
```

**How the pieces link together:**

- **`status-log.md`** is the chronological history of decisions and progress - every
  time something is decided or a phase completes, append an entry here. Kept separate
  from `docs/` on purpose: `docs/` is committed and stays a clean, current statement of
  the plan; this log is local-only and can be as verbose/historical as needed without
  cluttering the committed docs.
- **`settings.json`** scopes what Claude Code can run here without a permission prompt:
  Python/pip/uvicorn/pytest, and read-only git (`status`, `diff`, `log`). It explicitly
  denies force-push and hard-reset so those always require confirmation. This is
  intentionally narrow - expand it here (not globally) as the project's real commands
  become clear (e.g. once we add a test runner or a lint command).
- **`commands/`** holds project-specific slash commands invoked as `/run-dev`. Each file
  is a Markdown prompt with YAML frontmatter (`description`). Add a new file here
  whenever a multi-step local workflow (start server, run migrations, seed test data)
  is worth turning into a one-word command instead of re-explaining it every session.
- **`agents/`** is currently empty. It's the place for a custom subagent definition
  (Markdown + frontmatter, same shape as commands) if a recurring task needs one - e.g.
  a subagent whose only job is running retrieval-quality checks against
  `supabase/schema.sql` test data. Nothing needs one yet.
- This `CLAUDE.md` at the project root is what every Claude Code session reads
  automatically on startup - it's the entry point that explains what `.claude/`
  contains and why, since `.claude/` itself is invisible to git and therefore invisible
  to anyone who hasn't read this file.

**Rule going forward:** any time something is added to `.claude/` (a new command, a new
agent, a settings.json change), update the description above in the same turn - this
section should always match what's actually in the folder.

## `demo-video/` folder - the 2-min demo video production

Gitignored at the root, same reasoning as `.claude/` - it's local production material
(script drafts, screen recordings, voiceover audio, exports) for the 2-minute demo video
(1 min chatbot demo + 1 min code workflow explanation), not project source. Nothing in
it should be assumed to exist in a fresh clone.

```
demo-video/
└── script.md    # Voiceover script + synced screen-action beats, timestamped.
                  # Currently in review with the user before recording starts.
```

The plan: record the screen (Playwright) and the voiceover separately, keeping them in
sync beat-by-beat per `script.md` - if the screen action finishes before its narration
line, hold the frame; if the line finishes first, let the action complete before cutting.
`script.md` is the source of truth for both the narration text and what should be on
screen at that moment; update it first if either changes.

**Rule going forward:** as production moves from script → recording → editing, keep this
section current with what's actually in `demo-video/` (e.g. once a Playwright recording
script or raw takes are added).
