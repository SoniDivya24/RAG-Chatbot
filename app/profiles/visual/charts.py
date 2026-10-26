"""Describe charts with Gemini vision and cache the result.

A chart's numbers and relationships exist only as drawn bars and labels: the text layer has the
labels but not "445 - 99 = 346". One vision call per (image, prompt version) is cached on disk, so
re-indexing never pays for it again.
"""

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Callable

import pymupdf
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app import config
from app.profiles.base import Chunk
from app.profiles.visual.layout import Layout

PROMPT_VERSION = "g1"
DPI = 110

PROMPT = (
    "This is a page from a document. Describe the data chart(s) on it so the description can "
    "answer questions without seeing the image. For each chart state: what it shows; the bars, "
    "segments or series from first to last, each with its label and value exactly as printed; every "
    "step, change or difference between them with its size; the total and the final value; and the "
    "arithmetic that links them when the chart shows one (for example a starting bar minus the "
    "reductions equals the final bar). List the categories a stacked bar is split into. Quote every "
    "number, unit and label exactly as printed, keep footnote markers as [^n], and do not invent "
    "values that are not drawn. If the chart is laid out as several columns or stacks left to right "
    "(for example a before stack, a middle stack where each reduction is a dashed box on top of the "
    "category it reduces, and an after stack), describe it in that structure. An item that is only a "
    "label with a line pointing at a sliver too thin to see is not a visible segment - say it is not "
    "visible. Write plain prose or short bullets, no preamble."
)

Describer = Callable[[bytes, int], str]  # (page image PNG, page number) -> description


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


def _cache_dir() -> Path:
    return config.DATA_DIR / "vision_cache"


def gemini_describer(png: bytes, page: int) -> str:
    """The default describer: a cached Gemini vision call using CHAT_MODEL."""
    key = hashlib.sha256(png + PROMPT_VERSION.encode() + PROMPT.encode()).hexdigest()[:16]
    path = _cache_dir() / f"p{page}-{key}.json"
    if path.exists():
        return json.loads(path.read_text())["description"]
    config.require("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(model=config.CHAT_MODEL, temperature=0, timeout=config.VISION_TIMEOUT)
    message = HumanMessage(
        content=[
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": f"data:image/png;base64,{base64.b64encode(png).decode()}"},
        ]
    )
    description = _text(llm.invoke([message]).content).strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"page": page, "model": config.CHAT_MODEL, "prompt_version": PROMPT_VERSION, "description": description}
        )
    )
    return description


def render_page(doc: pymupdf.Document, page: int, dpi: int = DPI) -> bytes:
    return doc[page - 1].get_pixmap(dpi=dpi).tobytes("png")


def chart_chunks(doc: pymupdf.Document, layout: Layout, notes: dict[int, dict], describe: Describer) -> list[Chunk]:
    """One chunk per chart page: the description plus the endnotes its markers cite."""
    chunks = []
    for page in sorted(layout.chart_regions):
        description = describe(render_page(doc, page), page)
        text = f"Chart on p. {page} (described from the page image): {description}"
        for n in sorted({int(m) for m in re.findall(r"\[\^(\d+)\]", description)}):
            if n in notes:
                text += f"\nEndnote {n}: {notes[n]['text']}"
        chunks.append(Chunk(text=text, metadata={"page": page, "kind": "chart"}))
    return chunks
