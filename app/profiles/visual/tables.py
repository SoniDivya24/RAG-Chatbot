"""Rebuild a document's tables from geometry and emit self-describing text.

Tables here are drawn as dark header bars (filled rectangles) over words that PyMuPDF returns in
reading order with no row/column link. We find each table from its header bars, take the column edges
from the bars, bound the body with the last horizontal rule, assign words to rows (by y) and columns
(by x), then write every cell with its row label and column header.
"""

from dataclasses import dataclass, field

import pymupdf

from app.profiles.visual.layout import Layout

DARK = 0.5  # header bars are filled ~0.235 grey; body stripes are ~0.936
ROW_TOL = 3.0  # words whose vertical centres differ by less than this share a row (reference points)
MIN_BAR_WIDTH = 80  # glyph-like dark shapes (icons, logos) are narrower (reference points at 612pt)
RULE_MIN_WIDTH = 200  # horizontal rules (zero-height rects) that close a table (reference points at 612pt)
NOTE_WINDOW = 40.0  # a "Note:" line within this distance below a table belongs to it


@dataclass
class Table:
    page: int
    bbox: tuple[float, float, float, float]
    title: str  # words in header cells that span several columns ("Power consumption for iMac")
    headers: list[str]  # one per column; headers[0] labels the row-label column
    rows: list[dict] = field(default_factory=list)  # {"label", "cells": [...], "bullet": bool}
    note: str = ""

    def to_text(self) -> str:
        """Self-describing text: every value is stated with its row label and column header."""
        head = f"Table on p. {self.page}: {self.title or self.headers[0]}"
        lines = []
        if len(self.headers) == 2:
            lines.append(f"{head} - {self.headers[1]}.")
            parent = ""
            for r in self.rows:
                val = r["cells"][0]
                if r["bullet"]:
                    lines.append(f"- {r['label']}: {val} (share of {parent})")
                else:
                    parent = r["label"]
                    lines.append(f"- {r['label']}: {val}" if val else f"- {r['label']}")
        else:
            lines.append(f"{head} (columns: {', '.join(self.headers[1:])}).")
            for r in self.rows:
                lines.append(f"- {r['label']}: " + "; ".join(f"{h} = {c}" for h, c in zip(self.headers[1:], r["cells"])))
        if self.note:
            lines.append(self.note)
        return "\n".join(lines)


def _dark_bars(pg: pymupdf.Page, layout: Layout) -> list[pymupdf.Rect]:
    min_width = layout.page_fraction_x(MIN_BAR_WIDTH)
    out = []
    for d in pg.get_drawings():
        f, r = d.get("fill"), d["rect"]
        if f and max(f) < DARK and min_width <= r.width < pg.rect.width * 0.9 and r.height > layout.pts(2):
            out.append(r)
    return out


def _cluster_bars(bars: list[pymupdf.Rect], tol: float) -> list[list[pymupdf.Rect]]:
    """Bars that touch vertically belong to one table header."""
    groups: list[list[pymupdf.Rect]] = []
    for r in sorted(bars, key=lambda r: (r.y0, r.x0)):
        for g in groups:
            if r.y0 <= max(b.y1 for b in g) + tol:
                g.append(r)
                break
        else:
            groups.append([r])
    return groups


def _center(w) -> tuple[float, float]:
    return (w[0] + w[2]) / 2, (w[1] + w[3]) / 2


def _join(words, tol: float) -> str:
    return " ".join(w[4] for w in sorted(words, key=lambda w: (round(_center(w)[1] / tol), w[0])))


def _note_below(words, bottom: float, edges: tuple[float, float], layout: Layout) -> str:
    """A line starting "Note:" just under the table (e.g. "Percentages may not total 100")."""
    tol = layout.pts(ROW_TOL)
    near = [w for w in words if bottom < _center(w)[1] <= bottom + layout.pts(NOTE_WINDOW) and edges[0] - 2 <= _center(w)[0]]
    rows: list[list] = []
    for w in sorted(near, key=lambda w: (_center(w)[1], w[0])):
        if rows and abs(_center(w)[1] - rows[-1][0]) < tol:
            rows[-1][1].append(w)
        else:
            rows.append([_center(w)[1], [w]])
    for _, ws in rows:
        text = " ".join(w[4] for w in sorted(ws, key=lambda w: w[0]))
        if text.startswith("Note:"):
            return text
    return ""


def extract_tables(doc: pymupdf.Document, layout: Layout, page: int) -> list[Table]:
    pg = doc[page - 1]
    words = pg.get_text("words")
    tol = layout.pts(ROW_TOL)
    rules = [
        d["rect"]
        for d in pg.get_drawings()
        if d["rect"].height < layout.pts(1) and d["rect"].width >= layout.page_fraction_x(RULE_MIN_WIDTH)
    ]
    groups = _cluster_bars(_dark_bars(pg, layout), layout.pts(1))
    tables = []
    for gi, g in enumerate(groups):
        top, hb = min(b.y0 for b in g), max(b.y1 for b in g)
        next_top = groups[gi + 1][0].y0 if gi + 1 < len(groups) else float("inf")
        bottom = max((r.y0 for r in rules if hb <= r.y0 < next_top), default=hb)
        edges = sorted({round(b.x0, 1) for b in g} | {round(b.x1, 1) for b in g})
        cols = list(zip(edges, edges[1:]))
        # per column, the header bar that reaches lowest holds its label; words in other bars are the title
        label_bars = []
        for x0, x1 in cols:
            cx = (x0 + x1) / 2
            label_bars.append(max((b for b in g if b.x0 <= cx <= b.x1), key=lambda b: b.y1))
        hdr_words = [w for w in words if top <= _center(w)[1] <= hb and edges[0] <= _center(w)[0] <= edges[-1]]
        headers, used = [], set()
        for bar in label_bars:
            ws = [w for w in hdr_words if bar.x0 <= _center(w)[0] <= bar.x1 and bar.y0 <= _center(w)[1] <= bar.y1]
            used |= {id(w) for w in ws}
            headers.append(_join(ws, tol))
        title = _join([w for w in hdr_words if id(w) not in used], tol)
        body = [w for w in words if hb <= _center(w)[1] <= bottom + layout.pts(1) and edges[0] <= _center(w)[0] <= edges[-1]]
        rows: list[list] = []
        for w in sorted(body, key=lambda w: _center(w)[1]):
            if rows and abs(_center(w)[1] - rows[-1][0]) < tol:
                rows[-1][1].append(w)
            else:
                rows.append([_center(w)[1], [w]])
        t = Table(page, (edges[0], top, edges[-1], bottom), title, headers)
        for _, ws in rows:
            cells = [_join([w for w in ws if x0 <= _center(w)[0] < x1], tol) for x0, x1 in cols]
            label = cells[0]
            bullet = label.startswith("•")
            t.rows.append({"label": label.lstrip("• ").strip(), "cells": cells[1:], "bullet": bullet})
        t.note = _note_below(words, bottom, (edges[0], edges[-1]), layout)
        tables.append(t)
    return tables


def all_tables(doc: pymupdf.Document, layout: Layout) -> list[Table]:
    return [t for p in range(1, len(doc) + 1) for t in extract_tables(doc, layout, p)]
