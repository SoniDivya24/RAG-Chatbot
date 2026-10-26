"""Hierarchical chunking: split each section into small child chunks (never across a section
boundary) that carry their place in the document, and keep each section whole as a "parent" so the
prompt can later be built from the text around a hit.

Offsets in a chunk's `char_start`/`char_end` index into its parent's flat text. Tables are their own
parents and are never split mid-row: long ones are split by rows and every chunk repeats the
caption + column header, so a row like "South Asia | 6.6 | ..." is always readable.
"""

from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.profiles.base import Chunk
from app.profiles.long.sections import Section

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 20  # drops stray fragments such as lone equation numbers '(1)'
TABLE_CHUNK = 1500  # data rows per table chunk (the header is repeated on top of each)
HEADING_ROW = "[Column headings for the rows below:"  # a mid-table header row (see gep._format_row)

_SEPARATORS = ["\n\n", ". ", "? ", "! ", "; ", " ", ""]


@dataclass
class Exclusions:
    """Sections not worth indexing: reference lists, front-matter boilerplate, publication lists."""

    kinds: set[str] = field(default_factory=lambda: {"references"})
    titles: set[str] = field(default_factory=set)

    def excludes(self, sec: Section) -> bool:
        return (
            sec.kind in self.kinds
            or sec.path[-1] in self.titles
            or (sec.kind == "table" and len(sec.path) > 1 and sec.path[-2] in self.titles)
        )


def _splitter() -> RecursiveCharacterTextSplitter:
    # Text is hard-wrapped; newlines are turned into spaces (same length, offsets preserved)
    # so splits prefer sentence boundaries.
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=_SEPARATORS,
        keep_separator="end",
        add_start_index=True,
    )


def _embed_text(heading_path: str, text: str) -> str:
    """The heading path is embedded with the text (the passage says 'SAR', the heading 'South Asia')."""
    return f"{heading_path}\n\n{text}" if heading_path else text


def _metadata(sec: Section, si: int, page: int, page_end: int) -> dict:
    return {
        "page": page,
        "page_end": page_end,
        "section_index": si,
        "chapter": sec.chapter or 0,
        "chapter_title": sec.chapter_title,
        "region": sec.region or "",
        "kind": sec.kind,
        "heading_path": sec.heading_path,
        "section": sec.heading_path,
    }


def chunk_sections(sections: list[Section], exclusions: Exclusions) -> list[Chunk]:
    splitter = _splitter()
    chunks: list[Chunk] = []
    for si, sec in enumerate(sections):
        if exclusions.excludes(sec):
            continue
        if sec.kind == "table":
            chunks.extend(_table_chunks(sec, si))
            continue
        text, starts, pos = "", [], 0
        for page, seg in sec.segments:
            starts.append((pos, page))
            text += seg + "\n"
            pos += len(seg) + 1
        flat = text.replace("\n", " ")

        def page_at(off: int) -> int:
            return [pg for st, pg in starts if st <= off][-1]

        for doc in splitter.create_documents([flat]):
            start = doc.metadata["start_index"]
            body = doc.page_content.strip()
            if len(body) < MIN_CHUNK_CHARS:
                continue
            meta = _metadata(sec, si, page_at(start), page_at(min(start + len(doc.page_content) - 1, len(flat) - 1)))
            meta.update(char_start=start, char_end=start + len(doc.page_content))
            chunks.append(Chunk(text=body, metadata=meta, embed_text=_embed_text(sec.heading_path, body)))
    return chunks


def _table_chunks(sec: Section, si: int) -> list[Chunk]:
    page = sec.segments[0][0]
    groups, cur, size, heading_row = [], [], 0, None
    for row in sec.text.splitlines():
        if cur and size + len(row) > TABLE_CHUNK:
            if cur[-1] == heading_row:  # never end a chunk on column headings that describe the next rows
                cur.pop()
            groups.append(cur)
            cur, size = [], 0
            if heading_row and row != heading_row:
                # a table can change its column headings part-way down; keep the latest ones on top of
                # every later chunk so its rows are always read under the right years/columns
                cur, size = [heading_row], len(heading_row) + 1
        cur.append(row)
        size += len(row) + 1
        if row.startswith(HEADING_ROW):
            heading_row = row
    groups.append(cur)
    out = []
    for rows in groups:
        text = f"{sec.header}\n" + "\n".join(rows)
        meta = _metadata(sec, si, page, page)
        meta["kind"] = "table"
        out.append(Chunk(text=text, metadata=meta, embed_text=_embed_text(sec.heading_path, text)))
    return out


def build_parents(sections: list[Section], exclusions: Exclusions) -> dict[str, dict]:
    """One record per indexed section holding its full flat text (keyed by section index)."""
    parents = {}
    for si, sec in enumerate(sections):
        if exclusions.excludes(sec):
            continue
        if sec.kind == "table":
            text, pages = f"{sec.header}\n{sec.text}", [[0, sec.segments[0][0]]]
        else:
            text, pages, pos = "", [], 0
            for page, seg in sec.segments:
                pages.append([pos, page])
                text += seg + "\n"
                pos += len(seg) + 1
            text = text.replace("\n", " ")  # same flattening (and offsets) as the chunker
        parents[str(si)] = {"heading_path": sec.heading_path, "kind": sec.kind, "pages": pages, "text": text}
    return parents
