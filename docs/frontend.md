# Frontend Plan

Two-panel single page, vanilla HTML/CSS/JS, served as static files by FastAPI.

**Sidebar — document management**
- File upload (click or drag, accepts `.txt`, `.md`, `.pdf`)
- Document list: filename, chunk count, uploaded date, delete (×) per document
- Status bar: total documents / total chunks indexed

**Main panel — chat**
- User/assistant message bubbles, auto-scroll, "Thinking…" pending state
- Clear-conversation button
- Inline error states for failed uploads/chat calls

**Per-answer source display (decided):**
- Each assistant reply has an expandable **"Sources"** section
- Expanding it shows, per retrieved chunk: the **source filename**, the **similarity
  score**, and the **actual chunk text** that was retrieved and sent to the LLM
- Purpose: visually proves the answer is grounded in real retrieved content, not just
  "trust me" — this is the single clearest way to demonstrate the RAG mechanism working
  for a demo/assignment audience
- Data needed from `/api/chat` response: already planned (`sources: [{ text, score,
  source }]`) — no backend changes needed beyond what's in [architecture.md](architecture.md)

**State:**
- Chat history in `localStorage`
- Document list + counts re-fetched from `/api/documents` and `/api/status` after every
  upload/delete
