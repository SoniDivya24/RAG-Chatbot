"""Offline tests for the profile layer: the mode registry and the Standard
profile's behaviour (which must match the app as it was before modes)."""

import pytest

from app.profiles import Chunk, StandardProfile, UnavailableProfile, default_profiles


def test_registry_lists_the_four_modes_in_order():
    profiles = default_profiles()

    assert list(profiles) == ["standard", "report", "long", "visual"]
    assert [p.label for p in profiles.values()] == [
        "Standard",
        "Report",
        "Long document",
        "Visual document",
    ]
    assert profiles["standard"].available is True and profiles["report"].available is True
    assert all(not profiles[m].available for m in ("long", "visual"))


def test_unavailable_profiles_fail_clearly_instead_of_falling_back():
    long_mode = default_profiles()["long"]
    assert isinstance(long_mode, UnavailableProfile)

    with pytest.raises(ValueError, match="Long document mode isn't available yet"):
        long_mode.extract(b"x", "a.pdf")
    with pytest.raises(ValueError, match="Long document mode isn't available yet"):
        long_mode.chunk("x")


def test_standard_chunks_text_with_overlap_and_no_metadata():
    profile = StandardProfile()
    text = " ".join(f"word{n}" for n in range(600))  # ~4000 chars

    chunks = profile.chunk(text)

    assert len(chunks) > 1
    assert all(isinstance(c, Chunk) and c.text.strip() for c in chunks)
    assert all(c.metadata == {} and c.embed_text is None for c in chunks)
    assert max(len(c.text) for c in chunks) <= 800


def test_standard_rejects_empty_documents():
    with pytest.raises(ValueError, match="no usable text"):
        StandardProfile().chunk("   \n ")


def test_standard_fingerprint_is_by_text_not_file_bytes():
    profile = StandardProfile()

    as_txt = profile.fingerprint(b"hello world", "hello world")
    as_md = profile.fingerprint(b"# different bytes", "hello world")

    assert as_txt == as_md
    assert as_txt != profile.fingerprint(b"hello world", "other text")


def test_standard_source_payload_has_only_text_score_source():
    hit = {"text": "t", "score": 0.7, "metadata": {"source": "a.txt", "document_id": "d", "chunk_index": 0}}

    assert StandardProfile().source_payload(hit) == {"text": "t", "score": 0.7, "source": "a.txt"}


def test_source_payload_includes_page_section_kind_when_present():
    hit = {
        "text": "t",
        "score": 0.9,
        "metadata": {"source": "a.pdf", "page": 7, "section": "Intro > Scope", "kind": "table", "chunk_index": 2},
    }

    payload = StandardProfile().source_payload(hit)

    assert payload["page"] == 7 and payload["section"] == "Intro > Scope" and payload["kind"] == "table"
    assert "chunk_index" not in payload
