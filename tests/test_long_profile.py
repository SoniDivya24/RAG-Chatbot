"""Offline tests for the Long document mode: question -> filter, context assembly, section-bounded
chunking, the generic outline for other PDFs (synthetic PDFs built with PyMuPDF), and - when
samples/ has the reference report - a golden snapshot of its structure."""

import collections
import hashlib
import json
from pathlib import Path

import pytest

from app.profiles.long import LongDocumentProfile
from app.profiles.long.chunks import Exclusions, build_parents, chunk_sections
from app.profiles.long.context import assemble, render
from app.profiles.long.gep import gep_vocabulary
from app.profiles.long.pages import Line, Span, generic_running
from app.profiles.long.query import Vocabulary, understand
from app.profiles.long.sections import Section
from tests.pdfs import BODY_TEXT, build_pdf, text

GEP = Path(__file__).parent.parent / "samples" / "GEP-Jun-2026.pdf"
GOLDEN = Path(__file__).parent / "golden" / "long_gep.json"
MNA = "Middle East, North Africa, Afghanistan, and Pakistan"


# ---- question -> filter -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "question, where",
    [
        ("What is the growth outlook for South Asia in this report?", {"region": "South Asia"}),
        ("What is the growth outlook for India?", {"region": "South Asia"}),
        ("What is the growth outlook for Pakistan?", {"region": MNA}),  # not South Asia
        ("growth in sub-saharan africa", {"region": "Sub-Saharan Africa"}),
        ("What does Chapter 3 say about sovereign debt?", {"chapter": 3}),
        ("what does chapter three say", {"chapter": 3}),
        ("According to the executive summary, what are the risks?", {"heading_path": "Front Matter > Executive Summary"}),
        ("What is the growth outlook for India in chapter 2?", {"$and": [{"region": "South Asia"}, {"chapter": 2}]}),
        ("What is the growth outlook for Mars?", None),
        ("What will global growth be in 2035?", None),
    ],
)
def test_questions_become_conservative_filters(question, where):
    assert understand(question, gep_vocabulary()).where == where


def test_naming_several_regions_applies_no_region_filter():
    f = understand("Compare India and Brazil", gep_vocabulary())

    assert f.where is None and "several regions named: no region filter" in f.notes


def test_an_explicit_chapter_beats_a_region_in_another_chapter():
    f = understand("What does Chapter 3 say about India?", gep_vocabulary())

    assert f.where == {"chapter": 3}


def test_a_chapter_the_document_does_not_have_is_flagged_not_filtered():
    f = understand("What does Chapter 7 say about trade?", gep_vocabulary())

    assert f.bad_chapter == 7 and f.where is None


def test_a_document_without_chapters_never_flags_one():
    assert understand("What does Chapter 7 say?", Vocabulary()).bad_chapter is None


def test_the_vocabulary_survives_storage_and_merges_across_documents():
    one = gep_vocabulary()
    other = Vocabulary(chapters={9: "Nine"}, named_sections={"executive summary": "X > Executive Summary"})

    again = Vocabulary.from_json(json.loads(json.dumps(one.to_json())))
    merged = Vocabulary.merge([one, other])

    assert again.chapters == one.chapters and again.aliases == one.aliases
    assert 9 in merged.chapters and 3 in merged.chapters


# ---- context assembly -------------------------------------------------------------------------

PARENT_TEXT = ("A" * 300) + (" " + "B" * 300) + (" " + "C" * 300) + (" " + "D" * 300)


def hit(chunk_index, start, end, score, section=0, doc="d1", page_text=None):
    return {
        "text": "x",
        "score": score,
        "metadata": {"document_id": doc, "section_index": section, "char_start": start, "char_end": end, "chunk_index": chunk_index, "source": "r.pdf"},
    }


PARENTS = {
    ("d1", 0): {"heading_path": "Ch > Sec", "kind": "body", "pages": [[0, 5], [600, 6]], "text": PARENT_TEXT},
    ("d1", 1): {"heading_path": "Ch > Table", "kind": "table", "pages": [[0, 9]], "text": "caption\nrow1\nrow2"},
}


def parents(doc, section):
    return PARENTS.get((doc, section))


def test_hits_close_together_in_a_section_become_one_passage():
    passages = assemble([hit(0, 100, 200, 0.7), hit(1, 250, 350, 0.9)], parents, pad=100)

    assert len(passages) == 1
    assert passages[0].score == 0.9 and passages[0].chunk_indexes == [0, 1]
    assert passages[0].text == PARENT_TEXT[0:450].strip()  # widened by the pad, merged, clamped to the section


def test_distant_hits_stay_separate_and_come_out_in_document_order():
    passages = assemble([hit(1, 900, 1000, 0.9), hit(0, 10, 60, 0.5)], parents, pad=20)

    assert [p.start for p in passages] == [0, 880]
    assert passages[0].page == 5 and passages[1].page == 6  # each labelled with the page it starts on


def test_a_hit_in_a_table_sends_the_whole_table():
    (p,) = assemble([hit(5, 0, 0, 0.8, section=1)], parents)

    assert p.text == "caption\nrow1\nrow2" and p.kind == "table" and p.page == 9


def test_the_token_budget_drops_the_lowest_scored_passages_first():
    big = {"heading_path": "Big", "kind": "body", "pages": [[0, 1]], "text": "z" * 4000}
    lookup = lambda doc, s: big if s == 5 else PARENTS.get((doc, s))
    hits = [hit(0, 0, 4000, 0.9, section=5), hit(1, 0, 900, 0.4, section=0)]

    kept = assemble(hits, lookup, pad=0, budget_tokens=1200)

    assert [p.heading_path for p in kept] == ["Big"]  # the 0.4 passage no longer fits, the best always stays


def test_the_best_passage_is_kept_even_if_it_alone_exceeds_the_budget():
    big = {"heading_path": "Big", "kind": "body", "pages": [[0, 1]], "text": "z" * 4000}

    kept = assemble([hit(0, 0, 100, 0.9)], lambda d, s: big, pad=0, budget_tokens=10)

    assert len(kept) == 1


def test_passages_are_rendered_with_their_heading_path_and_page():
    (p,) = assemble([hit(0, 0, 50, 0.9)], parents, pad=0)

    assert render([p]).startswith("[Ch > Sec, p. 5] ")


def test_hits_whose_parent_is_missing_are_skipped():
    assert assemble([hit(0, 0, 50, 0.9, section=99)], parents) == []


# ---- chunking ---------------------------------------------------------------------------------


def section(path, segments, kind="body", chapter=None, region=None, header=""):
    return Section(chapter, "Report", region, kind, tuple(path), segments, header)


def test_chunks_never_cross_a_section_and_carry_their_place():
    one = section(["Report", "Alpha"], [(3, "Alpha sentence about revenue. " * 80)], chapter=1)
    two = section(["Report", "Beta"], [(4, "Beta sentence about staff. " * 80)], chapter=2, region="Asia")

    chunks = chunk_sections([one, two], Exclusions())

    assert all(("Alpha" in c.text) != ("Beta" in c.text) for c in chunks)
    first, last = chunks[0], chunks[-1]
    assert first.metadata["heading_path"] == "Report > Alpha" and first.metadata["chapter"] == 1 and first.metadata["page"] == 3
    assert last.metadata["region"] == "Asia" and last.metadata["section_index"] == 1
    assert first.embed_text == "Report > Alpha\n\n" + first.text  # the heading path is embedded with the text
    assert max(len(c.text) for c in chunks) <= 800


def test_a_chunks_offsets_point_into_its_parent_text():
    sec = section(["Report", "Alpha"], [(3, "First page sentence. " * 30), (4, "Second page sentence. " * 30)])
    parent = build_parents([sec], Exclusions())["0"]["text"]

    for c in chunk_sections([sec], Exclusions()):
        assert parent[c.metadata["char_start"] : c.metadata["char_end"]].strip() == c.text
    pages = {c.metadata["page"] for c in chunk_sections([sec], Exclusions())}
    assert pages == {3, 4}  # a chunk is labelled with the page it starts on


def test_a_long_table_is_split_by_rows_and_every_chunk_repeats_the_header():
    rows = "\n".join(f"Country {i} | {i}.1 | {i}.2" for i in range(200))
    table = section(["Report", "Tables", "TABLE 1"], [(26, rows)], kind="table", header="TABLE 1 Forecasts\nRegion | 2025 | 2026")

    chunks = chunk_sections([table], Exclusions())

    assert len(chunks) > 1
    assert all(c.text.startswith("TABLE 1 Forecasts\nRegion | 2025 | 2026\n") for c in chunks)
    assert all(c.metadata["kind"] == "table" and c.metadata["page"] == 26 for c in chunks)
    assert "".join(c.text for c in chunks).count("Country 199 |") == 1  # no row lost or duplicated


def test_reference_lists_and_listed_titles_are_not_indexed():
    body = section(["Report", "Body"], [(1, "Real content here. " * 10)])
    refs = section(["Report", "References"], [(2, "Smith 2020. " * 20)], kind="references")
    skip = section(["Report", "Copyright"], [(3, "All rights reserved. " * 10)])

    chunks = chunk_sections([body, refs, skip], Exclusions(titles={"Copyright"}))

    assert {c.metadata["heading_path"] for c in chunks} == {"Report > Body"}
    assert set(build_parents([body, refs, skip], Exclusions(titles={"Copyright"}))) == {"0"}


# ---- the generic outline (any other long PDF) --------------------------------------------------


def make_report(n_pages=10):
    pages = []
    for i in range(1, n_pages + 1):
        def build(page, i=i):
            text(page, 60, 40, "ACME ANNUAL REPORT", size=8)  # a running head
            y = 90.0
            if i % 4 == 1:
                text(page, 60, y, f"Chapter {(i - 1) // 4 + 1} Results", size=18, fontname="hebo")
                y += 30
            text(page, 60, y, f"Background {i}", size=13, fontname="hebo")
            for k in range(8):
                text(page, 60, y + 24 + k * 13, BODY_TEXT * 2, size=9)
            text(page, 300, 760, str(i), size=8)
        pages.append(build)
    return build_pdf(pages)


def test_another_pdf_gets_a_generic_outline_with_chapters_and_heading_paths():
    src = LongDocumentProfile().extract(make_report(), "report.pdf")

    assert src.preset == "generic"
    paths = [s.heading_path for s in src.sections]
    assert any(p.startswith("Chapter 1 Results") for p in paths)
    assert any(" > Background 2" in p for p in paths)  # sub-headings nest under their chapter
    assert {s.chapter for s in src.sections if s.chapter} == {1, 2, 3}
    assert set(src.vocabulary.chapters) == {1, 2, 3}


def test_running_heads_and_page_numbers_stay_out_of_the_body_text():
    prof = LongDocumentProfile()
    chunks = prof.chunk(prof.extract(make_report(), "report.pdf"))

    assert chunks and not any("ACME ANNUAL REPORT" in c.text for c in chunks)
    assert all(c.metadata["heading_path"] for c in chunks)


def test_a_document_without_headings_falls_back_to_one_section_per_page():
    def plain(page):
        for k in range(10):
            text(page, 60, 100 + k * 13, BODY_TEXT * 2, size=9)

    prof = LongDocumentProfile()
    src = prof.extract(build_pdf([plain, plain, plain]), "plain.pdf")

    assert [s.heading_path for s in src.sections] == ["plain > Page 1", "plain > Page 2", "plain > Page 3"]
    assert {c.metadata["page"] for c in prof.chunk(src)} == {1, 2, 3}


def test_unreadable_scanned_and_protected_pdfs_are_rejected_clearly():
    prof = LongDocumentProfile()

    with pytest.raises(ValueError, match="readable PDF"):
        prof.extract(b"not a pdf", "x.pdf")
    with pytest.raises(ValueError, match="No readable text"):
        prof.extract(build_pdf([lambda page: None]), "scan.pdf")
    with pytest.raises(ValueError, match="Password-protected"):
        prof.extract((Path(__file__).parent / "fixtures" / "protected.pdf").read_bytes(), "p.pdf")


def test_generic_running_detection_ignores_content_but_catches_page_furniture():
    def line(t):
        return Line(t, [Span(t, "f", 9.0, False, (0, 0, 1, 1))])

    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
    pages = [
        [line("ACME REPORT 2020")] + [line(f"{words[i]} {w} line of real content") for w in words[:6]] + [line(f"{i}")]
        for i in range(10)
    ]

    running = generic_running(pages)

    assert running(line("ACME REPORT 2020")) and running(line("7"))
    assert not running(line("alpha alpha line of real content"))


# ---- the reference report (skipped when the sample isn't present) -----------------------------


@pytest.fixture(scope="module")
def gep():
    prof = LongDocumentProfile()
    src = prof.extract(GEP.read_bytes(), GEP.name)
    return prof, src, prof.chunk(src)


@pytest.mark.skipif(not GEP.exists(), reason="samples/GEP-Jun-2026.pdf not present")
def test_gep_structure_matches_the_golden_snapshot(gep):
    prof, src, chunks = gep
    golden = json.loads(GOLDEN.read_text())

    assert src.preset == "gep"
    assert len(src.sections) == golden["sections"] and len(chunks) == golden["chunks"]
    assert dict(sorted(collections.Counter(c.metadata["kind"] for c in chunks).items())) == golden["kinds"]
    outline = "\n".join(f"{s.kind}|{s.heading_path}|{s.chapter}|{s.region}|{s.pages}" for s in src.sections)
    assert hashlib.sha256(outline.encode()).hexdigest() == golden["outline_sha256"]
    embedded = sorted(hashlib.sha256((c.embed_text or c.text).encode()).hexdigest() for c in chunks)
    assert hashlib.sha256("\n".join(embedded).encode()).hexdigest() == golden["embed_inputs_sha256"]


@pytest.mark.skipif(not GEP.exists(), reason="samples/GEP-Jun-2026.pdf not present")
def test_gep_key_facts_sit_in_the_right_sections(gep):
    _, src, chunks = gep

    south_asia = [c for c in chunks if c.metadata["page"] == 96 and "6.3 percent" in c.text]
    assert south_asia and south_asia[0].metadata["heading_path"].startswith("Regional Outlooks > South Asia")
    assert south_asia[0].metadata["region"] == "South Asia"

    pakistan = [c for c in chunks if c.metadata["region"] == MNA and "1.6 percent" in c.text]
    assert pakistan  # Pakistan's figure is in the Middle East region, not South Asia

    chapter3 = [c for c in chunks if c.metadata["chapter"] == 3 and "debt-service" in c.text.lower()]
    assert chapter3 and all(c.metadata["page"] >= 109 for c in chapter3)

    summary = [c for c in chunks if c.metadata["heading_path"] == "Front Matter > Executive Summary"]
    assert summary and any("downside" in c.text for c in summary)
    assert src.vocabulary.chapters == gep_vocabulary().chapters and len(src.vocabulary.chapters) == 4


def test_a_repeating_line_in_heading_sized_type_is_not_page_furniture():
    def line(t, size):
        return Line(t, [Span(t, "f", size, False, (0, 0, 1, 1))])

    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
    # the same digit-insensitive line on every page: 9pt is a running head, 14pt is a heading
    pages = [
        [line("Results 1", 14.0), line("ACME 2020", 9.0)] + [line(f"{words[i]} {w} real content", 9.0) for w in words[:6]]
        for i in range(10)
    ]

    running = generic_running(pages)

    assert running(line("ACME 2020", 9.0))
    assert not running(line("Results 3", 14.0))


@pytest.mark.skipif(not GEP.exists(), reason="samples/GEP-Jun-2026.pdf not present")
def test_a_column_header_row_in_the_middle_of_a_table_is_marked_and_stays_with_its_rows(gep):
    """Table 2.8 changes its column headings for the Egypt/Pakistan block ("2022/23 ... 2027/28f"). Left
    as a bare row of years it was read as data and Pakistan's FY2025/26e figure was labelled 2026/27f."""
    _, _, chunks = gep

    (with_pakistan,) = [c for c in chunks if "TABLE 2.8" in c.metadata["heading_path"] and "Pakistan 1:" in c.text]

    heading = with_pakistan.text.index("[Column headings for the rows below: 2022/23 |")
    row = with_pakistan.text.index("Pakistan 1: 2022/23 = -0.2; 2023/24 = 2.6; 2024/25 = 3.1; 2025/26e = 3.0; 2026/27f = 3.2; 2027/28f = 3.7")
    assert heading < row  # the same chunk, above the row - and every value is stated with its own year
    assert not any(c.text.startswith("[Column headings") for c in chunks)  # never the table's own header line
    assert not any(c.text.rstrip().endswith("2027/28f]") for c in chunks)  # a chunk never ends on headings for rows it lacks


def test_rows_under_a_mid_table_header_spell_out_their_columns():
    from app.profiles.long.gep import _format_rows

    out = _format_rows(
        [
            ["Egypt", "1.0", "2.0"],  # under the table's own header: left as printed
            ["2022/23", "2023/24", "2024/25", "2025/26e"],
            ["Pakistan", "-0.2", "2.6", "3.1", "3.0"],
            ["Short row", "9"],  # doesn't fit the headings: left as printed
        ]
    ).splitlines()

    assert out[0] == "Egypt | 1.0 | 2.0"
    assert out[1] == "[Column headings for the rows below: 2022/23 | 2023/24 | 2024/25 | 2025/26e]"
    assert out[2] == "Pakistan: 2022/23 = -0.2; 2023/24 = 2.6; 2024/25 = 3.1; 2025/26e = 3.0"
    assert out[3] == "Short row | 9"


def test_repeated_column_headings_are_told_apart():
    from app.profiles.long.gep import _format_rows

    out = _format_rows([["2025", "2026", "2025", "2026"], ["X", "1", "2", "3", "4"]]).splitlines()

    assert out[1] == "X: 2025 = 1; 2026 = 2; 2025 (repeated column) = 3; 2026 (repeated column) = 4"


def test_table_chunks_carry_the_latest_column_headings_forward():
    rows = ["A | 1 | 2"] * 3 + ["[Column headings for the rows below: 2024 | 2025 | 2026 | 2027]"] + ["Country %d | 1 | 2 | 3 | 4" % i for i in range(120)]
    table = section(["R", "T"], [(5, "\n".join(rows))], kind="table", header="TABLE X")

    chunks = chunk_sections([table], Exclusions())

    assert len(chunks) > 1
    for c in chunks[1:]:
        body = c.text.split("\n", 1)[1]
        assert body.startswith("[Column headings for the rows below: 2024 |")  # every later chunk restates them


def test_sources_show_where_each_passage_is_and_only_name_unusual_kinds():
    parents_by_doc = {
        "d1": {
            "0": {"heading_path": "Ch > Sec", "kind": "body", "pages": [[0, 5]], "text": PARENT_TEXT},
            "1": {"heading_path": "Ch > Table", "kind": "table", "pages": [[0, 9]], "text": "caption\nrow"},
        }
    }

    class Store:
        def get_sidecar(self, doc_id, name):
            return parents_by_doc[doc_id]

    context, sources = LongDocumentProfile().build_context(
        [hit(0, 10, 60, 0.9, section=0), hit(1, 0, 0, 0.8, section=1)], Store()
    )

    by_section = {s["section"]: s for s in sources}
    assert by_section["Ch > Sec"]["page"] == 5 and "kind" not in by_section["Ch > Sec"]  # plain body: no tag
    assert by_section["Ch > Table"]["kind"] == "table" and by_section["Ch > Table"]["page"] == 9
    assert [s["score"] for s in sources] == [0.9, 0.8]  # best first
    assert context.startswith("[Ch > Sec, p. 5] ") and "[Ch > Table, p. 9] caption" in context
