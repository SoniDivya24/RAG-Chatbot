from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import config
from app.chat_session import ChatSession
from app.rag_engine import RagEngine
from app.text_extract import extract_text

# Only GOOGLE_API_KEY is required this early — Supabase-backed routes validate
# their own required keys lazily when first used.
config.require("GOOGLE_API_KEY")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

MAX_FILES_PER_UPLOAD = 5
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_TURNS = 40

rag_engine = RagEngine()
chat_session = ChatSession(rag_engine)

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


@app.get("/api/status")
async def status() -> dict:
    return {
        "status": "ok",
        "chatModel": config.CHAT_MODEL,
        "documentCount": len(rag_engine.list_documents()),
        "chunkCount": rag_engine.count_chunks(),
    }


@app.get("/api/documents")
async def list_documents() -> dict:
    return {"documents": rag_engine.list_documents()}


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str) -> dict:
    rag_engine.delete_document(document_id)
    return {"ok": True}


@app.post("/api/upload")
@limiter.limit("10/minute")
async def upload(request: Request, documents: list[UploadFile] = File(...)) -> JSONResponse:
    if len(documents) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400, detail=f"Upload at most {MAX_FILES_PER_UPLOAD} files at a time."
        )

    loaded = []
    errors = []
    for file in documents:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(
                {"sourceName": file.filename, "error": "Only .txt, .md, or .pdf files are supported"}
            )
            continue

        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            errors.append({"sourceName": file.filename, "error": "File too large (max 4MB)"})
            continue

        try:
            text = extract_text(content, file.filename)
            doc = rag_engine.load_document(text, file.filename)
            loaded.append(
                {"id": doc["id"], "sourceName": doc["source_name"], "chunkCount": doc["chunk_count"]}
            )
        except Exception as exc:
            errors.append({"sourceName": file.filename, "error": str(exc)})

    status_code = 200 if loaded else 400
    return JSONResponse(status_code=status_code, content={"documents": loaded, "errors": errors})


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
    return chat_session.ask(message, history)


# Registered last so explicit API routes above take priority over the static mount.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
