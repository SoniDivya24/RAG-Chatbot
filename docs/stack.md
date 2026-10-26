# Stack

The app is **local-only** (since Phase 9): no database server, no hosting. Everything it stores lives under
the gitignored `data/` folder. Gemini is the only external service.

## References

- **Concept reference:** `Practical_Generative_AI_Workshop.ipynb` (Colab, Python + LangChain + Gemini) -
  chat model config, conversation memory, and RAG (chunk -> embed -> vector store -> similarity search ->
  grounded call). The code extends it with the same LangChain classes, the same grounded system-prompt
  pattern and the same history-as-messages memory model, plus the production upgrades it names: a persistent
  vector store, a web layer and file upload.
- **Scenario prototypes:** three separate repos (`RAG-GPO-Annual-Report`, `RAG-World-Bank-Economic-Report`,
  `RAG-iMac-Environmental-Report`) whose techniques were ported into the modes below.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Language/runtime | Python 3.11+ | Matches the Colab notebook |
| Web framework | FastAPI | Typed, minimal; file upload + JSON routes; serves the static frontend |
| AI orchestration | LangChain (`langchain`, `langchain-google-genai`, `langchain-text-splitters`, `langchain-core`) | Same package family as the notebook |
| LLM (chat, chart vision) | Google Gemini via `ChatGoogleGenerativeAI` (`CHAT_MODEL`, default `gemini-3.1-flash-lite`) | One API key; also reads the chart page in Visual mode |
| Embeddings | Gemini `gemini-embedding-001` behind a **SQLite cache** (`app/embeddings.py`) | The free tier allows ~1,000 embedding calls/day; the cache makes re-indexing free |
| Vector store | **Chroma** (cosine) on local disk + a JSON document registry (`app/vector_store.py`) | No server to run; one library per mode under `data/modes/<mode>/` |
| PDF parsing | `pypdf` (Report mode) and `pymupdf` (Visual and Long document modes: geometry, fonts) | Report only needs page text; the other two need layout |
| Frontend | Vanilla JS + HTML + CSS, served as static files by FastAPI | No build step |
| Security | `slowapi` rate limits on chat/upload/sample, 25 MB upload cap, the sample route never takes a file name from the caller | Basic hardening |
| Tests | `pytest` (offline with a fake embedder; a few smoke tests call Gemini) | See README |

## The four modes

| Mode | For | What it does differently |
|---|---|---|
| Standard | Any `.txt` / `.md` / `.pdf` | 800/150 chunks, relevance floor 0.62, temperature 0.7 |
| Report | Plain-text PDF reports | Page-tagged chunks that never span pages, running heads/feet removed, page citations, exact refusal with no sources, temperature 0 |
| Long document | 100+ page structured reports | Outline from fonts (chapter / region / box), section-bounded chunks with heading path, parent sections as context under a token budget, region/chapter filters, a no-model reply for a chapter that doesn't exist |
| Visual document | Facts in tables, charts, footnotes, call-outs | Tables rebuilt from geometry, footnotes kept with their claims, chart pages described by the model (cached), element-typed chunks |

Install note: `pip install --only-binary=:all: pymupdf` if pip tries a source build; import it as `pymupdf`.

History: the first version (Phases 0-8) used Supabase pgvector and was deployed on Render; Part 2 of
[phases.md](phases.md) replaced both with the local stack above.
