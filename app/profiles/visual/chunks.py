"""Element-aware chunking: prose chunks plus one chunk per table, call-out, footnoted claim, endnote
and chart - so each kind of fact is stored in a form a retriever can find."""

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.profiles.base import Chunk
from app.profiles.visual.callouts import Callout, all_callouts, callout_chunks
from app.profiles.visual.charts import Describer, chart_chunks
from app.profiles.visual.footnotes import footnote_chunks, inside, join_lines, parse_endnotes, render_line
from app.profiles.visual.layout import Layout
from app.profiles.visual.tables import Table, all_tables

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_PROSE_CHARS = 40  # drops stray diagram labels ("Design and Source")


def _prose_blocks(
    doc: pymupdf.Document, layout: Layout, tables: list[Table], callouts: list[Callout]
) -> list[tuple[int, str, str]]:
    """[(page, section, text)] - body text with tables, call-outs, charts, footers and endnote
    pages removed. Markers stay inline as [^n]; the endnote itself lives in the claim/endnote chunks."""
    out = []
    for pno, pg in enumerate(doc, start=1):
        if pno in layout.endnote_pages:
            continue
        boxes = [t.bbox for t in tables if t.page == pno] + [c.bbox for c in callouts if c.page == pno]
        chart = layout.chart_regions.get(pno)
        title, blocks = [], []
        prev = None
        for b in pg.get_text("dict")["blocks"]:
            parts = []
            for ln in b.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"].strip()]
                text, prev = render_line(ln, layout, prev)
                if not spans or not text:
                    continue
                bb = ln["bbox"]
                if bb[1] >= layout.footer_y or any(inside(bb, box, 1.0) for box in boxes):
                    continue
                if chart and chart[0] <= bb[1] <= chart[1]:
                    continue
                if layout.title_size and abs(max(s["size"] for s in spans) - layout.title_size) < 0.05:
                    title.append(text)
                    continue
                parts.append(text)
            if parts:
                blocks.append(join_lines(parts))
        section = " ".join(title)
        out += [(pno, section, t) for t in blocks]
    return out


def build_chunks(doc: pymupdf.Document, layout: Layout, describe: Describer) -> list[Chunk]:
    tables = all_tables(doc, layout)
    callouts = all_callouts(doc, layout)
    notes = parse_endnotes(doc, layout)

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    by_page: dict[int, tuple[str, list[str]]] = {}
    for page, section, text in _prose_blocks(doc, layout, tables, callouts):
        by_page.setdefault(page, (section, []))[1].append(text)

    chunks: list[Chunk] = []
    for page, (section, texts) in sorted(by_page.items()):
        for text in (t for t in splitter.split_text("\n".join(texts)) if len(t) >= MIN_PROSE_CHARS):
            head = f"Section: {section} (p. {page})\n" if section else f"(p. {page})\n"
            chunks.append(Chunk(text=head + text, metadata={"page": page, "kind": "prose", "section": section or None}))

    chunks += [Chunk(text=t.to_text(), metadata={"page": t.page, "kind": "table"}) for t in tables]
    chunks += callout_chunks(callouts, notes)
    chunks += footnote_chunks(doc, layout, notes, exclude=[(c.page, c.bbox) for c in callouts])
    chunks += chart_chunks(doc, layout, notes, describe)
    return chunks
