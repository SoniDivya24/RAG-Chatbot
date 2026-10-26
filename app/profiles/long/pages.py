"""Per-page lines with fonts and positions, and a notion of "running" lines (heads, feet, page numbers).

Running lines are kept on the page (chapter detection reads them) but left out of the body text.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Callable

import pymupdf

from app.profiles.long.repair import repair

_PAGE_NUMBER = re.compile(r"^(\d{1,3}|[ivxl]{1,6})$")  # arabic or roman (front matter)
_EDGE_LINES = 3
_MAX_RUNNING_LINE = 100
_MIN_PAGES_FOR_DETECTION = 6


@dataclass
class Span:
    text: str
    font: str
    size: float
    bold: bool
    bbox: tuple[float, float, float, float]


@dataclass
class Line:
    text: str  # stripped, not yet repaired
    spans: list[Span]

    @property
    def size(self) -> float:  # dominant (largest) size on the line, used for heading detection
        return max(s.size for s in self.spans)

    @property
    def font(self) -> str:
        return max(self.spans, key=lambda s: len(s.text)).font

    @property
    def top(self) -> float:
        return self.spans[0].bbox[1]


@dataclass
class Page:
    page: int  # 1-indexed PDF page (the canonical citation)
    lines: list[Line] = field(default_factory=list)  # all lines, including running heads
    text: str = ""  # cleaned body text (running lines dropped, repaired)


IsRunning = Callable[[Line], bool]


def raw_lines(doc: pymupdf.Document) -> list[list[Line]]:
    pages = []
    for pg in doc:
        lines = []
        for block in pg.get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                spans = [
                    Span(s["text"], s["font"], s["size"], bool(s["flags"] & 16) or "Bold" in s["font"], tuple(s["bbox"]))
                    for s in ln["spans"]
                    if s["text"].strip()
                ]
                text = "".join(s["text"] for s in ln["spans"]).strip()
                if spans and text:
                    lines.append(Line(text=text, spans=spans))
        pages.append(lines)
    return pages


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", text.lower())).strip()


def _modal_size(pages: list[list[Line]]) -> float:
    chars: dict[float, int] = {}
    for lines in pages:
        for line in lines:
            chars[round(line.size, 1)] = chars.get(round(line.size, 1), 0) + len(line.text)
    return max(chars, key=chars.get) if chars else 10.0


# Running heads and feet are set small. A repeating line in larger type is a heading ("Background 1",
# "Background 2" look identical once digits are ignored), and must not be mistaken for furniture.
_MAX_RUNNING_SIZE = 1.15
_MAX_PAGE_NUMBER_SIZE = 1.5


def generic_running(pages: list[list[Line]]) -> IsRunning:
    """Lines that repeat (digits ignored) in the head/foot zone of at least ~5% of pages are page
    furniture, and so are bare page numbers. Works for any document; the reference report uses
    explicit patterns instead (see gep.py) so its text is reproduced exactly."""
    n = len(pages)
    body = _modal_size(pages)
    running: set[str] = set()
    if n >= _MIN_PAGES_FOR_DETECTION:
        threshold = max(3, math.ceil(0.05 * n))
        seen: dict[str, set[int]] = {}
        for index, lines in enumerate(pages):
            for line in lines[:_EDGE_LINES] + lines[-_EDGE_LINES:]:
                if len(line.text) <= _MAX_RUNNING_LINE and line.size <= _MAX_RUNNING_SIZE * body:
                    seen.setdefault(_key(line.text), set()).add(index)
        running = {key for key, where in seen.items() if len(where) >= threshold}
    return lambda line: (bool(_PAGE_NUMBER.match(line.text)) and line.size <= _MAX_PAGE_NUMBER_SIZE * body) or (
        len(line.text) <= _MAX_RUNNING_LINE and line.size <= _MAX_RUNNING_SIZE * body and _key(line.text) in running
    )


def build_pages(raw: list[list[Line]], is_running: IsRunning, th_damaged: bool, min_chars: int = 0) -> list[Page]:
    """Pages with all lines kept; `text` is the repaired body. Pages with fewer than `min_chars`
    cleaned characters get empty text (covers/dividers) but are still returned."""
    pages = []
    for number, lines in enumerate(raw, start=1):
        body = "\n".join(line.text for line in lines if not is_running(line))
        text = repair(body, th_damaged)
        pages.append(Page(page=number, lines=lines, text=text if len(text) >= min_chars else ""))
    return pages
