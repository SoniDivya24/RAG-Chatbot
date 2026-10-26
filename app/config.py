import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(dotenv_path=ROOT / ".env.local")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gemini-3.1-flash-lite")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-001")
PORT = int(os.environ.get("PORT", "8000"))

# Everything the app persists (vector index, document registry, embedding
# cache) lives under one local, gitignored folder - there is no database or
# hosted service. Override DATA_DIR (e.g. in tests) to point it elsewhere.
DATA_DIR = Path(os.environ.get("DATA_DIR") or ROOT / "data")

_ENV_VALUES = {
    "GOOGLE_API_KEY": GOOGLE_API_KEY,
}


def require(*names: str) -> None:
    """Raise a clear error if any of the named env vars aren't set.

    Checked lazily by whichever feature needs them (Gemini calls need
    GOOGLE_API_KEY) so importing the app never fails just because a key
    isn't configured yet.
    """
    missing = [name for name in names if not _ENV_VALUES.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in .env.local."
        )
