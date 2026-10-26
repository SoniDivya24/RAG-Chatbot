"""Context management: turn retrieved child chunks into a compact, ordered prompt context.

1. Group hits by parent section and widen each hit by `pad` characters either side (clamped to the
   section), merging windows that touch - so adjacent/overlapping hits become one passage.
2. Tables hit by any chunk are sent whole (they are meaningless in fragments).
3. Order passages by document position, label each with its heading path + page.
4. Enforce a token budget (~4 chars/token): drop the lowest-scored passages first.
"""

from dataclasses import dataclass, field
from typing import Callable

DEFAULT_PAD = 400
DEFAULT_BUDGET_TOKENS = 3000


@dataclass
class Passage:
    heading_path: str
    page: int
    text: str
    score: float
    document_id: str
    section: int
    start: int
    source: str = ""
    kind: str = "body"
    chunk_indexes: list[int] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.heading_path}, p. {self.page}"


def est_tokens(text: str) -> int:
    return len(text) // 4 + 1


def _page_at(pages: list[list[int]], off: int) -> int:
    return [pg for st, pg in pages if st <= off][-1]


def assemble(
    hits: list[dict],
    get_parent: Callable[[str, int], dict | None],
    pad: int = DEFAULT_PAD,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> list[Passage]:
    """`get_parent(document_id, section_index)` returns the parent record (or None)."""
    by_section: dict[tuple[str, int], list[dict]] = {}
    for h in hits:
        by_section.setdefault((h["metadata"]["document_id"], h["metadata"]["section_index"]), []).append(h)

    passages: list[Passage] = []
    for (doc_id, si), group in by_section.items():
        parent = get_parent(doc_id, si)
        if parent is None:
            continue
        text, score = parent["text"], max(h["score"] for h in group)
        source = group[0]["metadata"].get("source", "")
        indexes = [h["metadata"]["chunk_index"] for h in group]
        if parent["kind"] == "table":
            passages.append(Passage(parent["heading_path"], parent["pages"][0][1], text, score, doc_id, si, 0, source, "table", indexes))
            continue
        spans = sorted(
            (
                max(0, h["metadata"]["char_start"] - pad),
                min(len(text), h["metadata"]["char_end"] + pad),
                h["score"],
                h["metadata"]["chunk_index"],
            )
            for h in group
        )
        merged: list[list] = []
        for a, b, sc, idx in spans:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
                merged[-1][2] = max(merged[-1][2], sc)
                merged[-1][3].append(idx)
            else:
                merged.append([a, b, sc, [idx]])
        for a, b, sc, idxs in merged:
            passages.append(
                Passage(parent["heading_path"], _page_at(parent["pages"], a), text[a:b].strip(), sc, doc_id, si, a, source, parent["kind"], idxs)
            )

    # budget: drop lowest-scored passages until the rest fits (always keep the best one)
    passages.sort(key=lambda p: -p.score)
    kept, used = [], 0
    for p in passages:
        cost = est_tokens(p.text)
        if kept and used + cost > budget_tokens:
            continue
        kept.append(p)
        used += cost
    return sorted(kept, key=lambda p: (p.document_id, p.section, p.start))  # document order


def render(passages: list[Passage]) -> str:
    return "\n\n".join(f"[{p.label}] {p.text}" for p in passages)
