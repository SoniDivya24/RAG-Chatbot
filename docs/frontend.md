# Frontend Plan

Two-panel single page, vanilla HTML/CSS/JS, served as static files by FastAPI.

**Sidebar - document management**
- File upload (click or drag, accepts `.txt`, `.md`, `.pdf`)
- Document list: filename, chunk count, uploaded date, delete (×) per document
- Status bar: total documents / total chunks indexed

**Main panel - chat**
- User/assistant message bubbles, auto-scroll, "Thinking…" pending state
- Clear-conversation button
- Inline error states for failed uploads/chat calls

**Per-answer source display (decided):**
- Each assistant reply has an expandable **"Sources"** section
- Expanding it shows, per retrieved chunk: the **source filename**, the **similarity
  score**, and the **actual chunk text** that was retrieved and sent to the LLM
- Purpose: visually proves the answer is grounded in real retrieved content, not just
  "trust me" - this is the single clearest way to demonstrate the RAG mechanism working
  for a demo/assignment audience
- Data needed from `/api/chat` response: already planned (`sources: [{ text, score,
  source }]`) - no backend changes needed beyond what's in [architecture.md](architecture.md)

**State:**
- Chat history in `localStorage`
- Document list + counts re-fetched from `/api/documents` and `/api/status` after every
  upload/delete

## Mode switch (built, Part 2 - Phase 11)

The current UI is a masthead (brand, theme picker, help, "New conversation"), a **mode bar**, the chat
thread, a horizontal document rail and the composer. (The two-panel sidebar layout above is the original
design; the app has since moved to this single-column layout.)

A **segmented control** in the mode bar switches the whole app between the normal RAG and the three
scenario RAGs, in one component (no separate pages):

`[ Standard ] [ Report ] [ Long document ] [ Visual document ]`  *(working labels - to confirm)*

- Segments are built from `GET /api/modes`. Modes the backend hasn't implemented yet are **disabled with a
  "soon" tag** (clicking explains why); they switch on automatically when their profile becomes available.
- The selected mode scopes **everything below it**: the document rail and its count, the upload target
  (`?mode=`), the accepted file types and the drop-zone hint, the chat history (`localStorage` key
  `rag-chatbot:thread:<mode>`; the old single-thread key is read once as the Standard thread), the empty
  state, the composer placeholder and the help dialog's mode line.
- The empty state offers **example-question chips** (each profile's `exampleQuestions`); they appear once the
  mode's library has a document, and clicking one sends it.
- Each assistant answer carries a small **mode tag** (e.g. STANDARD) so it is clear which RAG produced it.
- The **Sources panel** keeps filename, match % and excerpt, and adds **tags** when the mode knows them:
  `p. N`, the section / heading path, and the element type (text, table, chart, footnote, call-out).
- The active mode lives in the **URL hash** (`#report`) and `localStorage`, so it survives reloads and can be
  linked; arrow keys / Home / End move between available segments (radio-group behaviour).
- "New conversation" clears the chat and the documents of the **current mode only**.
- A response that arrives after the user has switched modes is filed under the mode it was asked in, never
  shown in the wrong conversation.
- On phones the control becomes a 2 x 2 grid (a sideways-scrolling row would hide the last mode); the
  description wraps under it.
- Each mode's **Load sample document** action arrives with the samples (Phase 15).
