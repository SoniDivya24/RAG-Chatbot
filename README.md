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

## The four modes

A **mode switch** under the title flips the app between four pipelines. Each mode has its own documents
and its own conversation, and answers are tagged with the mode that produced them.

| Mode | Use it for | What it does |
|---|---|---|
| **Standard** | Any `.txt`, `.md` or `.pdf` | The general-purpose RAG described above |
| **Report** | Plain-text PDF reports | Keeps each passage's page, cites pages, and replies "I could not find this in the document." (no sources) when the report doesn't cover the question |
| **Long document** | 100+ page structured reports | Recovers the chapter / section / box outline, so a South Asia question is answered from the South Asia section, "Chapter 3" means Chapter 3, and the model gets the text *around* each hit within a token budget |
| **Visual document** | PDFs whose facts sit in tables, charts, footnotes and call-outs | Rebuilds tables so each value carries its row and column, keeps footnotes with their claims, and has the model describe chart pages |

Report, Long document and Visual document each have a built-in **sample**: a "Load sample" button appears
while the mode's library is empty. The three PDFs are not in the repo (see below).

### Loading the samples

Copy the three PDFs into `samples/` (gitignored) under these names:
`GPO-Anual-report.pdf` (Report), `GEP-Jun-2026.pdf` (Long document), `iMac_PER_Oct2024.pdf` (Visual document).
The first load of each embeds it, which counts against the free Gemini tier's ~1,000 embedding calls/day; the
result is cached in `data/`, so later loads are free. Without the files the buttons just don't appear, and
uploading works as normal.

### Evaluation

`eval/run_eval.py --mode <mode>` indexes the sample into a throwaway library and runs a fixed question set
(15-21 questions each: core, extended and "not in the document" refusals). [docs/results/](docs/results/README.md)
has the combined table, including Standard mode on the same documents for comparison. Current results:

| Run | Result |
|---|---|
| Report on the GPO 2018 Annual Report | core 3/3, extended 8/8, refusals 4/4 |
| Long document on the World Bank GEP (June 2026) | core 3/3, extended 8/8, refusals 4/4; 0/8 scoped questions got chunks from the wrong chapter or region |
| Visual document on the iMac environmental report | 21/21 (Standard mode on the same report: 19/21) |

Answer correctness is an automatic substring check and the question sets are small - a sanity check, not a
benchmark. On plain prose (the GPO report) Standard mode answers just as correctly; Report's advantage there
is page-tagged sources and clean refusals.

The Long document outline for PDFs other than the reference report is a generic font-size heuristic, tested
on synthetic PDFs only - best-effort. Roadmap and history: [docs/phases.md](docs/phases.md).

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
# folder, never your real library. ~170 tests.
```
