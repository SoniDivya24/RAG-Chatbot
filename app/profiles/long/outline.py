"""A generic outline for long PDFs that aren't the reference report: headings are found from the
document's own type scale (larger or bold short lines, ranked by size) and become a heading path
for every passage. Best-effort - it knows nothing about tables, boxes or regions."""

import collections
import re

from app.profiles.long.pages import IsRunning, Line, Page
from app.profiles.long.query import Vocabulary
from app.profiles.long.sections import Section

_MAX_HEADING = 90
_MAX_LEVELS = 3
_WRAP_GAP = 22.0  # a heading wrapped onto a second line sits at most this far below the first
_CHAPTER = re.compile(r"^(chapter|part)\s+(\d+)\b", re.I)
_REFERENCES = re.compile(r"^(references|bibliography|works cited)\b", re.I)


def _style(line: Line) -> tuple[float, bool]:
    return round(line.size, 1), line.spans[0].bold


def _body_size(pages: list[Page], is_running: IsRunning) -> float:
    chars: collections.Counter = collections.Counter()
    for page in pages:
        for line in page.lines:
            if not is_running(line):
                chars[round(line.size, 1)] += len(line.text)
    return chars.most_common(1)[0][0] if chars else 10.0


def _is_candidate(line: Line, body: float) -> bool:
    text = line.text
    if len(text) > _MAX_HEADING or len(text) < 3 or not re.search(r"[A-Za-z]", text):
        return False
    if text.endswith((".", ",", ";", ":")) and not _CHAPTER.match(text):
        return False
    size, bold = _style(line)
    return size >= 1.12 * body or (bold and size >= 0.95 * body and len(text) <= 70)


def _heading_levels(pages: list[Page], is_running: IsRunning, body: float) -> dict[tuple[float, bool], int]:
    counts: collections.Counter = collections.Counter()
    for page in pages:
        for line in page.lines:
            if not is_running(line) and _is_candidate(line, body):
                counts[_style(line)] += 1
    # a heading style recurs (at least twice) but is not the document's bulk: bold emphasis, table
    # cells and the like would otherwise outnumber real headings
    total_lines = sum(len(p.lines) for p in pages) or 1
    usable = [s for s, c in counts.items() if 2 <= c <= 0.2 * total_lines]
    usable.sort(key=lambda s: (-s[0], not s[1]))
    return {style: level for level, style in enumerate(usable[:_MAX_LEVELS], start=1)}


def build_generic_sections(pages: list[Page], is_running: IsRunning, title: str = "Document") -> list[Section]:
    body = _body_size(pages, is_running)
    levels = _heading_levels(pages, is_running, body)

    if not levels:  # no recognisable headings: one section per page, cited by page
        return [
            Section(None, title, None, "body", (title, f"Page {p.page}"), [(p.page, p.text)])
            for p in pages
            if p.text.strip()
        ]

    sections: list[Section] = []
    stack: dict[int, str] = {}
    chapter: int | None = None
    chapter_title = title
    current: Section | None = None
    last_heading: tuple[int, tuple[float, bool], float, int] | None = None  # level, style, top, page

    def path() -> tuple[str, ...]:
        return tuple(stack[k] for k in sorted(stack)) or (title,)

    def kind() -> str:
        return "references" if stack.get(1) and _REFERENCES.match(stack[1]) else "body"

    for page in pages:
        last_heading = None if last_heading and last_heading[3] != page.page else last_heading
        for line in page.lines:
            if is_running(line):
                continue
            level = levels.get(_style(line)) if _is_candidate(line, body) else None
            if level is not None:
                text = line.text
                if last_heading and last_heading[0] == level and last_heading[1] == _style(line) and 0 < line.top - last_heading[2] <= _WRAP_GAP:
                    # a wrapped heading: extend the previous one
                    stack[level] = f"{stack[level]} {text}"
                    if current is not None and not current.segments:
                        current.path = path()
                    last_heading = (level, _style(line), line.top, page.page)
                    continue
                stack[level] = text
                for deeper in [k for k in stack if k > level]:
                    del stack[deeper]
                m = _CHAPTER.match(text) if level == 1 else None
                if m:
                    chapter, chapter_title = int(m.group(2)), text
                current = Section(chapter, chapter_title, None, kind(), path(), [])
                sections.append(current)
                last_heading = (level, _style(line), line.top, page.page)
                continue
            last_heading = None
            if current is None:
                current = Section(chapter, chapter_title, None, kind(), path(), [])
                sections.append(current)
            if not current.segments or current.segments[-1][0] != page.page:
                current.segments.append((page.page, ""))
            current.segments[-1] = (page.page, current.segments[-1][1] + line.text + "\n")

    return [s for s in sections if any(t.strip() for _, t in s.segments)]


def generic_vocabulary(sections: list[Section]) -> Vocabulary:
    vocab = Vocabulary()
    for s in sections:
        if s.chapter:
            vocab.chapters.setdefault(s.chapter, s.chapter_title)
        for i, name in enumerate(s.path):
            if name.strip().lower() == "executive summary":
                vocab.named_sections.setdefault("executive summary", " > ".join(s.path[: i + 1]))
    return vocab
