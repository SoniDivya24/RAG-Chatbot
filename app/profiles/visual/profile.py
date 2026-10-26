from dataclasses import dataclass

import pymupdf

from app.profiles.base import Chunk, Profile
from app.profiles.visual.charts import Describer, gemini_describer
from app.profiles.visual.chunks import build_chunks
from app.profiles.visual.layout import Layout, derive_layout

REFUSAL = "I could not find this in the document."
RETRIEVAL_K = 5
# Cosine-similarity floor shared with the other document modes (off-topic ~0.57, on-topic ~0.75-0.82).
MIN_RELEVANCE_SCORE = 0.68


@dataclass
class VisualSource:
    """An opened-for-validation upload plus the layout derived from it."""

    content: bytes
    layout: Layout
    n_pages: int


class VisualProfile(Profile):
    """Documents whose facts live in tables, charts, footnotes and call-outs rather than in running
    text. Each kind of element becomes its own chunk, footnotes travel with the claims they limit,
    and charts are described by a vision model (cached)."""

    id = "visual"
    label = "Visual document"
    description = "Documents whose facts live in tables, charts and footnotes."
    extensions = (".pdf",)
    upload_hint = "Short PDFs whose facts sit in tables, charts and footnotes."
    example_questions = (
        "How much less energy does iMac use compared to the ENERGY STAR requirement?",
        "What is the total carbon footprint of the iMac, and how much of that comes from product use versus manufacturing?",
        "What material is the iMac stand made from, and what percentage of it is recycled?",
    )

    retrieval_k = RETRIEVAL_K
    min_score = MIN_RELEVANCE_SCORE
    temperature = 0.0
    refusal = REFUSAL
    drop_sources_on_refusal = True

    grounded_instructions = (
        "You answer questions about the uploaded document using ONLY the CONTEXT passages below, each "
        "labelled with its page and the kind of element it came from (prose, table, call-out, chart, "
        "footnoted claim, endnote). Never use outside knowledge, even for well-known facts. If the "
        "passages do not contain the answer, reply with exactly: "
        f'"{REFUSAL}" and nothing else. Otherwise answer directly and concisely, quoting figures '
        "exactly as written with their units and the configuration printed next to the figure, add "
        'an endnote only when it limits or conditions the claim (e.g. "only", "except", a '
        "verification standard) - not for background or test-setup detail the question did not ask "
        "about - label any number you compute yourself as computed, and cite the page(s) you used "
        "like (p. 10)."
    )

    def __init__(self, describe: Describer | None = None) -> None:
        # Injectable so tests never call a vision model; the app uses the cached Gemini describer.
        self._describe = describe or gemini_describer

    def extract(self, content: bytes, filename: str) -> VisualSource:
        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise ValueError("That doesn't look like a readable PDF.") from exc
        with doc:
            if doc.needs_pass:
                raise ValueError("Password-protected PDFs aren't supported yet.")
            if not any(page.get_text().strip() for page in doc):
                raise ValueError("No readable text found in this PDF - is it a scan?")
            return VisualSource(content=content, layout=derive_layout(doc), n_pages=len(doc))

    def chunk(self, extracted: VisualSource) -> list[Chunk]:
        with pymupdf.open(stream=extracted.content, filetype="pdf") as doc:
            chunks = build_chunks(doc, extracted.layout, self._describe)
        if not chunks:
            raise ValueError("Document produced no usable text - is the file empty?")
        return chunks

    def format_context(self, hits: list[dict]) -> str:
        return "\n\n".join(
            f"[p. {hit['metadata'].get('page', '?')} | {hit['metadata'].get('kind', 'text')}] {hit['text']}"
            for hit in hits
        )
