"""Structure recovery tuned to the World Bank "Global Economic Prospects" report (June 2026).

Recovers chapter > section/region/box > sub-section from fonts. This is a *preset* for the reference
report: the font names and sizes, the chapter and region lists and the front-matter page map below
are that document's. Other long PDFs use the generic outline in outline.py.

Headings in the GEP: HelveticaLTStd-Bold 16 (section / region / annex), Bold 14 (sub-heading on the
Regional-developments pages), Roman 11 (sub-section), Bold 10 "BOX n.n title" (box header repeated
with "(continued)" on every box page). The running head carries "CHAPTER n"; the Statistical
Appendix has its own running head. Front matter is mapped by page (see FRONT).
"""
import re

from app.profiles.long.pages import IsRunning, Line, Page
from app.profiles.long.repair import repair
from app.profiles.long.sections import Section

# Running head ("CHAPTER 2 / GLOBAL ECONOMIC PROSPECTS | JUNE 2026 / 74") and bare page numbers.
_RUNNING = [
    re.compile(r"^GLOBAL ECONOMIC PROSPECTS \| JUNE 2026$"),
    re.compile(r"^CHAPTER \d$"),
    re.compile(r"^STATISTICAL APPENDIX$"),  # running head on appendix pages
    re.compile(r"^(\d{1,3}|[ivxl]{1,6})$"),  # arabic or roman (front matter) page numbers
]


def is_running(line: Line) -> bool:
    return any(p.match(line.text) for p in _RUNNING)


def is_gep(first_pages_text: str) -> bool:
    """Is this the reference report? (Its cover and copyright pages say so.)"""
    return "global economic prospects" in first_pages_text.lower()

CHAPTERS = {
    1: "Global Outlook",
    2: "Regional Outlooks",
    3: "A Rising Challenge: Sovereign Debt Levels and Interest Rates in EMDEs",
    4: "Navigating Volatility: Fiscal Policy and Commodity Price Swings",
}
APPENDIX = "Statistical Appendix"
FRONT_MATTER = "Front Matter"
# (first PDF page, section) - from the printed contents (roman page xiii = PDF p15).
FRONT = [(1, "Cover"), (6, "Copyright"), (7, "Contents"), (15, "Acknowledgments"), (17, "Foreword"),
         (19, "Executive Summary"), (21, "Abbreviations")]
REGIONS = [
    "East Asia and Pacific", "Europe and Central Asia", "Latin America and the Caribbean",
    "Middle East, North Africa, Afghanistan, and Pakistan", "South Asia", "Sub-Saharan Africa",
]
# Chapter 2 opens with a regional overview whose own title page carries no extractable text.
SEED_SECTION = {2: "Regional developments"}

_CHAPTER_RE = re.compile(r"^CHAPTER (\d)$")
_BOX_RE = re.compile(r"^BOX (\d\.\d) (.*?)(?: \(continued\))?$")
_CONT_RE = re.compile(r"\s*\(continued\)$")


def _style(l: Line) -> tuple[str, float]:
    s = l.spans[0]
    return s.font, round(s.size, 1)


def _chapter_of(pg: Page) -> int | None:
    for l in pg.lines[:3]:
        m = _CHAPTER_RE.match(l.text)
        if m:
            return int(m.group(1))
    return None


def _is_divider(pg: Page) -> bool:
    return bool(pg.lines) and len(pg.lines) < 8 and any(l.size >= 26 for l in pg.lines)


def _heading_level(l: Line) -> int | None:
    font, size = _style(l)
    if not font.startswith("HelveticaLTStd") or len(l.text) > 90:
        return None
    if l.text == "References" and font.endswith("-Bold"):
        return 1  # Bold 14 in chapter 2, Bold 16 elsewhere; always a chapter-level section
    if font.endswith("-Bold") and size >= 15:
        return 1
    if font.endswith("-Bold") and size >= 13:
        return 2
    if font.endswith("-Roman") and size == 11.0:
        return 2
    return None


_YEAR_CELL = re.compile(r"^((19|20)\d\d(/\d\d)?[ef]?)$")


def _is_header_row(cells: list[str]) -> bool:
    """A row of column headings (years / fiscal years), e.g. '2022/23 | 2023/24 | ... | 2026/27f'."""
    return sum(bool(_YEAR_CELL.match(c)) for c in cells) >= 4


def _format_rows(rows: list[list[str]]) -> str:
    """Data rows as text. A table can change its column headings part-way down ("Fiscal-year basis
    ..." then a new row of years for the next group). A bare row of years among the data lines reads
    as just another row, and a model then pairs values with the wrong year (Pakistan's FY2025/26e
    figure came back labelled 2026/27f). So that row is marked, and every row under it is written
    with its column headings spelled out. Rows under the table's own header stay as printed."""
    out, heads = [], None
    for cells in rows:
        if _is_header_row(cells):
            heads = [c for c in cells if _YEAR_CELL.match(c)]
            out.append(f"[Column headings for the rows below: {' | '.join(cells)}]")
        elif heads and len(cells) == len(heads) + 1:
            seen: dict[str, int] = {}
            labelled = []
            for h, v in zip(heads, cells[1:]):
                seen[h] = seen.get(h, 0) + 1
                labelled.append(f"{h}{' (repeated column)' if seen[h] > 1 else ''} = {v}")
            out.append(f"{cells[0]}: " + "; ".join(labelled))
        else:
            out.append(" | ".join(cells))
    return "\n".join(out)


_TABLE_RE = re.compile(r"^TABLE [\dA-Z.]+")
_NUM_RE = re.compile(r"^[-\u2212+]?[\d.,]+[a-z]?%?$|^\.\.$|^n\.a\.$")
_NOTE_RE = re.compile(r"^(Sources?|Notes?)\b")


def _small_helvetica(l: Line) -> bool:
    font, size = _style(l)
    return font.startswith("Helvetica") and size <= 8.1


def _rows(lines: list[Line]) -> list[list[str]]:
    """Cluster cell lines by vertical position into rows of cells ordered by x."""
    rows: list[list[Line]] = []
    for l in sorted(lines, key=lambda l: (l.top, l.spans[0].bbox[0])):
        if rows and abs(l.top - rows[-1][0].top) <= 2.5:
            rows[-1].append(l)
        else:
            rows.append([l])
    return [[c.text for c in sorted(r, key=lambda c: c.spans[0].bbox[0])] for r in rows]


def _is_data_row(cells: list[str]) -> bool:
    return len(cells) >= 4 and not _NUM_RE.match(cells[0]) and sum(bool(_NUM_RE.match(c)) for c in cells[1:]) >= 3


def _split_header(rows: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    for i, r in enumerate(rows):
        if _is_data_row(r):
            return rows[:i], rows[i:]
    return [], rows  # text-only table: keep every row, no repeated column header


def _find_tables(body: list[Line], l1: str | None, appendix_page: bool):
    """Tables on a page -> {first line id: (caption, header rows, data rows, consumed ids, note lines)}.
    A table is a 'TABLE n.n' caption + its small-Helvetica cell lines up to the Source/Note lines;
    on Statistical Appendix pages the whole page body is a table titled by its heading."""
    found = {}
    if appendix_page:
        cells = [l for l in body if _small_helvetica(l)]
        notes = [l for l in cells if _NOTE_RE.match(l.text)]
        cells = [l for l in cells if l not in notes and _heading_level(l) is None]
        if cells:
            hdr, data = _split_header(_rows(cells))
            found[id(cells[0])] = (l1 or "Statistical Appendix", hdr, data, {id(l) for l in cells + notes}, notes)
        return found
    caps = [l for l in body if _TABLE_RE.match(l.text) and _style(l)[0].endswith("-Bold") and _style(l)[1] >= 10]
    caps.sort(key=lambda l: l.top)
    for n, cap in enumerate(caps):
        # geometry, not stream order: cells sit below the caption and above the next caption
        bottom = caps[n + 1].top if n + 1 < len(caps) else float("inf")
        region = [m for m in body if cap.top < m.top < bottom and _small_helvetica(m)]
        note_tops = [m.top for m in region if _NOTE_RE.match(m.text) and _style(m)[1] <= 6.1]
        end = min(note_tops) if note_tops else float("inf")
        cells = [m for m in region if m.top < end]
        notes = [m for m in region if m.top >= end and _style(m)[1] <= 6.1]
        caption = re.sub(r"\s+", " ", "".join(s.text for s in cap.spans if s.size >= 8.1)).strip()
        caption = re.sub(r" \d$", "", caption)  # footnote marker glued to the title
        cells.sort(key=lambda m: m.top)
        if cells and cells[0].text.startswith("("):
            caption += " " + cells[0].text
            cells = cells[1:]
        if not cells:
            continue
        hdr, data = _split_header(_rows(cells))
        found[id(cap)] = (caption, hdr, data, {id(cap)} | {id(m) for m in cells + notes}, notes)
    return found


def build_sections(pages: list[Page], is_running: IsRunning = is_running) -> list[Section]:
    sections: list[Section] = []
    cur: Section | None = None

    chapter: int | None = None
    l1: str | None = None
    l2: str | None = None
    box: str | None = None
    saved: tuple[str | None, str | None] = (None, None)
    front = FRONT[0][1]

    def state() -> tuple:
        title = CHAPTERS.get(chapter, APPENDIX if chapter == 0 else FRONT_MATTER)
        region = l1 if chapter == 2 and l1 in REGIONS else None
        path = [title]
        if box:
            path.append(box)
        elif l1 and chapter is not None and chapter > 0:
            path.append(l1)
        elif chapter is None:
            path = [FRONT_MATTER, front]
        if chapter == 0 and l1:
            path.append(l1)
        if l2:
            path.append(l2)
        if box:
            kind = "box"
        elif l1 and l1.upper().startswith("ANNEX"):
            kind = "annex"
        elif l1 == "References":
            kind = "references"
        elif chapter is None:
            kind = "front"
        elif chapter == 0:
            kind = "appendix"
        else:
            kind = "body"
        return (chapter if chapter else None, title, region, kind, tuple(path))

    def emit(line_text: str, page: int):
        nonlocal cur
        ch, title, region, kind, path = state()
        if cur is None or cur.path != path:
            cur = Section(ch, title, region, kind, path, [])
            sections.append(cur)
        if not cur.segments or cur.segments[-1][0] != page:
            cur.segments.append((page, ""))
        cur.segments[-1] = (page, cur.segments[-1][1] + line_text + "\n")

    def emit_table(caption: str, hdr, data, notes, page: int):
        nonlocal cur
        ch, title, region, _, path = state()

        plain = lambda rows: "\n".join(" | ".join(c) for c in rows)  # the table's own header, as printed
        note_text = " ".join(n.text for n in notes)
        header = "\n".join([caption, plain(hdr)] if hdr else [caption])
        text = _format_rows(data) + (f"\n{note_text}" if note_text else "")
        tpath = path if path[-1] == caption else path + (caption,)
        sections.append(Section(ch, title, region, "table", tpath, [(page, text)], header))
        cur = None

    for pg in pages:
        ch = _chapter_of(pg)
        head = pg.lines[0].text if pg.lines else ""
        if ch is not None and ch != chapter:
            chapter, l1, l2, box = ch, SEED_SECTION.get(ch), None, None
        elif pg.page >= 185 and head == "STATISTICAL APPENDIX" or (chapter == 4 and _is_divider(pg) and "APPENDIX" in head):
            if chapter != 0:
                chapter, l1, l2, box = 0, None, None, None
        elif ch is None and _is_divider(pg) and (m := re.match(r"^CHAPTER (\d)$", head)):
            chapter, l1, l2, box = int(m.group(1)), SEED_SECTION.get(int(m.group(1))), None, None
        if chapter is None:
            for start, name in FRONT:
                if pg.page >= start:
                    front = name

        if _is_divider(pg) or not pg.lines:
            continue

        body = [l for l in pg.lines if not is_running(l)]
        has_box_header = any(_BOX_RE.match(l.text) for l in body if _style(l)[1] == 10.0)
        if box and not has_box_header:
            box, (l1, l2) = None, (saved[0], None)

        heads = {id(l): _heading_level(l) for l in body}
        merged_for = {}  # first line id -> (text, level, [line ids consumed])
        run: list[tuple[Line, int]] = []
        runs: list[list[tuple[Line, int]]] = []
        for l in body:
            lvl = heads[id(l)]
            if lvl is not None and not (_style(l)[1] == 10.0):
                if run and (_style(run[-1][0]) != _style(l) or not 0 < l.top - run[-1][0].top <= 22):
                    runs.append(run)
                    run = []
                run.append((l, lvl))
            elif run:
                runs.append(run)
                run = []
        if run:
            runs.append(run)
        for r in runs:
            merged_for[id(r[0][0])] = (" ".join(l.text for l, _ in r), r[0][1], {id(l) for l, _ in r})

        page_l1 = [m[0] for m in merged_for.values() if m[1] == 1] + [l1 or ""]
        appendix_page = chapter == 0 and any(t.startswith("Real GDP growth") for t in page_l1)
        tables = _find_tables(body, page_l1[0] or None, appendix_page)
        skip: set[int] = set()
        for t in tables.values():
            skip |= t[3]
        for l in body:
            if id(l) in tables:
                cap, hdr, data, ids, notes = tables[id(l)]
                emit_table(cap, hdr, data, notes, pg.page)
                continue
            if id(l) in skip:
                continue
            if _style(l)[1] == 10.0 and _BOX_RE.match(l.text):
                m = _BOX_RE.match(l.text)
                if not box:
                    title = m.group(2)
                    # wrapped box title on the next 10pt bold line
                    saved = (l1, l2)
                    box, l2 = f"Box {m.group(1)} {title}", None
                continue
            if id(l) in merged_for:
                text, lvl, ids = merged_for[id(l)]
                skip |= ids
                text = _CONT_RE.sub("", text)
                if lvl == 1:
                    box = None
                    if text != l1:
                        l1, l2 = text, None
                else:
                    if text != l2:
                        l2 = text
                continue
            emit(l.text, pg.page)

    for s in sections:
        s.header = repair(s.header, th_damaged=True)
        s.segments = [(p, repair(t, th_damaged=True).strip()) for p, t in s.segments]
        s.segments = [(p, t) for p, t in s.segments if t]
    return [s for s in sections if s.segments]


# ---- query vocabulary -------------------------------------------------------------------------
from app.profiles.long.query import Vocabulary  # noqa: E402

EAP, ECA, LAC, MNA, SAR, SSA = REGIONS

# Region name / abbreviation / country -> region (the report's six regions; Pakistan is in MNA).
_ALIASES: dict[str, str] = {}


def _add(region: str, *names: str):
    for n in names:
        _ALIASES[n.lower()] = region


_add(EAP, "east asia and pacific", "east asia", "eap", "china", "indonesia", "thailand", "vietnam",
     "philippines", "malaysia", "cambodia", "mongolia", "myanmar", "fiji", "papua new guinea")
_add(ECA, "europe and central asia", "eca", "turkiye", "türkiye", "turkey", "poland", "ukraine", "russia",
     "kazakhstan", "romania", "serbia", "georgia", "armenia", "azerbaijan", "uzbekistan")
_add(LAC, "latin america and the caribbean", "latin america", "lac", "brazil", "mexico", "argentina",
     "colombia", "chile", "peru", "ecuador", "guatemala", "honduras", "haiti")
_add(MNA, "middle east, north africa, afghanistan, and pakistan", "middle east and north africa",
     "mena", "menaap", "mna", "pakistan", "afghanistan", "egypt", "iran", "iraq", "morocco",
     "saudi arabia", "tunisia", "algeria", "jordan", "lebanon")
_add(SAR, "south asia", "sar", "india", "bangladesh", "sri lanka", "nepal", "bhutan", "maldives")
_add(SSA, "sub-saharan africa", "ssa", "nigeria", "south africa", "ethiopia", "kenya", "angola",
     "tanzania", "ghana", "zambia", "uganda", "senegal")



def gep_vocabulary() -> Vocabulary:
    """What the reference report's questions can name: chapters, the six regions (with the countries
    that belong to each - Pakistan is in MNA, not South Asia) and the executive summary."""
    return Vocabulary(
        chapters=dict(CHAPTERS),
        regions=list(REGIONS),
        aliases=dict(_ALIASES),
        named_sections={"executive summary": f"{FRONT_MATTER} > Executive Summary"},
    )
