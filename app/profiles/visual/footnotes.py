"""Superscript markers -> endnotes, and claim chunks that carry their caveat.

A marker is a tiny digit-only span that sits right after (and is much smaller than) the text it
qualifies. Endnote bodies are keyed by a small number span in the left margin of the pages headed
"Endnotes". Claims elsewhere are rendered with inline `[^n]` and the endnote text is attached, so a
retrieved claim always brings its limiting footnote (copper: four-port only; PVC: India/Thailand/
South Korea). A document with no endnote pages simply has no footnote chunks.
"""

import re
from dataclasses import dataclass

import pymupdf

from app.profiles.base import Chunk
from app.profiles.visual.layout import Layout
from app.profiles.visual.repair import repair
from app.profiles.visual.tables import extract_tables

RATIO = 1.2  # a marker is at least this much smaller than the text before it


@dataclass
class Marker:
    page: int
    number: int
    bbox: tuple[float, float, float, float]
    block: int  # index of the containing text block on the page


def _spans(pg):
    """[(block_idx, line_idx, span)] for text spans with non-blank text."""
    out = []
    for bi, b in enumerate(pg.get_text("dict")["blocks"]):
        for li, ln in enumerate(b.get("lines", [])):
            for s in ln["spans"]:
                if s["text"].strip():
                    out.append((bi, li, s))
    return out


def is_marker(s, prev, layout: Layout) -> bool:
    t = s["text"].strip()
    if not (t.isdigit() and len(t) <= 2) or s["size"] >= layout.marker_max:
        return False
    if prev is not None and prev["text"].rstrip().endswith("CO"):
        return False  # CO2e subscript
    near = (
        prev is not None
        and abs(prev["bbox"][2] - s["bbox"][0]) < layout.pts(6)
        and prev["bbox"][1] < s["bbox"][3]
        and prev["bbox"][3] > s["bbox"][1]
    )
    if near:
        return prev["size"] >= s["size"] * RATIO
    return s["size"] < layout.stray_marker_max  # stray marker beside an image (a badge)


def find_markers(doc: pymupdf.Document, layout: Layout, page: int) -> list[Marker]:
    if page in layout.endnote_pages:
        return []
    out, prev = [], None
    for bi, _, s in _spans(doc[page - 1]):
        if is_marker(s, prev, layout):
            out.append(Marker(page, int(s["text"].strip()), tuple(s["bbox"]), bi))
        prev = s
    return out


def parse_endnotes(doc: pymupdf.Document, layout: Layout) -> dict[int, dict]:
    """{number: {"page": int, "text": str}} from the pages headed Endnotes."""
    notes: dict[int, dict] = {}
    y_min, y_max = layout.body_y
    for page in layout.endnote_pages:
        excluded = [pymupdf.Rect(t.bbox) for t in extract_tables(doc, layout, page)]
        spans = [
            s
            for _, _, s in _spans(doc[page - 1])
            if y_min < s["bbox"][1] < y_max
            and s["bbox"][0] >= layout.note_x_min
            and not any(r.contains(pymupdf.Point(s["bbox"][0] + 1, s["bbox"][1] + 1)) for r in excluded)
        ]

        def is_number(s) -> bool:
            return (
                s["text"].strip().isdigit()
                and s["size"] < layout.endnote_number_max
                and s["bbox"][0] <= layout.note_x_max
            )

        starts = sorted((s["bbox"][1], int(s["text"].strip())) for s in spans if is_number(s))
        body: dict[int, list] = {n: [] for _, n in starts}
        for s in spans:
            if is_number(s):
                continue
            # The number is smaller than its text, so its top sits a little below the line's top:
            # up to ~4pt when baseline-aligned, ~5pt tolerated. Notes are 25pt+ apart, so this can't
            # attach a line to the wrong note.
            owner = [n for y, n in starts if y <= s["bbox"][1] + layout.pts(5)]
            if owner:
                body[owner[-1]].append(s)
        for n, ss in body.items():
            ss.sort(key=lambda s: (round(s["bbox"][1]), s["bbox"][0]))
            text, last_y = "", None
            for s in ss:
                t = s["text"].replace("\t", " ")
                if last_y is not None and abs(s["bbox"][1] - last_y) > layout.pts(3):
                    text += "\n" if t.lstrip().startswith("•") else " "
                text += t
                last_y = s["bbox"][1]
            notes[n] = {"page": page, "text": re.sub(r"[^\S\n]+", " ", repair(text)).replace(" \n", "\n").strip()}
    return notes


def render_line(ln, layout: Layout, prev=None):
    """Line text with markers rendered inline as [^n]; also returns the last text span."""
    line = ""
    for s in ln["spans"]:
        if not s["text"].strip():
            line += s["text"]
            continue
        if is_marker(s, prev, layout):
            line += f"[^{int(s['text'].strip())}]" + (" " if s["text"][-1:].isspace() else "")
        else:
            line += s["text"]
        prev = s
    return line.strip(), prev


def join_lines(parts: list[str]) -> str:
    """Join wrapped lines, gluing hyphen breaks (process-/based) without a space."""
    out: list[str] = []
    for line in parts:
        if out and out[-1].endswith("-") and line[:1].islower():
            out[-1] += line
        elif line:
            out.append(line)
    return re.sub(r"\s+", " ", repair(" ".join(out))).strip()


def _block_texts(pg, layout: Layout) -> list[str]:
    """Text per block with markers rendered inline as [^n]."""
    texts = []
    for b in pg.get_text("dict")["blocks"]:
        prev, parts = None, []
        for ln in b.get("lines", []):
            line, prev = render_line(ln, layout, prev)
            parts.append(line)
        texts.append(join_lines(parts))
    return texts


def _sentence(text: str, n: int) -> str:
    """The sentence(s) of a block carrying marker n; markers after a full stop stay with it."""
    cuts, start, out = [], 0, []
    for m in re.finditer(r"[.!?]((?:\[\^\d+\])*)\s+(?=[A-Z0-9])", text):
        cuts.append((start, m.end(1)))
        start = m.end()
    cuts.append((start, len(text)))
    for a, b in cuts:
        if f"[^{n}]" in text[a:b]:
            out.append(text[a:b].strip())
    return " ".join(out)


def inside(bbox, box, pad=2.0) -> bool:
    return box[0] - pad <= bbox[0] and bbox[2] <= box[2] + pad and box[1] - pad <= bbox[1] and bbox[3] <= box[3] + pad


def claims(doc: pymupdf.Document, layout: Layout, exclude: list[tuple[int, tuple]] | None = None) -> list[dict]:
    """[{page, number, claim}] one per (page, marker); claim has inline [^n] markers.

    `exclude` is [(page, bbox)] regions (call-outs) whose markers are already covered elsewhere."""
    out, seen = [], set()
    for page in range(1, len(doc) + 1):
        if page in layout.endnote_pages:
            continue
        texts = _block_texts(doc[page - 1], layout)
        for mk in find_markers(doc, layout, page):
            key = (page, mk.number, mk.block)
            if key in seen or any(p == page and inside(mk.bbox, box) for p, box in (exclude or [])):
                continue
            seen.add(key)
            claim = _sentence(texts[mk.block], mk.number) or texts[mk.block]
            out.append({"page": page, "number": mk.number, "claim": claim})
    return out


def footnote_chunks(
    doc: pymupdf.Document,
    layout: Layout,
    notes: dict[int, dict],
    exclude: list[tuple[int, tuple]] | None = None,
) -> list[Chunk]:
    """Standalone endnote chunks plus one claim chunk per marker (claim text + its endnote)."""
    chunks = []
    for n, nt in sorted(notes.items()):
        chunks.append(
            Chunk(
                text=f"Endnote {n} (p. {nt['page']}): {nt['text']}",
                metadata={"page": nt["page"], "kind": "endnote", "endnote": n},
            )
        )
    for c in claims(doc, layout, exclude):
        note = notes.get(c["number"])
        if not note:
            continue
        chunks.append(
            Chunk(
                text=f"Claim on p. {c['page']}: {c['claim']}\nEndnote {c['number']}: {note['text']}",
                metadata={"page": c["page"], "kind": "footnoted claim", "endnote": c["number"]},
            )
        )
    return chunks
