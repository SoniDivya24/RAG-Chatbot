"""Per-document layout facts, derived from the document itself.

The extractors for tables, footnotes, call-outs and charts all need to know a few things about the
page: where the footer starts, how big the body text is, what a page title looks like, which pages
hold the endnotes, and where a chart sits. The reference report these extractors were first tuned on
(an 8.5pt body, 24pt page titles, endnotes on pp11-12, a chart on p2) expressed them as absolute
numbers. Here every one of them is derived from the document, as a ratio of its body text size, and
the ratios are fitted so that on the reference report the derived values *equal* the original
constants (a test pins this). On another document they scale with its text instead of silently
cutting the wrong lines out.
"""

import collections
import re
from dataclasses import dataclass, field

import pymupdf

# The reference document's modal text size; every absolute threshold below is "its value there"
# times `layout.scale` (= this document's body size / REFERENCE_BODY).
REFERENCE_BODY = 8.5
REFERENCE_PAGE = (612.0, 792.0)

_ENDNOTE_HEADING = re.compile(r"(end|foot)notes?|notes", re.I)
# Chart bars are coloured; table stripes and rules are grey. Saturation separates them.
_MIN_SATURATION = 0.15
_MIN_BAR = (20.0, 10.0)  # width, height of a chart segment worth counting


@dataclass(frozen=True)
class Layout:
    width: float
    height: float
    body: float  # modal text size (by characters)
    title_size: float | None  # the largest size on most pages (page titles), if there is one
    endnote_pages: tuple[int, ...]
    note_x_max: float  # endnote numbers sit left of this x
    note_x_min: float  # endnote bodies start right of this x
    chart_regions: dict[int, tuple[float, float]] = field(default_factory=dict)  # page -> (y0, y1)

    # ---- scale and page geometry ----

    @property
    def scale(self) -> float:
        return self.body / REFERENCE_BODY

    @property
    def footer_y(self) -> float:
        return self.height * 735 / REFERENCE_PAGE[1]

    @property
    def body_y(self) -> tuple[float, float]:
        """Vertical band that holds endnote text (excludes the page title and the footer block)."""
        return self.height * 70 / REFERENCE_PAGE[1], self.height * 700 / REFERENCE_PAGE[1]

    # ---- type scale (ratios of the body size) ----

    @property
    def big(self) -> tuple[float, float]:
        """Headline / big-number sizes: above caption text, below the page title."""
        high = (self.title_size - self.scale) if self.title_size else 27.0 / REFERENCE_BODY * self.body
        return 14.0 / REFERENCE_BODY * self.body, high

    @property
    def heading(self) -> float:
        return 11.0 / REFERENCE_BODY * self.body

    @property
    def lead(self) -> float:
        """Size of a bold lead word in small caption text ("Gold. We use ...")."""
        return 7.5 / REFERENCE_BODY * self.body

    @property
    def body_size_max(self) -> float:
        return 11.5 / REFERENCE_BODY * self.body

    @property
    def marker_max(self) -> float:
        return 8.5 / REFERENCE_BODY * self.body

    @property
    def stray_marker_max(self) -> float:
        return 6.0 / REFERENCE_BODY * self.body

    @property
    def endnote_number_max(self) -> float:
        return 5.5 / REFERENCE_BODY * self.body

    @property
    def size_tol(self) -> float:
        return 0.15 * self.scale

    # ---- distances ----

    def pts(self, reference_points: float) -> float:
        """A distance tuned on the reference document, scaled to this one."""
        return reference_points * self.scale

    def page_fraction_x(self, reference_points: float) -> float:
        return reference_points / REFERENCE_PAGE[0] * self.width


def _modal_body_size(doc: pymupdf.Document) -> float:
    chars: collections.Counter = collections.Counter()
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if span["text"].strip():
                        chars[round(span["size"], 1)] += len(span["text"].strip())
    return chars.most_common(1)[0][0] if chars else REFERENCE_BODY


def _title_size(doc: pymupdf.Document, body: float) -> float | None:
    """The page-title size: the largest text size, if it tops at least half the pages."""
    page_max = []
    for page in doc:
        sizes = [
            span["size"]
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", [])
            for span in line["spans"]
            if span["text"].strip()
        ]
        if sizes:
            page_max.append(round(max(sizes), 1))
    if not page_max:
        return None
    size, count = collections.Counter(page_max).most_common(1)[0]
    return size if count >= len(page_max) / 2 and size >= 1.8 * body else None


def _endnote_geometry(doc: pymupdf.Document, body: float, title: float | None) -> tuple[tuple[int, ...], float, float]:
    """Pages headed "Endnotes"/"Footnotes"/"Notes" and the x-range of their note numbers."""
    pages = []
    for number, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"]).strip()
                size = max((s["size"] for s in line["spans"]), default=0)
                if _ENDNOTE_HEADING.fullmatch(text) and size >= 1.8 * body:
                    pages.append(number)
    pages = tuple(dict.fromkeys(pages))

    xs = []
    for number in pages:
        for block in doc[number - 1].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if (
                        span["text"].strip().isdigit()
                        and span["size"] < 5.5 / REFERENCE_BODY * body
                        and span["bbox"][0] < doc[number - 1].rect.width * 0.5
                    ):
                        xs.append(span["bbox"][0])
    if not xs:
        return pages, 0.0, 0.0
    # Number column: its right edge, and (a little left of its left edge) where note bodies begin.
    return pages, max(xs) + 0.5 * body, min(xs) - 0.45 * body


def _chart_regions(doc: pymupdf.Document, scale: float, footer_y: float) -> dict[int, tuple[float, float]]:
    """Pages with coloured stacked bars, and the vertical band the chart (with its labels) occupies."""
    regions = {}
    for number, page in enumerate(doc, start=1):
        rects = []
        for d in page.get_drawings():
            fill, rect = d.get("fill"), d["rect"]
            if (
                fill
                and max(fill) - min(fill) > _MIN_SATURATION
                and rect.width >= _MIN_BAR[0] * scale
                and rect.height >= _MIN_BAR[1] * scale
            ):
                rects.append((rect, tuple(round(c, 2) for c in fill)))
        stacks: dict[tuple[int, int], list] = collections.defaultdict(list)
        for rect, fill in rects:
            stacks[(round(rect.x0), round(rect.x1))].append((rect, fill))
        # a stacked-bar chart: at least two columns, each stacking three or more differently coloured segments
        columns = [s for s in stacks.values() if len(s) >= 3 and len({f for _, f in s}) >= 2]
        if len(columns) >= 2:
            y0 = min(r.y0 for s in columns for r, _ in s) - 40.0 * scale
            y1 = max(r.y1 for s in columns for r, _ in s) + 54.0 * scale
            regions[number] = (y0, min(y1, footer_y))
    return regions


def derive_layout(doc: pymupdf.Document) -> Layout:
    page = doc[0].rect
    body = _modal_body_size(doc)
    title = _title_size(doc, body)
    pages, note_x_max, note_x_min = _endnote_geometry(doc, body, title)
    scale = body / REFERENCE_BODY
    footer_y = page.height * 735 / REFERENCE_PAGE[1]
    return Layout(
        width=page.width,
        height=page.height,
        body=body,
        title_size=title,
        endnote_pages=pages,
        note_x_max=note_x_max,
        note_x_min=note_x_min,
        chart_regions=_chart_regions(doc, scale, footer_y),
    )
