"""Helpers that build small synthetic PDFs with PyMuPDF, for tests of layout-dependent code."""

import pymupdf

BODY_TEXT = "The quick brown fox jumps over the lazy dog while the committee reviews the annual figures. "


def build_pdf(page_builders) -> bytes:
    doc = pymupdf.open()
    for build in page_builders:
        page = doc.new_page(width=612, height=792)
        build(page)
    return doc.tobytes()


def text(page, x, y, s, size=8.5, **kw):
    """Insert a line of text; returns the x where it ends (so a marker can follow it)."""
    page.insert_text((x, y), s, fontsize=size, **kw)
    return x + pymupdf.get_text_length(s, fontsize=size, fontname=kw.get("fontname", "helv"))


def open_doc(data: bytes) -> pymupdf.Document:
    return pymupdf.open(stream=data, filetype="pdf")
