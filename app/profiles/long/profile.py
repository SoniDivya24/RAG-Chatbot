from dataclasses import dataclass, field

import pymupdf

from app.profiles.base import Chunk, Profile
from app.profiles.long import gep
from app.profiles.long.chunks import Exclusions, build_parents, chunk_sections
from app.profiles.long.context import DEFAULT_BUDGET_TOKENS, DEFAULT_PAD, assemble, est_tokens, render
from app.profiles.long.outline import build_generic_sections, generic_vocabulary
from app.profiles.long.pages import build_pages, generic_running, raw_lines
from app.profiles.long.query import QueryFilter, Vocabulary, understand
from app.profiles.long.repair import has_th_damage
from app.profiles.long.sections import Section

REFUSAL = "I could not find this in the document."
RETRIEVAL_K = 5
# Cosine-similarity floor. Placeholder carried over from the prototype; tuned on the refusal
# questions in eval/questions/long.json.
MIN_RELEVANCE_SCORE = 0.60

# Not worth embedding (and the free embedding tier is quota-limited) in the reference report:
# front-matter boilerplate and the back-matter publication lists.
GEP_EXCLUDED_TITLES = {
    "Cover", "Copyright", "Contents", "Acknowledgments",
    "Global Economic Prospects: Selected Topics, 2015-26",
    "Prospects Group: Selected Other Publications on the Global Economy, 2015-26",
}


@dataclass
class LongSource:
    """An analysed upload: its sections, the vocabulary questions can use, what to skip."""

    sections: list[Section]
    vocabulary: Vocabulary
    exclusions: Exclusions
    n_pages: int
    preset: str  # "gep" (the reference report) or "generic"
    notes: list[str] = field(default_factory=list)


class LongDocumentProfile(Profile):
    """Long, structured documents: the outline (chapters, sections, boxes, tables) becomes a heading
    path on every chunk; small child chunks are searched, and the prompt is built from the text around
    the hits (their parent sections), ordered and within a token budget."""

    id = "long"
    label = "Long document"
    description = "Long structured documents: section-aware retrieval with managed context."
    extensions = (".pdf",)
    sample_file = "GEP-Jun-2026.pdf"
    sample_label = "World Bank Global Economic Prospects, June 2026"
    upload_hint = "Long PDFs organised into chapters and sections (100+ pages)."
    example_questions = (
        "What is the growth outlook for South Asia in this report?",
        "What does Chapter 3 say about sovereign debt in developing economies?",
        "According to the executive summary, what are the main risks to the global outlook?",
    )

    retrieval_k = RETRIEVAL_K
    min_score = MIN_RELEVANCE_SCORE
    temperature = 0.0
    refusal = REFUSAL
    drop_sources_on_refusal = True

    # Context management: how far each hit is widened, and the prompt's token budget.
    context_pad = DEFAULT_PAD
    context_budget_tokens = DEFAULT_BUDGET_TOKENS

    grounded_instructions = (
        "You answer questions about the uploaded long document using ONLY the CONTEXT passages below. "
        "Each passage is labelled with its section path and PDF page. Never use outside knowledge, even "
        "for well-known facts. Do not mix figures from different regions, chapters or sections: answer "
        "from the passage that is about what the question asks. If the passages do not contain the "
        "answer (for example the question is about a topic or year the document does not cover), reply "
        f'with exactly: "{REFUSAL}" and nothing else. Otherwise answer directly and concisely, quoting '
        "figures exactly as written, and cite the section and page(s) you used like "
        "(Regional Outlooks > South Asia, p. 96)."
    )

    # ---- reading the upload -------------------------------------------------------------------

    def extract(self, content: bytes, filename: str) -> LongSource:
        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise ValueError("That doesn't look like a readable PDF.") from exc
        with doc:
            if doc.needs_pass:
                raise ValueError("Password-protected PDFs aren't supported yet.")
            if not any(page.get_text().strip() for page in doc):
                raise ValueError("No readable text found in this PDF - is it a scan?")
            raw = raw_lines(doc)
            n_pages = len(doc)

        opening = "\n".join(line.text for lines in raw[:6] for line in lines)
        if gep.is_gep(opening):
            pages = build_pages(raw, gep.is_running, th_damaged=True)
            sections = gep.build_sections(pages)
            return LongSource(
                sections, gep.gep_vocabulary(), Exclusions(titles=set(GEP_EXCLUDED_TITLES)), n_pages, "gep"
            )

        sample = "\n".join(line.text for lines in raw[:40] for line in lines)
        is_running = generic_running(raw)
        pages = build_pages(raw, is_running, th_damaged=has_th_damage(sample))
        sections = build_generic_sections(pages, is_running, title=filename.rsplit(".", 1)[0])
        return LongSource(sections, generic_vocabulary(sections), Exclusions(), n_pages, "generic")

    def chunk(self, extracted: LongSource) -> list[Chunk]:
        chunks = chunk_sections(extracted.sections, extracted.exclusions)
        if not chunks:
            raise ValueError("Document produced no usable text - is the file empty?")
        return chunks

    def sidecars(self, extracted: LongSource) -> dict:
        return {
            "parents": build_parents(extracted.sections, extracted.exclusions),
            "vocabulary": extracted.vocabulary.to_json(),
        }

    # ---- answering ----------------------------------------------------------------------------

    def _vocabulary(self, store) -> Vocabulary:
        return Vocabulary.merge([Vocabulary.from_json(v) for v in store.all_sidecars("vocabulary").values()])

    def query_filter(self, question: str, store) -> tuple[dict | None, list[str]]:
        f = understand(question, self._vocabulary(store))
        return f.where, f.notes

    def precheck(self, question: str, store) -> str | None:
        vocab = self._vocabulary(store)
        f: QueryFilter = understand(question, vocab)
        if f.bad_chapter:
            return f"The document has {len(vocab.chapters)} chapters; there is no Chapter {f.bad_chapter}."
        return None

    def build_context(self, hits: list[dict], store) -> tuple[str, list[dict]]:
        cache: dict[str, dict | None] = {}

        def get_parent(document_id: str, section: int) -> dict | None:
            if document_id not in cache:
                cache[document_id] = store.get_sidecar(document_id, "parents")
            parents = cache[document_id]
            return parents.get(str(section)) if parents else None

        passages = assemble(hits, get_parent, self.context_pad, self.context_budget_tokens)
        if not passages:  # no parent data (an older index): fall back to the raw hits
            return self.format_context(hits), [self.source_payload(h) for h in hits]
        sources = [
            {
                "text": p.text,
                "score": p.score,
                "source": p.source,
                "page": p.page,
                "section": p.heading_path,
                # "body" is the ordinary case and would be noise on every source; show the kind only
                # when it says something (a table, a box, front matter, an annex)
                **({"kind": p.kind} if p.kind != "body" else {}),
            }
            for p in sorted(passages, key=lambda p: -p.score)
        ]
        return render(passages), sources

    def format_context(self, hits: list[dict]) -> str:
        ordered = sorted(hits, key=lambda h: (h["metadata"].get("page", 0), h["metadata"].get("chunk_index", 0)))
        return "\n\n".join(
            f"[{h['metadata'].get('heading_path') or 'Document'}, p. {h['metadata'].get('page', '?')}] {h['text']}"
            for h in ordered
        )


__all__ = ["LongDocumentProfile", "LongSource", "est_tokens"]
