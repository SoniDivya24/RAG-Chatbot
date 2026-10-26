// Conversations are kept per mode ("rag-chatbot:thread:<mode>"). The single
// pre-modes thread key is read once as the Standard thread so nothing is lost.
const THREAD_KEY_PREFIX = "rag-chatbot:thread:";
const LEGACY_THREAD_KEY = "rag-chatbot:thread";
const MODE_KEY = "rag-chatbot:mode";
const DEFAULT_MODE = "standard";
// Keep in sync with MAX_FILES_PER_UPLOAD in app/main.py - this is just a
// client-side pre-check for a faster/friendlier rejection; the server
// enforces the real limit regardless.
const MAX_FILES_PER_UPLOAD = 5;

const els = {
  uploaderDrop: document.getElementById("uploader-drop"),
  uploaderDropLabel: document.getElementById("uploader-drop-label"),
  uploaderInput: document.getElementById("uploader-input"),
  uploaderAlert: document.getElementById("uploader-alert"),
  libraryCount: document.getElementById("library-count"),
  libraryList: document.getElementById("library-list"),
  threadLog: document.getElementById("thread-log"),
  composerForm: document.getElementById("composer-form"),
  composerInput: document.getElementById("composer-input"),
  composerSubmit: document.getElementById("composer-submit"),
  resetThread: document.getElementById("reset-thread"),
  helpOpen: document.getElementById("help-open"),
  helpClose: document.getElementById("help-close"),
  helpDialog: document.getElementById("help-dialog"),
  dropzoneOverlay: document.getElementById("dropzone-overlay"),
  themeToggle: document.getElementById("theme-toggle"),
  themePopover: document.getElementById("theme-popover"),
  themeSwatches: document.querySelectorAll(".theme-swatch"),
  modeSwitch: document.getElementById("mode-switch"),
  modeDescription: document.getElementById("mode-description"),
  helpMode: document.getElementById("help-mode"),
  dropzoneSubtitle: document.getElementById("dropzone-subtitle"),
};

const ALERT_DURATION_MS = 5000;
let alertTimer = null;

// A toast, not a persistent banner - shows briefly then auto-dismisses so it
// doesn't sit around cluttering the layout.
function showAlert(message) {
  els.uploaderAlert.textContent = message;
  els.uploaderAlert.hidden = false;
  clearTimeout(alertTimer);
  alertTimer = setTimeout(hideAlert, ALERT_DURATION_MS);
}

function hideAlert() {
  clearTimeout(alertTimer);
  els.uploaderAlert.hidden = true;
}

// Conversation lives in the browser, not the server: the backend is
// stateless, so every /api/chat call carries the full recent thread along
// with it.
function loadThread(mode) {
  try {
    const raw =
      localStorage.getItem(THREAD_KEY_PREFIX + mode) ??
      (mode === DEFAULT_MODE ? localStorage.getItem(LEGACY_THREAD_KEY) : null);
    return JSON.parse(raw || "[]");
  } catch {
    return [];
  }
}

function saveThread(mode, entries) {
  try {
    localStorage.setItem(THREAD_KEY_PREFIX + mode, JSON.stringify(entries));
  } catch {
    // storage unavailable (private browsing, quota) - thread just won't survive a reload
  }
}

// Modes come from GET /api/modes. Each one is its own RAG with its own
// documents and conversation; `thread` always holds the current mode's.
let modes = [];
let currentMode = DEFAULT_MODE;
let thread = [];

function modeInfo(id = currentMode) {
  return modes.find((m) => m.id === id);
}

function modeLabel(id = currentMode) {
  return modeInfo(id)?.label ?? id;
}

function apiUrl(path, mode = currentMode) {
  return `${path}${path.includes("?") ? "&" : "?"}mode=${encodeURIComponent(mode)}`;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function inlineMarkdown(str) {
  return str
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.+?)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/(^|[^_])_([^_\s][^_]*?)_(?!_)/g, "$1<em>$2</em>");
}

// Gemini replies commonly use Markdown (**bold**, headers, ordered/unordered
// lists) - render the handful of constructs that actually show up rather
// than displaying literal asterisks and #s. Not a full Markdown parser on
// purpose: this only needs to cover what the model realistically produces,
// not arbitrary documents.
function renderMarkdownLite(text) {
  const lines = escapeHtml(text).split("\n");
  const htmlParts = [];
  let listItems = [];
  let listTag = null;

  function flushList() {
    if (listItems.length > 0) {
      htmlParts.push(`<${listTag}>${listItems.join("")}</${listTag}>`);
      listItems = [];
      listTag = null;
    }
  }

  for (const line of lines) {
    const heading = line.match(/^#{1,6}\s+(.*)/);
    if (heading) {
      flushList();
      htmlParts.push(`<div class="note__heading">${inlineMarkdown(heading[1])}</div>`);
      continue;
    }

    const bullet = line.match(/^\s*[*-]\s+(.*)/);
    if (bullet) {
      if (listTag && listTag !== "ul") flushList();
      listTag = "ul";
      listItems.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
      continue;
    }

    const ordered = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (ordered) {
      if (listTag && listTag !== "ol") flushList();
      listTag = "ol";
      listItems.push(`<li>${inlineMarkdown(ordered[1])}</li>`);
      continue;
    }

    flushList();
    if (line.trim() === "") continue;
    htmlParts.push(`<p>${inlineMarkdown(line)}</p>`);
  }
  flushList();

  return htmlParts.join("") || `<p>${escapeHtml(text)}</p>`;
}

const EXCERPT_MAX_CHARS = 220;

// Chunk text is raw document markdown (headers, bullets, emphasis markers).
// Shown verbatim it reads as visual noise in a small card, so strip the
// syntax down to plain prose before truncating to a short snippet.
function cleanExcerpt(text) {
  const plain = text
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/[*_`]/g, "")
    .replace(/^[-•]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
  return plain.length > EXCERPT_MAX_CHARS
    ? `${plain.slice(0, EXCERPT_MAX_CHARS).trimEnd()}…`
    : plain;
}

function makeTag(text, extraClass) {
  const tag = document.createElement("span");
  tag.className = extraClass ? `citation__tag ${extraClass}` : "citation__tag";
  tag.textContent = text;
  return tag;
}

function buildCitations(sources) {
  const details = document.createElement("details");
  details.className = "citations";

  const summary = document.createElement("summary");
  summary.textContent = `Sources (${sources.length})`;
  details.appendChild(summary);

  for (const s of sources) {
    const card = document.createElement("div");
    card.className = "citation";

    const meta = document.createElement("div");
    meta.className = "citation__meta";
    const source = document.createElement("span");
    source.className = "citation__source";
    source.textContent = s.source || "unlabeled";
    const score = document.createElement("span");
    score.className = "citation__score";
    score.textContent = `${Math.round((s.score ?? 0) * 100)}% match`;
    meta.append(source, score);

    // Where in the document the passage came from - only shown when the mode
    // knows it (page, section / heading path, element type).
    const tags = document.createElement("div");
    tags.className = "citation__tags";
    if (s.page != null) tags.append(makeTag(`p. ${s.page}`));
    if (s.section) tags.append(makeTag(s.section));
    if (s.kind) tags.append(makeTag(s.kind, "citation__tag--kind"));

    const excerpt = document.createElement("p");
    excerpt.className = "citation__excerpt";
    excerpt.textContent = cleanExcerpt(s.text);

    card.append(meta);
    if (tags.children.length > 0) card.append(tags);
    card.append(excerpt);
    details.appendChild(card);
  }

  return details;
}

function appendPendingNote() {
  const note = document.createElement("div");
  note.className = "note note--pending";

  const label = document.createElement("p");
  label.className = "note__pending-label";
  label.textContent = "Thinking...";
  note.appendChild(label);

  const skeleton = document.createElement("div");
  skeleton.className = "skeleton";
  skeleton.innerHTML = `
    <span class="skeleton__line skeleton__line--full"></span>
    <span class="skeleton__line skeleton__line--full"></span>
    <span class="skeleton__line skeleton__line--short"></span>
  `;
  note.appendChild(skeleton);

  els.threadLog.appendChild(note);
  els.threadLog.scrollTop = els.threadLog.scrollHeight;
  return note;
}

// The app's own notes ("Added: some_file_name.pdf") and what the user types are
// literal text: running them through the Markdown renderer turned the underscores
// in file names into italics. Only the model's answers are Markdown.
function renderPlain(text) {
  const paragraphs = text.split("\n").filter((line) => line.trim() !== "");
  return paragraphs.map((line) => `<p>${escapeHtml(line)}</p>`).join("") || "<p></p>";
}

function appendNote(role, text, sources, tagLabel) {
  const note = document.createElement("div");
  note.className = `note note--${role}`;

  // Names the mode that produced an answer, so the standard RAG and the
  // document-specific ones are easy to tell apart.
  if (tagLabel) {
    const tag = document.createElement("div");
    tag.className = "note__tag";
    tag.textContent = tagLabel;
    note.appendChild(tag);
  }

  const content = document.createElement("div");
  content.className = "note__content";
  content.innerHTML = role === "assistant" ? renderMarkdownLite(text) : renderPlain(text);
  note.appendChild(content);

  if (sources && sources.length > 0) {
    note.appendChild(buildCitations(sources));
  }

  els.threadLog.appendChild(note);
  els.threadLog.scrollTop = els.threadLog.scrollHeight;
  return note;
}

let libraryHasDocuments = false;

function renderEmptyState() {
  const info = modeInfo();
  const intro =
    currentMode === DEFAULT_MODE || !info
      ? "Add a document below, then ask questions grounded in what you've added."
      : `${info.description} Add a document below, then ask questions about it.`;
  const note = appendNote("system", intro);
  note.id = "empty-state";

  const questions = info?.exampleQuestions ?? [];
  if (questions.length === 0) return;

  // Example questions only make sense once there is something to ask about;
  // updateEmptyState() reveals them when the library has a document.
  const wrap = document.createElement("div");
  wrap.className = "note__try";
  wrap.hidden = !libraryHasDocuments;

  const label = document.createElement("p");
  label.className = "note__chips-label";
  label.textContent = "Try asking:";

  const chips = document.createElement("div");
  chips.className = "note__chips";
  for (const question of questions) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip-btn";
    chip.textContent = question;
    chip.addEventListener("click", () => sendMessage(question));
    chips.appendChild(chip);
  }

  wrap.append(label, chips);
  note.appendChild(wrap);
}

function updateEmptyState() {
  const wrap = document.querySelector("#empty-state .note__try");
  if (wrap) wrap.hidden = !libraryHasDocuments;
}

function renderThread() {
  els.threadLog.innerHTML = "";
  if (thread.length === 0) {
    renderEmptyState();
    return;
  }
  for (const entry of thread) {
    const isAssistant = entry.role === "assistant";
    appendNote(isAssistant ? "assistant" : "user", entry.content, null, isAssistant ? modeLabel() : null);
  }
}

function renderLibrary(documents) {
  libraryHasDocuments = documents.length > 0;
  updateEmptyState();
  els.libraryCount.textContent = `${documents.length} indexed`;
  els.libraryList.innerHTML = "";
  if (documents.length === 0) {
    const hint = modeInfo()?.uploadHint;
    els.libraryList.innerHTML =
      `<li class="rail__empty">No documents added yet${currentMode === DEFAULT_MODE ? "" : ` in ${escapeHtml(modeLabel())} mode`}. ` +
      `${hint ? `${escapeHtml(hint)} ` : ""}Drag &amp; drop files here, or click "+ Add document".</li>`;
    return;
  }
  for (const doc of documents) {
    const chip = document.createElement("li");
    chip.className = "rail__chip";

    const label = document.createElement("span");
    label.className = "rail__chip-label";
    label.textContent = doc.source_name;
    label.title = `${doc.source_name} - ${doc.chunk_count} chunks`;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "rail__chip-remove";
    remove.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" width="13" height="13">' +
      '<path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />' +
      '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />' +
      '<path d="M10 11v6M14 11v6" />' +
      "</svg>";
    remove.title = `Remove ${doc.source_name}`;
    remove.addEventListener("click", () => removeDocument(doc.id));

    chip.append(label, remove);
    els.libraryList.appendChild(chip);
  }
}

async function refreshLibrary() {
  const mode = currentMode;
  const docsRes = await fetch(apiUrl("/api/documents", mode));
  const docsData = await docsRes.json();
  // The user may have switched modes while this was in flight - don't paint
  // another mode's documents into the current mode's rail.
  if (mode !== currentMode) return;
  renderLibrary(docsData.documents || []);
  els.composerSubmit.disabled = false;
}

async function removeDocument(id) {
  try {
    await fetch(apiUrl(`/api/documents/${id}`), { method: "DELETE" });
    await refreshLibrary();
  } catch (err) {
    showAlert(`Couldn't remove that: ${err.message}`);
  }
}

// Shared by both the file picker and drag-and-drop - uploading happens the
// moment files are provided, no separate "Add" step.
async function uploadFiles(fileList) {
  const files = Array.from(fileList || []);
  if (files.length === 0) return;

  hideAlert();

  if (files.length > MAX_FILES_PER_UPLOAD) {
    showAlert(`Add at most ${MAX_FILES_PER_UPLOAD} files at a time (${files.length} selected).`);
    return;
  }

  els.uploaderDrop.classList.add("busy");
  els.uploaderDropLabel.textContent = "Adding...";
  const mode = currentMode; // uploads go to the mode that was selected when they started

  try {
    const formData = new FormData();
    for (const file of files) formData.append("documents", file);

    const res = await fetch(apiUrl("/api/upload", mode), { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok && (!data.documents || data.documents.length === 0)) {
      throw new Error(data.errors?.[0]?.error || data.error || "Upload failed.");
    }

    if (data.documents?.length > 0) {
      const fresh = data.documents.filter((d) => !d.duplicate).map((d) => d.sourceName);
      const dupes = data.documents.filter((d) => d.duplicate).map((d) => d.sourceName);
      if (mode === currentMode) {
        if (fresh.length > 0) appendNote("system", `Added: ${fresh.join(", ")}.`);
        if (dupes.length > 0) {
          appendNote("system", `Already added (skipped re-indexing): ${dupes.join(", ")}.`);
        }
      }
    }
    if (data.errors?.length > 0) {
      showAlert(data.errors.map((e) => `${e.sourceName}: ${e.error}`).join(" · "));
    }

    await refreshLibrary();
  } catch (err) {
    showAlert(err.message);
  } finally {
    els.uploaderDrop.classList.remove("busy");
    els.uploaderDropLabel.textContent = "+ Add document";
  }
}

els.uploaderInput.addEventListener("change", () => {
  uploadFiles(els.uploaderInput.files);
  els.uploaderInput.value = "";
});

// Drag-and-drop works anywhere on the page, not just over the document rail.
// A plain dragenter/dragleave pair misfires constantly while the pointer
// crosses child elements (each child re-triggers both events) - a counter
// is the standard fix: only truly "outside" when it drops back to zero.
let dragCounter = 0;

window.addEventListener("dragenter", (e) => {
  e.preventDefault();
  dragCounter += 1;
  els.dropzoneOverlay.hidden = false;
});

window.addEventListener("dragover", (e) => e.preventDefault());

window.addEventListener("dragleave", () => {
  dragCounter -= 1;
  if (dragCounter <= 0) {
    dragCounter = 0;
    els.dropzoneOverlay.hidden = true;
  }
});

window.addEventListener("drop", (e) => {
  e.preventDefault();
  dragCounter = 0;
  els.dropzoneOverlay.hidden = true;
  uploadFiles(e.dataTransfer.files);
});

// ---- Theme switcher ----
const THEME_KEY = "rag-chatbot:theme";

function applyTheme(theme) {
  if (theme === "orange") {
    document.documentElement.removeAttribute("data-theme"); // orange is the :root default
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
  for (const swatch of els.themeSwatches) {
    swatch.classList.toggle("active", swatch.dataset.theme === theme);
  }
}

for (const swatch of els.themeSwatches) {
  swatch.addEventListener("click", () => {
    const theme = swatch.dataset.theme;
    applyTheme(theme);
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // storage unavailable - theme just won't persist across reloads
    }
    // Stays open on purpose - only an outside click or Escape closes it, so
    // trying a few themes in a row doesn't mean reopening the popover each time.
  });
}

function openThemePopover() {
  els.themePopover.hidden = false;
  els.themeToggle.setAttribute("aria-expanded", "true");
}

function closeThemePopover() {
  els.themePopover.hidden = true;
  els.themeToggle.setAttribute("aria-expanded", "false");
}

els.themeToggle.addEventListener("click", (e) => {
  e.stopPropagation();
  if (els.themePopover.hidden) openThemePopover();
  else closeThemePopover();
});

// Close on any click outside the popover/toggle, and on Escape.
document.addEventListener("click", (e) => {
  if (els.themePopover.hidden) return;
  if (els.themePopover.contains(e.target) || els.themeToggle.contains(e.target)) return;
  closeThemePopover();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !els.themePopover.hidden) closeThemePopover();
});

applyTheme((() => {
  try {
    return localStorage.getItem(THEME_KEY) || "orange";
  } catch {
    return "orange";
  }
})());

function autosizeComposer() {
  els.composerInput.style.height = "auto";
  els.composerInput.style.height = `${Math.min(els.composerInput.scrollHeight, 160)}px`;
}

els.composerInput.addEventListener("input", autosizeComposer);

// Desktop: Enter sends, Shift+Enter inserts a newline (the usual chat-app
// convention). Mobile: touch keyboards don't have a Shift key to combine
// with Enter, so their Enter/return key is left alone to do its native
// thing (insert a newline / advance to the next line) - sending is always
// an explicit tap on the button there.
const isCoarsePointer = window.matchMedia?.("(pointer: coarse)").matches ?? false;

els.composerInput.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || isCoarsePointer || e.shiftKey) return;
  e.preventDefault();
  els.composerForm.requestSubmit();
});

async function sendMessage(message) {
  if (!message || els.composerSubmit.disabled) return;

  const mode = currentMode; // the answer belongs to the mode it was asked in
  appendNote("user", message);
  els.composerInput.value = "";
  autosizeComposer();
  els.composerSubmit.disabled = true;
  const pending = appendPendingNote();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: thread, mode }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "That request failed.");

    pending.remove();
    if (mode === currentMode) {
      appendNote("assistant", data.reply, data.sources, modeLabel(mode));
      thread.push({ role: "user", content: message });
      thread.push({ role: "assistant", content: data.reply });
      saveThread(mode, thread);
    } else {
      // The user switched modes while waiting: file the exchange under the
      // mode it came from instead of showing it in the wrong conversation.
      const other = loadThread(mode);
      other.push({ role: "user", content: message }, { role: "assistant", content: data.reply });
      saveThread(mode, other);
    }
  } catch (err) {
    pending.remove();
    if (mode === currentMode) appendNote("assistant", `Something went wrong: ${err.message}`);
  } finally {
    els.composerSubmit.disabled = false;
    els.composerInput.focus();
  }
}

els.composerForm.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(els.composerInput.value.trim());
});

els.resetThread.addEventListener("click", async () => {
  const mode = currentMode; // only this mode's conversation and documents are cleared
  thread = [];
  saveThread(mode, thread);
  renderThread();

  // "New conversation" means a genuinely clean slate - documents from the
  // previous conversation shouldn't stay grounding answers in the new one.
  try {
    const res = await fetch(apiUrl("/api/documents", mode));
    const data = await res.json();
    await Promise.all(
      (data.documents || []).map((doc) =>
        fetch(apiUrl(`/api/documents/${doc.id}`, mode), { method: "DELETE" })
      )
    );
  } catch (err) {
    showAlert(`Couldn't clear documents: ${err.message}`);
  }
  await refreshLibrary();
});

els.helpOpen.addEventListener("click", () => els.helpDialog.showModal());
els.helpClose.addEventListener("click", () => els.helpDialog.close());

// A click on the <dialog> element itself (not any of its content) means it
// landed on the backdrop area outside the actual dialog box.
els.helpDialog.addEventListener("click", (e) => {
  if (e.target === els.helpDialog) els.helpDialog.close();
});

// ---- Mode switch ----

function renderModeSwitch() {
  els.modeSwitch.innerHTML = "";
  for (const mode of modes) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "modeswitch__btn";
    btn.dataset.mode = mode.id;
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", String(mode.id === currentMode));
    btn.tabIndex = mode.id === currentMode ? 0 : -1;
    btn.title = mode.available ? mode.description : `${mode.label} - coming soon`;

    const label = document.createElement("span");
    label.textContent = mode.label;
    btn.appendChild(label);

    if (!mode.available) {
      btn.setAttribute("aria-disabled", "true");
      const soon = document.createElement("span");
      soon.className = "modeswitch__soon";
      soon.textContent = "soon";
      btn.appendChild(soon);
    }

    btn.addEventListener("click", () => {
      if (mode.available) setMode(mode.id);
      else showAlert(`${mode.label} mode is coming soon.`);
    });
    els.modeSwitch.appendChild(btn);
  }
}

// Arrow keys move between the available segments (radio-group behaviour).
els.modeSwitch.addEventListener("keydown", (e) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
  const available = modes.filter((m) => m.available);
  if (available.length < 2) return;
  e.preventDefault();
  const index = available.findIndex((m) => m.id === currentMode);
  let next = index;
  if (e.key === "ArrowRight") next = (index + 1) % available.length;
  if (e.key === "ArrowLeft") next = (index - 1 + available.length) % available.length;
  if (e.key === "Home") next = 0;
  if (e.key === "End") next = available.length - 1;
  setMode(available[next].id);
  els.modeSwitch.querySelector(`[data-mode="${available[next].id}"]`)?.focus();
});

// Everything that depends on the active mode, in one place.
function applyModeUI() {
  const info = modeInfo();
  for (const btn of els.modeSwitch.querySelectorAll(".modeswitch__btn")) {
    const active = btn.dataset.mode === currentMode;
    btn.setAttribute("aria-checked", String(active));
    btn.tabIndex = active ? 0 : -1;
  }
  els.modeDescription.textContent = info?.description ?? "";
  els.helpMode.textContent = info ? `Current mode - ${info.label}: ${info.description}` : "";

  const extensions = info?.extensions ?? [".txt", ".md", ".pdf"];
  els.uploaderInput.accept = extensions.join(",");
  els.dropzoneSubtitle.textContent = `${extensions.join(", ")} - up to ${MAX_FILES_PER_UPLOAD} files at a time`;
  els.composerInput.placeholder =
    currentMode === DEFAULT_MODE
      ? "Ask about your documents..."
      : `Ask about your documents (${modeLabel()} mode)...`;
}

function setMode(id, { updateHash = true } = {}) {
  const info = modeInfo(id);
  if (!info || !info.available || id === currentMode) return;

  currentMode = id;
  try {
    localStorage.setItem(MODE_KEY, id);
  } catch {
    // storage unavailable - the mode just won't be remembered across visits
  }
  if (updateHash) history.replaceState(null, "", `#${id}`);

  hideAlert();
  thread = loadThread(id);
  libraryHasDocuments = false;
  // Don't leave the previous mode's documents on screen while this mode's load.
  els.libraryCount.textContent = "…";
  els.libraryList.innerHTML = '<li class="rail__empty">Loading documents…</li>';
  applyModeUI();
  renderThread();
  refreshLibrary().catch((err) => showAlert(`Couldn't load documents: ${err.message}`));
}

function initialMode() {
  const fromHash = location.hash.replace("#", "");
  let remembered = null;
  try {
    remembered = localStorage.getItem(MODE_KEY);
  } catch {
    // storage unavailable
  }
  for (const candidate of [fromHash, remembered]) {
    const info = modeInfo(candidate);
    if (info?.available) return info.id;
  }
  return DEFAULT_MODE;
}

// Following a link / editing the hash by hand switches modes too.
window.addEventListener("hashchange", () => {
  const id = location.hash.replace("#", "");
  if (modeInfo(id)?.available) setMode(id, { updateHash: false });
});

async function init() {
  try {
    const res = await fetch("/api/modes");
    modes = (await res.json()).modes || [];
  } catch {
    modes = [];
  }
  if (modes.length === 0) {
    // Older server without /api/modes: behave as the single-mode app it was.
    modes = [
      { id: DEFAULT_MODE, label: "Standard", description: "", available: true, extensions: [".txt", ".md", ".pdf"] },
    ];
  }

  currentMode = initialMode();
  thread = loadThread(currentMode);
  renderModeSwitch();
  applyModeUI();
  renderThread();
  try {
    await refreshLibrary();
  } catch (err) {
    showAlert(`Couldn't load documents: ${err.message}`);
  }
}

init();
