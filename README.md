<div align="center">

# RAG Chatbot

Upload your own documents and ask questions about them — answers are grounded in
what you actually uploaded, with the exact source passages shown alongside every
reply.

**Runs entirely on your machine** - the index, your documents' text and the
embedding cache all live in a local `data/` folder. No database, no hosting.

</div>

<br>

![Screenshot of the chat UI answering a question grounded in an uploaded document, with the Sources panel expanded](docs/assets/screenshot.png)

## What it does

- **Upload** `.txt`, `.md`, or `.pdf` files (drag-and-drop or the file picker).
- **Ask questions** about them in plain conversation - replies stay grounded in
  your documents rather than the model's own general knowledge, and honestly
  say "I don't have that information" when nothing relevant was uploaded.
- **See the receipts.** Every grounded answer has an expandable **Sources**
  panel showing exactly which passage it came from, which file, and how
  strong the match was - so you're never just taking the answer on faith.
- **Multiple documents, no duplicates.** Upload as many files as you like;
  re-uploading the same content (even under a different filename) is
  detected and skipped rather than indexed twice.
- **5 color themes**, a clean conversation history that persists between
  visits, and a "New conversation" button that gives you a genuinely clean
  slate (chat + documents both cleared).

## How it works

```
upload → extract text → chunk → embed (Gemini, cached on disk) → store (local Chroma index)
                                                        ↓
your question → embed → similarity search → relevant chunks → grounded answer (Gemini)
```

Built with **Python + FastAPI** on the backend, **LangChain + Google Gemini**
for chat and embeddings, a **local Chroma** vector index (plus a small JSON
document registry and a SQLite embedding cache, all under `data/`), and a
**vanilla HTML/CSS/JS** frontend - no frontend framework, no build step.
Gemini is the only external service; nothing is deployed.

A **mode switch** under the title flips the app between this **Standard** RAG
and three document-specific RAGs (**Report**, **Long document**, **Visual
document**). Each mode has its own documents and its own conversation.
All four modes are built: **Standard**, **Report**, **Long document** and **Visual document**. Report
mode is for plain-text PDF reports: it keeps every passage's page, cites pages
in its answers, and answers "I could not find this in the document." (with no
sources) when the report doesn't cover the question. **Visual document** mode is for
PDFs whose facts sit in tables, charts, footnotes and call-outs: tables are rebuilt so each value
carries its row and column, footnotes travel with the claims they limit, and chart pages are
described by the model - so a question about a footprint split or a power-consumption table finds
its number instead of a nearby sentence. **Long document** mode is for 100+ page structured
reports: it recovers the chapter / section / box outline, so a question about South Asia is answered from
the South Asia section (not East Asia's), "Chapter 3" means Chapter 3, and the model is given the text
*around* each hit - ordered and kept within a token budget - instead of a pile of fragments. Answers are tagged with the mode that
produced them, and the Sources panel shows page / section / element type where
a mode provides them. See Part 2 of [docs/phases.md](docs/phases.md) for the
roadmap.

For the full technical write-up (architecture, schema, API contract, and
how each part was built and verified), see [docs/](docs/) - start with
[docs/architecture.md](docs/architecture.md). Current build status/phase
tracking lives in [docs/progress.md](docs/progress.md).

## Running it yourself

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Put GOOGLE_API_KEY (and optionally CHAT_MODEL) in .env.local - that's the
# only credential needed. See docs/setup.md for the full list.

uvicorn app.main:app --reload --port 8000
# -> open http://localhost:8000
```

```bash
pytest
# Offline tests (store, embedding cache, engine) need no key. The smoke tests
# make real Gemini calls and need GOOGLE_API_KEY. Tests use a throwaway data
# folder, never your real library.
```
