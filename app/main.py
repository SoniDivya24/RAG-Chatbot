from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import config
from app.modes import ModeUnavailable, Modes, UnknownMode
from app.rag_engine import RagEngine

# GOOGLE_API_KEY is the only credential the app needs: the index, the document
# registry and the embedding cache are all local files under data/.
config.require("GOOGLE_API_KEY")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

MAX_FILES_PER_UPLOAD = 5
MAX_UPLOAD_MB = 25  # local-only app: the reference PDFs are 4-7 MB
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_TURNS = 40

# One library (store + engine + chat session) per mode, created on first use.
modes = Modes()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="RAG Chatbot")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Keep stack traces out of responses; the real error still hits server logs.
    print(f"Unhandled error: {exc!r}")
    return JSONResponse(status_code=500, content={"error": "Something went wrong."})


def _engine(mode: str | None) -> RagEngine:
    """The engine for a mode; no/unknown/unavailable mode becomes a clear API error."""
    try:
        return modes.engine(mode)
    except UnknownMode as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ModeUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc))


def _extensions_message(extensions: tuple[str, ...]) -> str:
    if len(extensions) == 1:
        return f"Only {extensions[0]} files are supported"
    return f"Only {', '.join(extensions[:-1])}, or {extensions[-1]} files are supported"


def _sanitize_history(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    sanitized = []
    for turn in raw[-MAX_HISTORY_TURNS:]:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        content = turn.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        sanitized.append({"role": role, "content": content[:MAX_MESSAGE_LENGTH]})
    return sanitized


@app.get("/api/modes")
async def list_modes() -> dict:
    """Every mode the app offers, for the UI's mode switch. Scenario modes that
    aren't implemented yet are listed with available=false."""
    return {"modes": modes.describe()}


@app.get("/api/status")
async def status(mode: str | None = None) -> dict:
    engine = _engine(mode)
    return {
        "status": "ok",
        "chatModel": config.CHAT_MODEL,
        "storage": "local",
        "mode": engine.profile.id,
        "documentCount": len(engine.list_documents()),
        "chunkCount": engine.count_chunks(),
    }


@app.get("/api/documents")
async def list_documents(mode: str | None = None) -> dict:
    return {"documents": _engine(mode).list_documents()}


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str, mode: str | None = None) -> dict:
    _engine(mode).delete_document(document_id)
    return {"ok": True}


@app.post("/api/upload")
@limiter.limit("10/minute")
async def upload(
    request: Request, documents: list[UploadFile] = File(...), mode: str | None = None
) -> JSONResponse:
    engine = _engine(mode)
    allowed = engine.profile.extensions
    if len(documents) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400, detail=f"Upload at most {MAX_FILES_PER_UPLOAD} files at a time."
        )

    loaded = []
    errors = []
    for file in documents:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in allowed:
            errors.append({"sourceName": file.filename, "error": _extensions_message(allowed)})
            continue

        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            errors.append(
                {"sourceName": file.filename, "error": f"File too large (max {MAX_UPLOAD_MB}MB)"}
            )
            continue

        try:
            doc = engine.load_file(content, file.filename)
            loaded.append(
                {
                    "id": doc["id"],
                    "sourceName": doc["source_name"],
                    "chunkCount": doc["chunk_count"],
                    "duplicate": doc.get("duplicate", False),
                }
            )
        except Exception as exc:
            errors.append({"sourceName": file.filename, "error": str(exc)})

    status_code = 200 if loaded else 400
    return JSONResponse(status_code=status_code, content={"documents": loaded, "errors": errors})


@app.post("/api/sample")
@limiter.limit("10/minute")
async def load_sample(request: Request, mode: str | None = None) -> JSONResponse:
    """Index the mode's built-in sample document (same response shape as /api/upload)."""
    engine = _engine(mode)
    profile = engine.profile
    if not profile.sample_file:
        raise HTTPException(status_code=404, detail=f"The {profile.label} mode has no sample document.")
    path = config.SAMPLES_DIR / profile.sample_file  # a name fixed by the profile, not by the caller
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"The sample file {profile.sample_file} isn't in the samples/ folder - copy it there (see the README).",
        )
    try:
        doc = engine.load_file(path.read_bytes(), path.name)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"documents": [], "errors": [{"sourceName": path.name, "error": str(exc)}]})
    loaded = {
        "id": doc["id"],
        "sourceName": doc["source_name"],
        "chunkCount": doc["chunk_count"],
        "duplicate": doc.get("duplicate", False),
    }
    return JSONResponse(content={"documents": [loaded], "errors": []})


@app.post("/api/chat")
@limiter.limit("20/minute")
async def chat(request: Request) -> dict:
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail="Message is too long.")

    history = _sanitize_history(body.get("history"))
    # Resolve the mode first so a bad/unavailable mode fails before any model call.
    mode = body.get("mode") if isinstance(body.get("mode"), str) else None
    _engine(mode)
    return modes.chat(mode).ask(message, history)


# Registered last so explicit API routes above take priority over the static mount.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
