"""Offline tests for the Report mode: page cleaning, page-tagged chunking,
context labelling, and how the chat session applies the mode's answer rules.
The real-PDF checks run only when the sample is present under samples/."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.chat_session import ChatSession
from app.modes import Modes
from app.profiles import default_profiles
from app.profiles.report import (
    REFUSAL,
    Page,
    ReportProfile,
    clean_pages,
    detect_running_lines,
)

FIXTURES = Path(__file__).parent / "fixtures"
GPO_SAMPLE = Path(__file__).parent.parent / "samples" / "GPO-Anual-report.pdf"

BODY = (
    "The company opened {n} new offices during the year and hired a large number of "
    "engineers across all regions, expanding its research budget substantially. "
) * 3


def make_pages(n=12, head=True, foot=True, extra_mid=None):
    """n synthetic pages with a running head, page-number foot and unique body."""
    pages = []
    for i in range(1, n + 1):
        lines = []
        if head:
            lines.append(f"ACME {2020} ANNUAL REPORT | {i if i % 2 else ''}".strip(" |"))
        lines.append(f"Part {chr(64 + i)} overview")  # a real heading: distinct words per page
        lines.extend(BODY.format(n=i).split(". "))
        if extra_mid:
            lines.insert(len(lines) // 2, extra_mid.format(i=i))
        if foot:
            lines.append(str(i))
        pages.append("\n".join(lines))
    return pages


def test_running_heads_feet_and_page_numbers_are_removed():
    pages = clean_pages(make_pages())

    assert len(pages) == 12
    for page in pages:
        assert "ANNUAL REPORT" not in page.text
        assert not any(line.strip().isdigit() for line in page.text.splitlines())
        assert f"Part {chr(64 + page.page)} overview" in page.text  # real content stays


def test_page_numbers_glued_to_the_head_and_mid_page_copies_are_removed():
    # Two-up spreads put a second page's running head mid-text, with its own number glued on.
    pages = clean_pages(make_pages(extra_mid="{i} ACME 2020 ANNUAL REPORT"))

    assert len(pages) == 12
    assert all("ANNUAL REPORT" not in p.text for p in pages)


def test_a_sentence_that_only_appears_twice_is_not_page_furniture():
    raw = make_pages()
    for i in (3, 9):
        raw[i] += "\nFootnote: figures are unaudited."

    pages = {p.page: p for p in clean_pages(raw)}

    assert "Footnote: figures are unaudited." in pages[4].text
    assert "Footnote: figures are unaudited." in pages[10].text


def test_short_documents_are_left_alone():
    # With fewer than 6 pages there's no way to tell furniture from content.
    pages = clean_pages(make_pages(n=4))

    assert len(pages) == 4 and "ANNUAL REPORT" in pages[0].text


def test_near_empty_pages_are_dropped_but_numbering_is_kept():
    raw = make_pages()
    raw[1] = "Cover\n2"  # page 2 becomes a near-empty divider

    pages = clean_pages(raw)

    assert [p.page for p in pages] == [1] + list(range(3, 13))


def test_detect_running_lines_returns_normalised_keys():
    # The same head with and without a trailing page number is one running line.
    def page(n):
        head = "ACME 2020 ANNUAL REPORT | 3" if n % 2 else "ACME 2020 ANNUAL REPORT"
        body = [f"{chr(97 + n)}{chr(97 + k)}word line of real content" for k in range(7)]
        return [head, *body]

    lines = [page(n) for n in range(8)]

    assert detect_running_lines(lines) == {"acme # annual report"}


def test_chunks_carry_their_page_and_never_span_pages():
    profile = ReportProfile()
    pages = [Page(1, "Alpha sentence about revenue. " * 60), Page(7, "Beta sentence about staff. " * 60)]

    chunks = profile.chunk(pages)

    assert {c.metadata["page"] for c in chunks} == {1, 7}
    assert all(("Alpha" in c.text) != ("Beta" in c.text) for c in chunks)
    assert all(set(c.metadata) == {"page"} for c in chunks)  # no noisy 'kind' tag
    assert max(len(c.text) for c in chunks) <= 800


def test_chunk_rejects_a_document_with_no_pages():
    with pytest.raises(ValueError, match="no usable text"):
        ReportProfile().chunk([])


def test_context_is_labelled_with_pages():
    profile = ReportProfile()
    hits = [
        {"text": "166 libraries", "score": 0.9, "metadata": {"page": 5}},
        {"text": "other", "score": 0.8, "metadata": {"page": 21}},
    ]

    assert profile.format_context(hits) == "[p. 5] 166 libraries\n\n[p. 21] other"
    assert profile.source_payload(hits[0])["page"] == 5


def test_password_protected_pdfs_are_rejected_clearly():
    with pytest.raises(ValueError, match="Password-protected"):
        ReportProfile().extract((FIXTURES / "protected.pdf").read_bytes(), "protected.pdf")


def test_extract_reads_a_real_pdf_into_1_indexed_pages():
    pages = ReportProfile().extract((FIXTURES / "sample.pdf").read_bytes(), "sample.pdf")

    assert pages and pages[0].page >= 1
    assert all(p.text.strip() for p in pages)


# ---- how the chat session applies the mode's answer rules ------------------


class RecordingLLM:
    def __init__(self, reply):
        self.reply = reply
        self.messages = []

    def invoke(self, messages):
        self.messages = messages
        return SimpleNamespace(content=self.reply)


@pytest.fixture
def report_chat(tmp_path, fake_embedder):
    profiles = default_profiles()
    profiles["report"].min_score = 0.25  # floor suited to the fake embeddings
    modes = Modes(tmp_path / "data", fake_embedder, profiles)
    engine = modes.engine("report")
    engine._index(
        [Page(5, "In FY 2018 GPO staff visited 166 depository libraries in 25 states. " * 3)],
        "report.pdf",
        "h1",
    )
    return modes.chat("report"), engine


def test_grounded_prompt_labels_pages_and_states_the_refusal_sentence(report_chat):
    chat, _ = report_chat
    chat._llm = RecordingLLM("GPO staff visited 166 depository libraries (p. 5).")

    result = chat.ask("How many depository libraries did GPO staff visit?")

    system = chat._llm.messages[0].content
    assert "[p. 5]" in system and REFUSAL in system
    assert result["sources"] and result["sources"][0]["page"] == 5


def test_a_refusal_comes_back_without_sources(report_chat):
    chat, _ = report_chat
    chat._llm = RecordingLLM(REFUSAL)

    result = chat.ask("How many depository libraries did GPO staff visit?")

    assert result["reply"] == REFUSAL
    assert result["sources"] == []


def test_nothing_relevant_uses_the_reports_refusal_wording(report_chat):
    chat, _ = report_chat
    chat._llm = RecordingLLM(REFUSAL)

    chat.ask("zebra quantum astrophysics volcano")

    assert f'"{REFUSAL}"' in chat._llm.messages[0].content


def test_report_answers_are_deterministic(monkeypatch, report_chat):
    chat, _ = report_chat
    seen = {}

    class FakeChat:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr("app.chat_session.ChatGoogleGenerativeAI", FakeChat)
    monkeypatch.setattr("app.chat_session.config.GOOGLE_API_KEY", "x", raising=False)
    monkeypatch.setitem(__import__("app.config", fromlist=["_ENV_VALUES"])._ENV_VALUES, "GOOGLE_API_KEY", "x")

    chat.llm  # builds the model

    assert seen["temperature"] == 0.0


def test_standard_keeps_its_original_wording_and_creativity():
    from app.profiles import StandardProfile

    standard = StandardProfile()
    assert standard.temperature == 0.7
    assert standard.refusal == "I don't have that information in the documents."
    assert standard.drop_sources_on_refusal is False


# ---- the real GPO annual report (skipped when the sample isn't present) ----


@pytest.mark.skipif(not GPO_SAMPLE.exists(), reason="samples/GPO-Anual-report.pdf not present")
def test_gpo_annual_report_is_cleaned_and_chunked_as_validated():
    profile = ReportProfile()
    pages = profile.extract(GPO_SAMPLE.read_bytes(), GPO_SAMPLE.name)
    by_page = {p.page: p.text for p in pages}

    assert len(pages) == 70  # 82 PDF pages; covers, dividers and blank pages dropped
    assert "166 depository libraries" in by_page[5]
    assert "govinfo" in by_page[22]
    assert not any("ANNUAL REPORT | U.S. GOVERNMENT" in t.upper() for t in by_page.values())
    assert len(profile.chunk(pages)) == 263  # the count the prototype's evaluation was run on


def test_the_chat_model_gets_a_request_timeout(monkeypatch, report_chat):
    chat, _ = report_chat
    seen = {}

    class FakeChat:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr("app.chat_session.ChatGoogleGenerativeAI", FakeChat)
    monkeypatch.setitem(__import__("app.config", fromlist=["_ENV_VALUES"])._ENV_VALUES, "GOOGLE_API_KEY", "x")

    chat.llm

    assert seen["timeout"] == __import__("app.config", fromlist=["LLM_TIMEOUT"]).LLM_TIMEOUT > 0
