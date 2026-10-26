import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """One searchable unit produced by a profile.

    `text` is what is stored, shown as a source and sent to the model.
    `embed_text`, when set, is what gets embedded instead (e.g. a heading path
    prepended to the text) so retrieval can use context the stored text lacks.
    `metadata` carries whatever the profile knows about where the chunk came
    from - page, section / heading path, element kind, parent id. Values must
    be str / int / float / bool (None entries are dropped by the store).
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embed_text: str | None = None


class Profile(ABC):
    """A document pipeline: how an upload is read and chunked for one mode, and
    how retrieved chunks are turned into context and sources for the answer.

    Each mode of the app (Standard, Report, Long document, Visual document) is
    one Profile. The engine, store and chat session are generic; everything
    document-specific lives here.
    """

    id: str
    label: str
    description: str
    extensions: tuple[str, ...] = (".txt", ".md", ".pdf")
    available: bool = True

    # Shown by the UI for this mode: what to upload, and questions worth trying.
    upload_hint: str = ""
    example_questions: tuple[str, ...] = ()
    # A built-in sample document for this mode: a file name inside the samples folder (never a path
    # from a request) and a human label. None means the mode has no sample.
    sample_file: str | None = None
    sample_label: str = ""

    retrieval_k: int = 5
    # Chunks scoring below this cosine similarity are noise, not real matches.
    min_score: float = 0.62

    # How the model answers: creativity, and the exact sentence it uses when the
    # documents don't contain the answer.
    temperature: float = 0.7
    refusal: str = "I don't have that information in the documents."
    # Show no sources for an answer that is a refusal (they didn't inform it).
    drop_sources_on_refusal: bool = False

    # System-prompt text used when relevant chunks were found; the chat session
    # appends the formatted context after it.
    grounded_instructions: str = ""

    @abstractmethod
    def extract(self, content: bytes, filename: str) -> Any:
        """Read an uploaded file into whatever structure `chunk` consumes."""

    @abstractmethod
    def chunk(self, extracted: Any) -> list[Chunk]:
        """Turn the extracted document into chunks (raise ValueError if none)."""

    def sidecars(self, extracted: Any) -> dict[str, Any]:
        """Extra per-document data to store next to the chunks (JSON-able), e.g. the parent
        sections a mode assembles its context from. Deleted with the document."""
        return {}

    def query_filter(self, question: str, store: Any) -> tuple[dict | None, list[str]]:
        """A metadata filter for this question (and notes on why), or (None, [])."""
        return None, []

    def precheck(self, question: str, store: Any) -> str | None:
        """A canned reply for questions that can be answered without the model (e.g. "Chapter 7"
        when the document has four chapters), else None."""
        return None

    def build_context(self, hits: list[dict], store: Any) -> tuple[str, list[dict]]:
        """(the CONTEXT text sent to the model, the sources shown to the user) for retrieved hits."""
        return self.format_context(hits), [self.source_payload(hit) for hit in hits]

    def fingerprint(self, content: bytes, extracted: Any) -> str:
        """Identity of a document for duplicate detection."""
        return hashlib.sha256(content).hexdigest()

    def format_context(self, hits: list[dict]) -> str:
        """The CONTEXT block sent to the model for the retrieved chunks."""
        return "\n\n".join(hit["text"] for hit in hits)

    def source_payload(self, hit: dict) -> dict:
        """What the UI receives for one retrieved chunk. Always the text, the
        score and the source file; plus page / section / kind when known."""
        meta = hit["metadata"]
        payload = {"text": hit["text"], "score": hit["score"], "source": meta.get("source")}
        for key in ("page", "section", "kind"):
            if meta.get(key) not in (None, ""):
                payload[key] = meta[key]
        return payload


class UnavailableProfile(Profile):
    """A mode that is registered (so it shows up in the UI's mode list) but not
    implemented yet. Using it is a clear error, never a silent fallback to a
    different pipeline."""

    available = False

    def __init__(
        self,
        id: str,
        label: str,
        description: str,
        upload_hint: str = "",
        example_questions: tuple[str, ...] = (),
    ) -> None:
        self.id = id
        self.label = label
        self.description = description
        self.upload_hint = upload_hint
        self.example_questions = example_questions

    def _unavailable(self) -> ValueError:
        return ValueError(f"The {self.label} mode isn't available yet.")

    def extract(self, content: bytes, filename: str) -> Any:
        raise self._unavailable()

    def chunk(self, extracted: Any) -> list[Chunk]:
        raise self._unavailable()
