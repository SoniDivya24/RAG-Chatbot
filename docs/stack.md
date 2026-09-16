# Stack Decision

## References

- **Concept reference (the actual spec we're extending):**
  `Practical_Generative_AI_Workshop.ipynb` (Colab, Python + LangChain + Gemini). This is
  the detailed demo we were walked through — chat model config, LLM parameters, basic
  chatbot, conversation history/memory, RAG (chunk → embed → vector store → similarity
  search → grounded LLM call). Our code extends this almost line-for-line: same
  `ChatGoogleGenerativeAI` / `GoogleGenerativeAIEmbeddings` / `RecursiveCharacterTextSplitter`
  classes, same grounded system-prompt pattern, same history-as-message-list memory model.
  The three things it explicitly calls out as "production upgrades" are exactly what we're
  adding: a persistent vector store, a web layer, and file upload handling.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Language/runtime | Python (3.11+) | Matches the Colab notebook directly — extends taught code with minimal translation risk |
| Web framework | FastAPI | Async, typed, minimal boilerplate, easy to wrap file upload + JSON routes, serves static frontend too |
| AI orchestration | LangChain (Python): `langchain`, `langchain-google-genai`, `langchain-text-splitters`, `langchain-core` | Same package family used in the notebook |
| LLM (chat) | Google Gemini via `ChatGoogleGenerativeAI` | Required by task; matches notebook |
| Embeddings | Google Gemini via `GoogleGenerativeAIEmbeddings` (`gemini-embedding-001`, 3072-dim) | Same provider as chat, one API key; matches notebook |
| Vector store | Supabase (Postgres + `pgvector` extension) | Required by task; persistent (notebook's own suggested upgrade from `InMemoryVectorStore`) |
| File upload | FastAPI's built-in `UploadFile`/`multipart` handling | No extra dependency needed |
| PDF parsing | `pypdf` (fallback `pdfplumber` if extraction quality needs it) | Pure-Python, no native/canvas deps — safe on Render |
| Frontend | Vanilla JS + HTML + CSS, served as static files by FastAPI | No build step, one deployable service, fast to iterate |
| Deployment | **Render** (free web service, 750 instance-hrs/mo, no card required) | See platform comparison below — Railway's free tier ($1/mo credit) isn't enough to keep a service running |
| Security | Rate limiting (`slowapi`) on `/chat` and `/upload`, request size caps | Basic hardening |

### Why Render over Railway (checked 2026-09-15)

- **Render**: genuine recurring free tier, 750 free instance-hours/month, no credit card
  required to start. Free services spin down after 15 min idle (~1 min cold start on
  next request) — an acceptable trade-off for a demo app.
- **Railway**: the old generous free tier is gone. Current free plan is just **$1/month**
  in usage credit (1 vCPU / 0.5GB cap) — not enough to keep a FastAPI service running
  continuously; you'd need the $5/mo Hobby plan almost immediately.
- Decision: **Render**, revisit only if we hit a concrete limitation (e.g. cold-start
  latency becomes a real problem for the demo).

**Not deviating from this stack** unless we hit a concrete limitation — build the working
core first; creative differentiators come after (see [backlog.md](backlog.md)).
