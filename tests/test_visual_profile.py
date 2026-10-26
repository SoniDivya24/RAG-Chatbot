"""Offline tests for the Visual document mode.

The generic behaviour (layout derived from the document, chart detection, table rebuild, footnote
linking, call-out grouping) is tested on small synthetic PDFs built here with PyMuPDF. The real iMac
report is checked against a golden snapshot of chunk hashes when samples/ has it. No vision or
embedding calls are made: the chart describer is a stub.
"""

import collections
import hashlib
import json
from pathlib import Path

import pymupdf
import pytest

from app.profiles import VisualProfile
from app.profiles.visual.callouts import all_callouts
from app.profiles.visual.footnotes import claims, find_markers, parse_endnotes
from app.profiles.visual.layout import derive_layout
from app.profiles.visual.tables import extract_tables

IMAC = Path(__file__).parent.parent / "samples" / "iMac_PER_Oct2024.pdf"
GOLDEN = Path(__file__).parent / "golden" / "visual_imac_chunks.json"

BODY_TEXT = "The quick brown fox jumps over the lazy dog while the committee reviews the annual figures. "


def build_pdf(page_builders) -> bytes:
    doc = pymupdf.open()
    for build in page_builders:
        page = doc.new_page(width=612, height=792)
        build(page)
    return doc.tobytes()


def text(page, x, y, s, size=8.5, **kw):
    page.insert_text((x, y), s, fontsize=size, **kw)
    return x + pymupdf.get_text_length(s, fontsize=size)


def body_page(title):
    def build(page):
        text(page, 60, 80, title, size=24)
        for i in range(8):
            text(page, 60, 130 + i * 14, BODY_TEXT * 2)
    return build


def open_doc(data: bytes) -> pymupdf.Document:
    return pymupdf.open(stream=data, filetype="pdf")


# ---- layout is derived from the document, not hard-coded -------------------------------------


def test_layout_finds_body_size_page_titles_and_endnote_pages():
    def endnotes(page):
        text(page, 60, 80, "Endnotes", size=24)
        text(page, 211, 120, "1", size=4.7)
        text(page, 222, 120, "A note about the first claim.")

    layout = derive_layout(open_doc(build_pdf([body_page("One"), body_page("Two"), body_page("Three"), endnotes])))

    assert layout.body == 8.5 and layout.scale == 1.0
    assert layout.title_size == 24.0
    assert layout.endnote_pages == (4,)
    assert layout.note_x_min < 211 < layout.note_x_max < 222  # number column found from the document


def test_a_document_with_bigger_text_scales_its_thresholds():
    def big(page):
        text(page, 60, 80, "Title", size=30)
        for i in range(8):
            text(page, 60, 130 + i * 16, BODY_TEXT * 2, size=10.2)

    layout = derive_layout(open_doc(build_pdf([big, big, big])))

    assert layout.body == 10.2 and layout.scale == pytest.approx(1.2)
    assert layout.heading == pytest.approx(11 * 1.2) and layout.pts(20) == pytest.approx(24)


def test_no_title_and_no_endnotes_is_fine():
    def plain(page):
        for i in range(8):
            text(page, 60, 100 + i * 14, BODY_TEXT * 2)

    layout = derive_layout(open_doc(build_pdf([plain, plain])))

    assert layout.title_size is None and layout.endnote_pages == () and layout.chart_regions == {}


def test_stacked_coloured_bars_are_a_chart_but_table_stripes_are_not():
    def chart(page):
        text(page, 60, 80, "Chart", size=24)
        for col, x in enumerate((100, 250, 400)):
            y = 300.0
            for fill in ((0.9, 0.3, 0.8), (0.95, 0.85, 0.1), (0.1, 0.8, 0.9)):
                page.draw_rect(pymupdf.Rect(x, y, x + 70, y + 60), fill=fill)
                y += 60

    def stripes(page):
        text(page, 60, 80, "Table", size=24)
        for i in range(6):
            page.draw_rect(pymupdf.Rect(60, 200 + i * 20, 500, 220 + i * 20), fill=(0.94, 0.94, 0.94) if i % 2 else (0.8, 0.8, 0.8))

    layout = derive_layout(open_doc(build_pdf([body_page("A"), chart, stripes])))

    assert list(layout.chart_regions) == [2]
    y0, y1 = layout.chart_regions[2]
    assert y0 < 300 and y1 > 480  # the band covers the bars plus room for their labels


# ---- tables ----------------------------------------------------------------------------------


def power_table(page):
    text(page, 60, 80, "Tables", size=24)
    # header bar over three columns: row labels | 100V | 115V
    for x0, x1 in ((60, 200), (200, 340), (340, 480)):
        page.draw_rect(pymupdf.Rect(x0, 150, x1, 175), fill=(0.2, 0.2, 0.2))
    text(page, 64, 166, "Mode")
    text(page, 204, 166, "100V")
    text(page, 344, 166, "115V")
    for i, (label, a, b) in enumerate((("Off", "0.27W", "0.27W"), ("Sleep", "0.56W", "0.57W"))):
        y = 195 + i * 20
        text(page, 64, y, label)
        text(page, 204, y, a)
        text(page, 344, y, b)
    page.draw_rect(pymupdf.Rect(60, 235, 480, 235.4), fill=(0.5, 0.5, 0.5))  # closing rule
    text(page, 60, 255, "Note: Values are measured at the wall.")


def test_a_table_is_rebuilt_so_every_value_sits_next_to_its_headers():
    layout = derive_layout(open_doc(build_pdf([body_page("A"), body_page("B"), power_table])))
    doc = open_doc(build_pdf([body_page("A"), body_page("B"), power_table]))

    (table,) = extract_tables(doc, layout, 3)
    out = table.to_text()

    assert table.headers == ["Mode", "100V", "115V"]
    assert "- Sleep: 100V = 0.56W; 115V = 0.57W" in out
    assert "- Off: 100V = 0.27W; 115V = 0.27W" in out
    assert out.endswith("Note: Values are measured at the wall.")


# ---- footnotes -------------------------------------------------------------------------------


def footnote_pages():
    def claim(page):
        text(page, 60, 80, "Materials", size=24)
        x = text(page, 60, 140, "We use recycled copper in the thermal module")
        x = text(page, x, 138, "1", size=4.7)  # superscript marker right after the claim
        text(page, x, 140, ". Other parts use steel.")

    def endnotes(page):
        text(page, 60, 80, "Endnotes", size=24)
        text(page, 211, 130, "1", size=4.7)
        text(page, 222, 130, "Applies to the four-port model only.")

    return [body_page("A"), body_page("B"), claim, endnotes]


def test_a_footnote_marker_is_linked_to_its_endnote_text():
    data = build_pdf(footnote_pages())
    doc = open_doc(data)
    layout = derive_layout(doc)

    notes = parse_endnotes(doc, layout)
    markers = find_markers(doc, layout, 3)
    found = claims(doc, layout)

    assert notes == {1: {"page": 4, "text": "Applies to the four-port model only."}}
    assert [m.number for m in markers] == [1]
    assert found == [{"page": 3, "number": 1, "claim": "We use recycled copper in the thermal module[^1]."}]


def test_claim_chunks_carry_their_caveat_and_endnotes_are_searchable_on_their_own():
    profile = VisualProfile(describe=lambda png, page: "")
    chunks = profile.chunk(profile.extract(build_pdf(footnote_pages()), "x.pdf"))
    by_kind = collections.defaultdict(list)
    for c in chunks:
        by_kind[c.metadata["kind"]].append(c)

    (claim,) = by_kind["footnoted claim"]
    assert "recycled copper" in claim.text and "four-port model only" in claim.text
    assert claim.metadata == {"page": 3, "kind": "footnoted claim", "endnote": 1}
    assert [c.text for c in by_kind["endnote"]] == ["Endnote 1 (p. 4): Applies to the four-port model only."]
    # the endnote pages themselves aren't also indexed as prose
    assert all(c.metadata["page"] != 4 for c in by_kind["prose"])


# ---- call-outs -------------------------------------------------------------------------------


def test_a_big_number_and_its_caption_become_one_call_out():
    def callout(page):
        text(page, 60, 80, "Packaging", size=24)
        text(page, 60, 200, "100%", size=18, fontname="hebo")
        text(page, 60, 216, "of the packaging is fiber-based", size=9.5)
        text(page, 60, 228, "due to our work to remove plastic", size=9.5)

    doc = open_doc(build_pdf([body_page("A"), body_page("B"), callout]))
    found = all_callouts(doc, derive_layout(doc))

    assert [c.text for c in found] == ["100% of the packaging is fiber-based due to our work to remove plastic"]


# ---- the profile -----------------------------------------------------------------------------


def test_the_chart_page_is_described_once_and_stored_as_a_chart_chunk():
    def chart(page):
        text(page, 60, 80, "Chart", size=24)
        for x in (100, 250, 400):
            y = 300.0
            for fill in ((0.9, 0.3, 0.8), (0.95, 0.85, 0.1), (0.1, 0.8, 0.9)):
                page.draw_rect(pymupdf.Rect(x, y, x + 70, y + 60), fill=fill)
                y += 60

    seen = []
    profile = VisualProfile(describe=lambda png, page: seen.append((page, png[:4])) or "Baseline 445 kg minus 99 kg is 346 kg.")
    chunks = profile.chunk(profile.extract(build_pdf([body_page("A"), chart]), "x.pdf"))

    (chart_chunk,) = [c for c in chunks if c.metadata["kind"] == "chart"]
    assert seen == [(2, b"\x89PNG")]  # a rendered image of page 2 went to the describer
    assert chart_chunk.text == "Chart on p. 2 (described from the page image): Baseline 445 kg minus 99 kg is 346 kg."


def test_any_text_pdf_works_even_with_no_special_elements():
    profile = VisualProfile(describe=lambda png, page: "")
    chunks = profile.chunk(profile.extract(build_pdf([body_page("A"), body_page("B")]), "x.pdf"))

    assert chunks and {c.metadata["kind"] for c in chunks} == {"prose"}
    assert chunks[0].text.startswith("Section: A (p. 1)\n")


def test_unreadable_and_scanned_pdfs_are_rejected_clearly():
    profile = VisualProfile(describe=lambda png, page: "")
    blank = build_pdf([lambda page: None])

    with pytest.raises(ValueError, match="readable PDF"):
        profile.extract(b"this is not a pdf", "x.pdf")
    with pytest.raises(ValueError, match="No readable text"):
        profile.extract(blank, "scan.pdf")


def test_password_protected_pdfs_are_rejected_clearly():
    fixture = Path(__file__).parent / "fixtures" / "protected.pdf"

    with pytest.raises(ValueError, match="Password-protected"):
        VisualProfile(describe=lambda png, page: "").extract(fixture.read_bytes(), "protected.pdf")


def test_context_labels_each_passage_with_page_and_element_kind():
    hits = [
        {"text": "346 kg", "score": 0.9, "metadata": {"page": 10, "kind": "table"}},
        {"text": "445 kg", "score": 0.8, "metadata": {"page": 2, "kind": "chart"}},
    ]

    assert VisualProfile(describe=lambda *a: "").format_context(hits) == "[p. 10 | table] 346 kg\n\n[p. 2 | chart] 445 kg"


def test_answers_are_deterministic_and_refusals_carry_no_sources():
    profile = VisualProfile(describe=lambda *a: "")

    assert profile.temperature == 0.0 and profile.drop_sources_on_refusal is True
    assert profile.refusal in profile.grounded_instructions


# ---- the real iMac report (skipped when the sample isn't present) ----------------------------


@pytest.mark.skipif(not IMAC.exists(), reason="samples/iMac_PER_Oct2024.pdf not present")
def test_imac_report_layout_is_derived_to_the_values_the_extractors_were_tuned_on():
    layout = derive_layout(pymupdf.open(IMAC))

    assert (layout.body, layout.scale, layout.title_size) == (8.5, 1.0, 24.0)
    assert layout.endnote_pages == (11, 12)
    assert layout.footer_y == pytest.approx(735) and layout.body_y == pytest.approx((70, 700))
    assert layout.big == pytest.approx((14, 23)) and layout.heading == pytest.approx(11)
    assert layout.note_x_max == pytest.approx(218, abs=0.1) and layout.note_x_min == pytest.approx(205, abs=0.1)
    assert layout.chart_regions == {2: pytest.approx((240, 735))}


@pytest.mark.skipif(not IMAC.exists(), reason="samples/iMac_PER_Oct2024.pdf not present")
def test_imac_report_chunks_match_the_golden_snapshot():
    golden = json.loads(GOLDEN.read_text())
    profile = VisualProfile(describe=lambda png, page: "STUB")
    chunks = profile.chunk(profile.extract(IMAC.read_bytes(), IMAC.name))

    assert dict(sorted(collections.Counter(c.metadata["kind"] for c in chunks).items())) == golden["kinds"]
    hashes = sorted(hashlib.sha256(c.text.encode()).hexdigest() for c in chunks if c.metadata["kind"] != "chart")
    assert hashes == golden["non_chart_sha256"]


@pytest.mark.skipif(not IMAC.exists(), reason="samples/iMac_PER_Oct2024.pdf not present")
def test_imac_key_facts_are_in_the_right_elements():
    profile = VisualProfile(describe=lambda png, page: "STUB")
    chunks = profile.chunk(profile.extract(IMAC.read_bytes(), IMAC.name))

    tables = [c for c in chunks if c.metadata["kind"] == "table"]
    footprint = next(c for c in tables if "346 kg" in c.text)
    assert "Product use: 45%" in footprint.text and "Production: 50%" in footprint.text
    power = next(c for c in tables if "Sleep" in c.text)
    assert "Sleep: 100V = 0.56W; 115V = 0.57W; 230V = 0.59W" in power.text
    copper = next(c for c in chunks if "thermal module" in c.text and c.metadata["kind"] == "call-out")
    assert "(four ports) only" in copper.text  # the claim carries its endnote
