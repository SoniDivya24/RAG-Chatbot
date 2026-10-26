"""Group call-outs (big number / headline / headed caption) into single-fact units.

PyMuPDF returns a call-out's number and caption as separate blocks ("100%" ... "of the packaging is
fiber-based"), and side-by-side call-outs can even merge into one block, so we work on lines. A
call-out is anchored on its headline line - a big number or headline (above caption size but not the
page title), a bold column heading, or a bold lead word ending in a full stop ("Gold. We use ...") -
plus the lines beneath it in the same column until the next anchor or a vertical gap.
"""

import re
from dataclasses import dataclass, field

import pymupdf

from app.profiles.base import Chunk
from app.profiles.visual.footnotes import find_markers, join_lines, render_line
from app.profiles.visual.layout import Layout

GAP = 20.0  # max vertical gap between a call-out's lines (reference points)
CONTINUE_GAP = 4.0  # a wrapped heading ("Progress toward" / "our 2030 goal")

_LEAD = re.compile(r"^[A-Z][A-Za-z ]{2,25}\.(\s|$)")
_BOLD = ("semibold", "bold", "heavy", "black")


def _is_bold(font: str) -> bool:
    return any(k in font.lower() for k in _BOLD)


def _is_light(font: str) -> bool:
    return "light" in font.lower()


@dataclass
class Callout:
    page: int
    bbox: tuple[float, float, float, float]
    text: str  # lines joined, markers inline as [^n]
    markers: list[int] = field(default_factory=list)


def _lines(pg, layout: Layout) -> list[dict]:
    out, prev = [], None
    for b in pg.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            spans = [s for s in ln["spans"] if s["text"].strip()]
            if not spans:
                continue
            text, prev = render_line(ln, layout, prev)
            out.append({"bbox": tuple(ln["bbox"]), "text": text, "size": max(s["size"] for s in spans), "first": spans[0]})
    return sorted(out, key=lambda l: (l["bbox"][1], l["bbox"][0]))


def _is_anchor(l, layout: Layout) -> bool:
    f = l["first"]
    if l["bbox"][1] > layout.footer_y:
        return False
    big_low, big_high = layout.big
    if big_low <= l["size"] < big_high and len(l["text"]) < 70 and not _is_light(f["font"]):
        return True
    if abs(l["size"] - layout.heading) < layout.size_tol and _is_bold(f["font"]) and len(l["text"]) < 40:
        return True
    # small-caption call-outs: bold lead word + period ("Gold" and "." can be separate spans)
    return abs(f["size"] - layout.lead) < layout.size_tol and _is_bold(f["font"]) and bool(_LEAD.match(l["text"]))


def _overlaps(a, b) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > 5


def extract_callouts(doc: pymupdf.Document, layout: Layout, page: int) -> list[Callout]:
    lines = _lines(doc[page - 1], layout)
    markers = find_markers(doc, layout, page)
    gap_max, continue_gap = layout.pts(GAP), layout.pts(CONTINUE_GAP)
    used: set[int] = set()
    out = []
    for i, a in enumerate(lines):
        if i in used or not _is_anchor(a, layout):
            continue
        group, box = [i], list(a["bbox"])
        for j in range(i + 1, len(lines)):
            b = lines[j]
            if j in used or b["bbox"][1] < box[1] or b["bbox"][1] > layout.footer_y or not _overlaps(box, b["bbox"]):
                continue
            gap = b["bbox"][1] - box[3]
            if (
                _is_anchor(b, layout)
                and a["size"] >= layout.big[0]
                and abs(b["size"] - layout.heading) < layout.size_tol
                and gap < gap_max
            ):
                pass  # a headline's own link/sub-heading ("Apple Trade In" + "apple.com/recycle")
            elif _is_anchor(b, layout):
                if not (
                    b["size"] == a["size"]
                    and gap < continue_gap
                    and group == [i] + group[1:]
                    and all(_is_anchor(lines[k], layout) for k in group)
                ):
                    continue
            elif gap > gap_max or b["size"] > layout.body_size_max:
                continue
            group.append(j)
            box = [min(box[0], b["bbox"][0]), min(box[1], b["bbox"][1]), max(box[2], b["bbox"][2]), max(box[3], b["bbox"][3])]
        used |= set(group)
        nums = sorted(
            {
                m.number
                for m in markers
                if box[0] - 2 <= m.bbox[0] and m.bbox[2] <= box[2] + 2 and box[1] - 2 <= m.bbox[1] and m.bbox[3] <= box[3] + 2
            }
        )
        out.append(Callout(page, tuple(box), join_lines([lines[k]["text"] for k in group]), nums))
    return out


def all_callouts(doc: pymupdf.Document, layout: Layout) -> list[Callout]:
    return [c for p in range(1, len(doc) + 1) for c in extract_callouts(doc, layout, p)]


def callout_chunks(callouts: list[Callout], notes: dict[int, dict]) -> list[Chunk]:
    """One chunk per call-out; the endnotes its markers point to are appended so caveats travel along."""
    chunks = []
    for c in callouts:
        text = f"Call-out on p. {c.page}: {c.text}"
        for n in c.markers:
            if n in notes:
                text += f"\nEndnote {n}: {notes[n]['text']}"
        chunks.append(Chunk(text=text, metadata={"page": c.page, "kind": "call-out"}))
    return chunks
