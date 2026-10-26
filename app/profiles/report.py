import io
import logging
import math
import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError

from app.profiles.base import Chunk, Profile

# pypdf logs a noisy font warning for some CFF fonts; the text is unaffected.
logging.getLogger("pypdf").setLevel(logging.ERROR)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
RETRIEVAL_K = 5
# Cosine-similarity floor measured on the GPO annual report with Gemini
# embeddings: off-topic questions score about 0.57, on-topic ones 0.75-0.82.
MIN_RELEVANCE_SCORE = 0.68
# Pages with less cleaned text than this are covers, dividers or blank pages.
MIN_PAGE_CHARS = 200

REFUSAL = "I could not find this in the document."

# Running heads/feet live in the first and last few lines of a page; a line
# that repeats there across many pages is page furniture, not content.
_EDGE_LINES = 3
_MAX_RUNNING_LINE = 100
_MIN_PAGES_FOR_DETECTION = 6
_BARE_PAGE_NUMBER = re.compile(r"^\d{1,3}$")


@dataclass
class Page:
    page: int  # 1-indexed PDF page: the canonical citation
    text: str


def _line_key(line: str) -> str:
    """Normalise a line so the same running head matches on every page: page
    numbers vary and are sometimes glued to either end ("3U.S. GOVERNMENT ...")."""
    line = re.sub(r"^(?:\d+\s*)+|(?:\s*\d+)+$", "", line.strip())
    key = re.sub(r"\s+", " ", re.sub(r"\d+", "#", line.lower())).strip()
    # A separator left dangling by the removed number ("... report |") would
    # otherwise make two spellings of the same running head look different.
    return key.strip(" |·•-–—:")


def detect_running_lines(pages_lines: list[list[str]]) -> set[str]:
    """Normalised lines that repeat in the head/foot zone of enough pages."""
    n_pages = len(pages_lines)
    if n_pages < _MIN_PAGES_FOR_DETECTION:
        return set()
    threshold = max(3, math.ceil(0.10 * n_pages))
    seen_on: dict[str, set[int]] = {}
    for index, lines in enumerate(pages_lines):
        edge = lines[:_EDGE_LINES] + lines[-_EDGE_LINES:]
        for line in edge:
            if len(line) <= _MAX_RUNNING_LINE and (key := _line_key(line)):
                seen_on.setdefault(key, set()).add(index)
    return {key for key, pages in seen_on.items() if len(pages) >= threshold}


def clean_pages(raw_pages: list[str], min_chars: int = MIN_PAGE_CHARS) -> list[Page]:
    """Cleaned, 1-indexed pages. Running heads/feet and bare page numbers are
    dropped; near-empty pages are dropped too but page numbering is kept."""
    pages_lines = [
        [line.strip() for line in raw.splitlines() if line.strip()] for raw in raw_pages
    ]
    running = detect_running_lines(pages_lines)

    pages = []
    for number, lines in enumerate(pages_lines, start=1):
        kept = [
            line
            for line in lines
            if not _BARE_PAGE_NUMBER.match(line)
            and not (len(line) <= _MAX_RUNNING_LINE and _line_key(line) in running)
        ]
        text = "\n".join(kept)
        if len(text) >= min_chars:
            pages.append(Page(page=number, text=text))
    return pages


class ReportProfile(Profile):
    """Plain-text reports (annual reports and the like): page-aware chunks, so
    every passage - and every answer - can cite the page it came from."""

    id = "report"
    label = "Report"
    description = "Plain-text reports: page-aware answers with page citations."
    extensions = (".pdf",)
    sample_file = "GPO-Anual-report.pdf"
    sample_label = "GPO 2018 Annual Report"
    upload_hint = "PDF reports written in running text, such as an annual report."
    example_questions = (
        "How many depository libraries did GPO staff visit in FY 2018?",
        "What new digital system replaced FDsys, and when was it fully deployed?",
        "How much did GPO procure in printing and information products in FY 2018 on behalf of federal agencies?",
    )

    retrieval_k = RETRIEVAL_K
    min_score = MIN_RELEVANCE_SCORE
    # Factual lookups should be repeatable, and a refusal must be the exact
    # sentence with no sources attached.
    temperature = 0.0
    refusal = REFUSAL
    drop_sources_on_refusal = True

    grounded_instructions = (
        "You answer questions about the uploaded report using ONLY the CONTEXT "
        "passages below, each labelled with its page. Never use outside "
        "knowledge, even for well-known facts. If the passages do not contain "
        "the answer (for example the question is about a year or topic the "
        "report does not cover), reply with exactly: "
        f'"{REFUSAL}" and nothing else. Otherwise answer directly and '
        "concisely, quote figures exactly as written, and cite the page(s) you "
        "used like (p. 5)."
    )

    def __init__(self) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )

    def extract(self, content: bytes, filename: str) -> list[Page]:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs aren't supported yet.")
        try:
            raw = [page.extract_text() or "" for page in reader.pages]
        except FileNotDecryptedError as exc:
            raise ValueError("Password-protected PDFs aren't supported yet.") from exc
        pages = clean_pages(raw)
        if not pages:
            raise ValueError("No readable text found in this PDF - is it a scan?")
        return pages

    def chunk(self, extracted: list[Page]) -> list[Chunk]:
        # Chunks never span pages, so each has exactly one citable page.
        chunks = [
            Chunk(text=text, metadata={"page": page.page})
            for page in extracted
            for text in self.splitter.split_text(page.text)
        ]
        if not chunks:
            raise ValueError("Document produced no usable text - is the file empty?")
        return chunks

    def format_context(self, hits: list[dict]) -> str:
        return "\n\n".join(f"[p. {hit['metadata'].get('page', '?')}] {hit['text']}" for hit in hits)
