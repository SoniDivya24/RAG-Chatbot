const HISTORY_KEY = "rag-chatbot:history";

const fileInput = document.getElementById("file-input");
const fileDrop = document.getElementById("file-drop");
const fileDropLabel = document.getElementById("file-drop-label");
const uploadForm = document.getElementById("upload-form");
const uploadBtn = document.getElementById("upload-btn");
const uploadError = document.getElementById("upload-error");

const statusChunks = document.getElementById("status-chunks");
const docList = document.getElementById("doc-list");

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const messagesEl = document.getElementById("messages");
const resetBtn = document.getElementById("reset-btn");

// Chat history lives in the browser, not the server: the backend is stateless,
// so every /api/chat call carries the full recent history along with it.
function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(history) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch {
    // localStorage unavailable (private browsing, quota) — conversation just won't persist across reloads.
  }
}

let history = loadHistory();

function buildSourcesSection(sources) {
  const wrapper = document.createElement("div");
  wrapper.className = "sources-section";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "sources-toggle";
  toggle.textContent = `Sources (${sources.length}) ▾`;

  const list = document.createElement("div");
  list.className = "sources-list";
  list.hidden = true;

  for (const s of sources) {
    const card = document.createElement("div");
    card.className = "source-card";

    const meta = document.createElement("div");
    meta.className = "source-meta";
    const name = document.createElement("span");
    name.className = "source-name";
    name.textContent = s.source || "unknown source";
    const score = document.createElement("span");
    score.className = "source-score";
    score.textContent = `${Math.round((s.score ?? 0) * 100)}% match`;
    meta.appendChild(name);
    meta.appendChild(score);

    const text = document.createElement("div");
    text.className = "source-text";
    text.textContent = s.text;

    card.appendChild(meta);
    card.appendChild(text);
    list.appendChild(card);
  }

  toggle.addEventListener("click", () => {
    list.hidden = !list.hidden;
    toggle.textContent = `Sources (${sources.length}) ${list.hidden ? "▾" : "▴"}`;
  });

  wrapper.appendChild(toggle);
  wrapper.appendChild(list);
  return wrapper;
}

function addMessage(role, text, sources) {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.appendChild(bubble);

  if (sources && sources.length > 0) {
    row.appendChild(buildSourcesSection(sources));
  }

  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return row;
}

function renderHistory() {
  messagesEl.innerHTML = "";
  if (history.length === 0) {
    addMessage("ai", "Hi! Upload one or more documents on the left, then ask me anything about them.");
    return;
  }
  for (const turn of history) {
    addMessage(turn.role === "assistant" ? "ai" : "user", turn.content);
  }
}

function renderDocuments(documents) {
  docList.innerHTML = "";
  if (documents.length === 0) {
    docList.innerHTML = `<li class="doc-empty">No documents uploaded yet.</li>`;
    return;
  }
  for (const doc of documents) {
    const li = document.createElement("li");
    li.className = "doc-item";

    const info = document.createElement("div");
    info.className = "doc-info";
    const name = document.createElement("span");
    name.className = "doc-name";
    name.textContent = doc.source_name;
    name.title = doc.source_name;
    const meta = document.createElement("span");
    meta.className = "doc-meta";
    meta.textContent = `${doc.chunk_count} chunks`;
    info.appendChild(name);
    info.appendChild(meta);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "doc-delete";
    deleteBtn.type = "button";
    deleteBtn.textContent = "×";
    deleteBtn.title = `Remove ${doc.source_name}`;
    deleteBtn.addEventListener("click", () => deleteDocument(doc.id));

    li.appendChild(info);
    li.appendChild(deleteBtn);
    docList.appendChild(li);
  }
}

async function refreshDocuments() {
  const [docsRes, statusRes] = await Promise.all([fetch("/api/documents"), fetch("/api/status")]);
  const docsData = await docsRes.json();
  const statusData = await statusRes.json();
  renderDocuments(docsData.documents || []);
  statusChunks.textContent = `${statusData.chunkCount ?? 0} chunks`;
  sendBtn.disabled = false;
}

async function deleteDocument(id) {
  try {
    await fetch(`/api/documents/${id}`, { method: "DELETE" });
    await refreshDocuments();
  } catch (err) {
    uploadError.textContent = `Failed to remove document: ${err.message}`;
    uploadError.hidden = false;
  }
}

fileInput.addEventListener("change", () => {
  const files = fileInput.files;
  if (!files || files.length === 0) {
    fileDropLabel.textContent = "Click to choose .txt, .md, or .pdf files";
    fileDrop.classList.remove("has-file");
    uploadBtn.disabled = true;
    return;
  }
  fileDropLabel.textContent =
    files.length === 1 ? files[0].name : `${files.length} files selected`;
  fileDrop.classList.add("has-file");
  uploadBtn.disabled = false;
});

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const files = fileInput.files;
  if (!files || files.length === 0) return;

  uploadError.hidden = true;
  uploadBtn.disabled = true;
  uploadBtn.textContent = "Indexing…";

  try {
    const formData = new FormData();
    for (const file of files) formData.append("documents", file);

    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok && (!data.documents || data.documents.length === 0)) {
      throw new Error(data.errors?.[0]?.error || data.error || "Upload failed.");
    }

    if (data.documents?.length > 0) {
      const names = data.documents.map((d) => d.sourceName).join(", ");
      addMessage("ai", `Indexed ${data.documents.length} document(s): ${names}. Ask away!`);
    }
    if (data.errors?.length > 0) {
      uploadError.textContent = data.errors.map((e) => `${e.sourceName}: ${e.error}`).join(" · ");
      uploadError.hidden = false;
    }

    fileInput.value = "";
    fileDropLabel.textContent = "Click to choose .txt, .md, or .pdf files";
    fileDrop.classList.remove("has-file");
    await refreshDocuments();
  } catch (err) {
    uploadError.textContent = err.message;
    uploadError.hidden = false;
  } finally {
    uploadBtn.textContent = "Upload & Index";
    uploadBtn.disabled = fileInput.files.length === 0;
  }
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  addMessage("user", message);
  chatInput.value = "";
  sendBtn.disabled = true;
  const pendingRow = addMessage("ai pending", "Thinking…");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Chat request failed.");

    pendingRow.remove();
    addMessage("ai", data.reply, data.sources);

    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: data.reply });
    saveHistory(history);
  } catch (err) {
    pendingRow.remove();
    addMessage("ai", `Error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
});

resetBtn.addEventListener("click", () => {
  history = [];
  saveHistory(history);
  renderHistory();
});

renderHistory();
refreshDocuments();
