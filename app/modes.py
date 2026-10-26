import threading
from pathlib import Path

from app import config
from app.chat_session import ChatSession
from app.embeddings import CachedEmbedder
from app.profiles import DEFAULT_MODE, Profile, default_profiles
from app.rag_engine import RagEngine
from app.vector_store import LocalVectorStore


class UnknownMode(ValueError):
    """The requested mode id isn't registered."""


class ModeUnavailable(ValueError):
    """The mode exists but its pipeline isn't implemented yet."""


class Modes:
    """The app's modes: one profile each, and for every available mode its own
    library - a separate store (Chroma + document registry) under
    `data/modes/<mode>/`, so a document uploaded in one mode can never show up
    in another, and each mode can be reset independently. The embedding cache
    is shared (its keys are model + text, so sharing is safe and saves calls).
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        embedder: CachedEmbedder | None = None,
        profiles: dict[str, Profile] | None = None,
    ) -> None:
        self.data_dir = Path(data_dir or config.DATA_DIR)
        self.embedder = embedder or CachedEmbedder(self.data_dir / "embedding_cache.sqlite")
        self.profiles = profiles if profiles is not None else default_profiles()
        self._engines: dict[str, RagEngine] = {}
        self._chats: dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def resolve(self, mode: str | None) -> Profile:
        """The profile for a mode id (None means the default mode)."""
        mode = mode or DEFAULT_MODE
        profile = self.profiles.get(mode)
        if profile is None:
            raise UnknownMode(f'Unknown mode "{mode}".')
        if not profile.available:
            raise ModeUnavailable(f"The {profile.label} mode isn't available yet.")
        return profile

    def engine(self, mode: str | None) -> RagEngine:
        profile = self.resolve(mode)
        with self._lock:
            if profile.id not in self._engines:
                store = LocalVectorStore(self.data_dir / "modes" / profile.id)
                self._engines[profile.id] = RagEngine(profile, store, self.embedder)
            return self._engines[profile.id]

    def chat(self, mode: str | None) -> ChatSession:
        engine = self.engine(mode)
        with self._lock:
            if engine.profile.id not in self._chats:
                self._chats[engine.profile.id] = ChatSession(engine)
            return self._chats[engine.profile.id]

    def describe(self) -> list[dict]:
        """Every registered mode, for the UI's mode switch."""
        modes = []
        for profile in self.profiles.values():
            info = {
                "id": profile.id,
                "label": profile.label,
                "description": profile.description,
                "available": profile.available,
                "extensions": list(profile.extensions),
            }
            if profile.available:
                info["documentCount"] = len(self.engine(profile.id).list_documents())
            modes.append(info)
        return modes
