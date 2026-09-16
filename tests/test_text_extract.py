from pathlib import Path

import pytest

from app.text_extract import extract_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_txt():
    text = extract_text(b"Hello, world.", "notes.txt")
    assert text == "Hello, world."


def test_extract_md():
    text = extract_text(b"# Heading\n\nSome *markdown*.", "notes.md")
    assert "Heading" in text
    assert "markdown" in text


def test_extract_pdf():
    pdf_bytes = (FIXTURES / "sample.pdf").read_bytes()
    text = extract_text(pdf_bytes, "sample.pdf")
    assert "Lorem ipsum" in text


def test_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(b"whatever", "spreadsheet.csv")


def test_password_protected_pdf_raises_friendly_error():
    pdf_bytes = (FIXTURES / "protected.pdf").read_bytes()
    with pytest.raises(ValueError, match="(?i)password-protected"):
        extract_text(pdf_bytes, "protected.pdf")
