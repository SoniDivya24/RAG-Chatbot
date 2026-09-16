import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env.local")

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gemini-3.1-flash-lite")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-001")
PORT = int(os.environ.get("PORT", "8000"))

_ENV_VALUES = {
    "GOOGLE_API_KEY": GOOGLE_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
}


def require(*names: str) -> None:
    """Raise a clear error if any of the named env vars aren't set.

    Checked lazily by whichever feature needs them (Gemini calls need
    GOOGLE_API_KEY, Supabase calls need SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY)
    instead of all at once on startup, since earlier phases don't need every
    key yet.
    """
    missing = [name for name in names if not _ENV_VALUES.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in .env.local."
        )
