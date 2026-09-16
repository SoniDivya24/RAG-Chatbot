const THREAD_KEY = "rag-chatbot:thread";
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
function loadThread() {
  try {
    return JSON.parse(localStorage.getItem(THREAD_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveThread(entries) {
  try {
    localStorage.setItem(THREAD_KEY, JSON.stringify(entries));
  } catch {
    // storage unavailable (private browsing, quota) - thread just won't survive a reload
  }
}

let thread = loadThread();

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

    const excerpt = document.createElement("p");
    excerpt.className = "citation__excerpt";
    excerpt.textContent = cleanExcerpt(s.text);

    card.append(meta, excerpt);
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

function appendNote(role, text, sources) {
  const note = document.createElement("div");
  note.className = `note note--${role}`;

  const content = document.createElement("div");
  content.className = "note__content";
  content.innerHTML = renderMarkdownLite(text);
  note.appendChild(content);

  if (sources && sources.length > 0) {
    note.appendChild(buildCitations(sources));
  }

  els.threadLog.appendChild(note);
  els.threadLog.scrollTop = els.threadLog.scrollHeight;
  return note;
}

function renderThread() {
  els.threadLog.innerHTML = "";
  if (thread.length === 0) {
    appendNote("system", "Add a document below, then ask questions grounded in what you've added.");
    return;
  }
  for (const entry of thread) {
    appendNote(entry.role === "assistant" ? "assistant" : "user", entry.content);
  }
}

function renderLibrary(documents) {
  els.libraryCount.textContent = `${documents.length} indexed`;
  els.libraryList.innerHTML = "";
  if (documents.length === 0) {
    els.libraryList.innerHTML = `<li class="rail__empty">No documents added yet. Drag &amp; drop files here, or click "+ Add document".</li>`;
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
  const [docsRes, statusRes] = await Promise.all([fetch("/api/documents"), fetch("/api/status")]);
  const docsData = await docsRes.json();
  await statusRes.json();
  renderLibrary(docsData.documents || []);
  els.composerSubmit.disabled = false;
}

async function removeDocument(id) {
  try {
    await fetch(`/api/documents/${id}`, { method: "DELETE" });
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

  try {
    const formData = new FormData();
    for (const file of files) formData.append("documents", file);

    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok && (!data.documents || data.documents.length === 0)) {
      throw new Error(data.errors?.[0]?.error || data.error || "Upload failed.");
    }

    if (data.documents?.length > 0) {
      const fresh = data.documents.filter((d) => !d.duplicate).map((d) => d.sourceName);
      const dupes = data.documents.filter((d) => d.duplicate).map((d) => d.sourceName);
      if (fresh.length > 0) appendNote("system", `Added: ${fresh.join(", ")}.`);
      if (dupes.length > 0) {
        appendNote("system", `Already added (skipped re-indexing): ${dupes.join(", ")}.`);
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

els.composerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = els.composerInput.value.trim();
  if (!message) return;

  appendNote("user", message);
  els.composerInput.value = "";
  autosizeComposer();
  els.composerSubmit.disabled = true;
  const pending = appendPendingNote();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: thread }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "That request failed.");

    pending.remove();
    appendNote("assistant", data.reply, data.sources);

    thread.push({ role: "user", content: message });
    thread.push({ role: "assistant", content: data.reply });
    saveThread(thread);
  } catch (err) {
    pending.remove();
    appendNote("assistant", `Something went wrong: ${err.message}`);
  } finally {
    els.composerSubmit.disabled = false;
    els.composerInput.focus();
  }
});

els.resetThread.addEventListener("click", async () => {
  thread = [];
  saveThread(thread);
  renderThread();

  // "New conversation" means a genuinely clean slate - documents from the
  // previous conversation shouldn't stay grounding answers in the new one.
  try {
    const res = await fetch("/api/documents");
    const data = await res.json();
    await Promise.all(
      (data.documents || []).map((doc) =>
        fetch(`/api/documents/${doc.id}`, { method: "DELETE" })
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

renderThread();
refreshLibrary();
