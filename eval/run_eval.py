"""Evaluate a mode against its question set, through the same path the UI uses.

  PYTHONPATH=. .venv/bin/python eval/run_eval.py --mode report
  PYTHONPATH=. .venv/bin/python eval/run_eval.py --mode visual

Indexes the sample document into a throwaway library (data/eval/<mode>/ - never your real
one), asks every question via the mode's ChatSession, and writes docs/results/<mode>.md.
Embeddings come from the shared cache, so a document whose vectors were imported
(scripts/import_cache.py) costs no embedding calls.

Question fields: question; must_contain (or must) - a list of groups, each needing one of its
strings in the answer; must_not; refusal (or expect_refusal) with optional refusal_or;
gold_pages (+ gold_elements) for retrieval; chapter / region (counts retrieved chunks from outside
that section); core; type (adds a per-type table).
Answer correctness is an automatic substring check - a convenience; read the printed answers
to judge for real. Retrieval is scored on the raw top-k, before the relevance floor.
"""

import argparse
import json
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

from app import config
from app.embeddings import CachedEmbedder
from app.modes import Modes

DEFAULT_SAMPLES = {
    "report": "samples/GPO-Anual-report.pdf",
    "visual": "samples/iMac_PER_Oct2024.pdf",
    "long": "samples/GEP-Jun-2026.pdf",
}


def norm(text: str) -> str:
    t = text.lower().replace(" ", " ").replace("–", "-")
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)
    return re.sub(r"\s*(percent|%)", "%", t)


# A mode's own refusal sentence is exact (Report, Visual); Standard declines in free wording
# ("I do not have information about ... in the provided documents"). Both are refusals.
_DECLINES = re.compile(
    r"^(i (do not|don't|could not|couldn't|cannot|can't) (have|find)|"
    r"(the )?(provided )?(document|documents|report|text|context)s? (do|does) not (contain|provide|mention|include|list|specify))",
    re.I,
)


def is_refusal(answer: str, refusal: str) -> bool:
    return answer.startswith(refusal) or bool(_DECLINES.match(answer.strip()))


def required_groups(q: dict) -> list[list[str]]:
    """Each group needs one of its strings in the answer. A flat list of strings (["6.3", "2026"])
    means one required string per group - it must NOT be read as groups of alternatives, or a plain
    string would be iterated character by character and match almost anything."""
    raw = q.get("must_contain") or q.get("must") or []
    return [[g] if isinstance(g, str) else list(g) for g in raw]


def judge(q: dict, answer: str, refusal: str) -> bool:
    a = norm(answer)
    refused = is_refusal(answer, refusal)
    must_not = q.get("must_not", [])
    if q.get("refusal") or q.get("expect_refusal"):
        ok = refused or any(norm(x) in a for x in q.get("refusal_or", []))
        return ok and not any(norm(x) in a for x in must_not if not refused)
    return (
        not refused
        and all(any(norm(alt) in a for alt in g) for g in required_groups(q))
        and not any(norm(x) in a for x in must_not)
    )


def summarize(rows: list[dict]) -> dict:
    groups = defaultdict(list)
    for r in rows:
        groups[r["type"]].append(r)
        groups["ALL"].append(r)
    out = {}
    for t, rs in groups.items():
        ret = [r for r in rs if not r["refusal"]]
        paged = [r for r in ret if r["paged"]]  # a mode that stores no pages has no page metrics
        out[t] = {
            "n": len(rs),
            "pass": sum(r["pass"] for r in rs),
            "n_ret": len(ret),
            "n_paged": len(paged),
            "hit3": sum(bool(r["rank"] and r["rank"] <= 3) for r in paged),
            "hit5": sum(bool(r["rank"]) for r in paged),
            "mrr": (sum(1 / r["rank"] for r in paged if r["rank"]) / len(paged)) if paged else None,
            "evid": sum(bool(r["evidence"]) for r in ret),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--mode", default="report")
    parser.add_argument("--pdf", type=Path, default=None, help="document to index (default: the mode's sample)")
    parser.add_argument("--questions", type=Path, default=None)
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between questions (rate limits)")
    parser.add_argument("--label", default=None, help="name for the results file and throwaway library "
                        "(default: the mode) - e.g. run Standard on the iMac report: "
                        "--mode standard --pdf samples/iMac_PER_Oct2024.pdf --questions eval/questions/visual.json --label standard-on-imac")
    args = parser.parse_args()

    pdf = args.pdf or config.ROOT / DEFAULT_SAMPLES[args.mode]
    questions = json.loads((args.questions or config.ROOT / "eval" / "questions" / f"{args.mode}.json").read_text())

    label = args.label or args.mode
    eval_dir = config.DATA_DIR / "eval" / label
    shutil.rmtree(eval_dir, ignore_errors=True)  # a fresh library every run
    embedder = CachedEmbedder()  # the real shared cache, so imported vectors are reused
    modes = Modes(eval_dir, embedder)
    engine, chat = modes.engine(args.mode), modes.chat(args.mode)
    profile = engine.profile

    before = embedder.cache_size()
    doc = engine.load_file(pdf.read_bytes(), pdf.name)
    new_embeddings = embedder.cache_size() - before
    print(f"indexed {pdf.name}: {doc['chunk_count']} chunks, {new_embeddings} new embeddings (rest from cache)\n")

    k = profile.retrieval_k
    rows = []
    for q in questions:
        reply = chat.ask(q["question"], [])
        text = reply["reply"].strip()
        refusal = bool(q.get("refusal") or q.get("expect_refusal"))
        gold = q.get("gold_pages", [])
        hits, pages, kinds, rank, evidence, paged, notes = [], [], [], None, None, False, []
        off_section = None
        if not refusal:
            # the same search the chat performs: the mode's filter first, then unfiltered if that
            # leaves nothing relevant (raw top-k here, before the relevance floor, for ranking)
            vector = engine.embed_query(q["question"])
            where, notes = profile.query_filter(q["question"], engine.store)
            hits = engine.store.similarity_search(vector, k, where)
            if where and not any(h["score"] >= profile.min_score for h in hits):
                hits, notes = engine.store.similarity_search(vector, k), [*notes, "filter matched nothing: unfiltered"]
            pages = [h["metadata"].get("page") for h in hits]
            paged = any(p is not None for p in pages)
            kinds = [h["metadata"].get("kind", "text") for h in hits]
            rank = next((i + 1 for i, p in enumerate(pages) if p in gold), None)
            groups = required_groups(q)
            context = norm(" ".join(h["text"] for h in hits if h["score"] >= profile.min_score))
            evidence = all(any(norm(alt) in context for alt in g) for g in groups) if groups else None
            if q.get("chapter") or q.get("region"):
                off_section = sum(
                    1 for h in hits
                    if (q.get("region") and h["metadata"].get("region") != q["region"])
                    or (q.get("chapter") and h["metadata"].get("chapter") != q["chapter"])
                )
        ok = judge(q, text, profile.refusal)
        rows.append(
            {"q": q, "id": q["id"], "type": q.get("type", "refusal" if refusal else "answer"), "refusal": refusal,
             "answer": text, "pass": ok, "rank": rank, "pages": pages, "kinds": kinds, "evidence": evidence,
             "paged": paged, "notes": notes, "off": off_section, "n_hits": len(hits), "ctx": reply.get("contextTokens", 0)}
        )
        print(f"[{'PASS' if ok else 'FAIL'}] {q['id']} {q['question']}\n   -> {text}\n   pages {pages} kinds {kinds} gold-rank {rank}\n")
        time.sleep(args.pause)

    summ = summarize(rows)
    core = [r for r in rows if r["q"].get("core")]
    ext = [r for r in rows if not r["q"].get("core") and not r["refusal"]]
    neg = [r for r in rows if r["refusal"]]
    allr = summ["ALL"]
    summary = (
        f"core {sum(r['pass'] for r in core)}/{len(core)}, extended {sum(r['pass'] for r in ext)}/{len(ext)}, "
        f"refusals {sum(r['pass'] for r in neg)}/{len(neg)}"
    )
    scoped = [r for r in rows if r["off"] is not None]
    ctx = [r["ctx"] for r in rows if r["ctx"]]
    if allr["n_paged"]:
        n = allr["n_paged"]
        summary += f"; hit@3 {allr['hit3'] / n:.2f}, hit@5 {allr['hit5'] / n:.2f}, MRR {allr['mrr']:.2f}"
    else:
        summary += "; page metrics n/a (this mode stores no pages)"
    extras = []
    if scoped:
        extras.append(f"questions with chunks from outside the asked-about chapter/region: {sum(bool(r['off']) for r in scoped)}/{len(scoped)}")
    if ctx:
        extras.append(f"context sent to the model: avg {sum(ctx) // len(ctx)} est. tokens (max {max(ctx)})")
    print(summary)
    for e in extras:
        print(e)

    md = [
        f"# Results - {profile.label} mode" + (f" ({label})" if label != args.mode else ""),
        "",
        f"Document: `{pdf.name}` ({doc['chunk_count']} chunks, {new_embeddings} newly embedded). Config: k={k}, min score {profile.min_score}, "
        f"temperature {profile.temperature}, chat `{config.CHAT_MODEL}`, embeddings `{config.EMBEDDING_MODEL}`.",
        "",
        f"**{summary}**",
        "",
        *[f"- {e}" for e in extras],
        *([""] if extras else []),
        "Answer correctness is an automatic substring check (a convenience); retrieval is the raw top-k before the "
        "relevance floor. Regenerate with `PYTHONPATH=. .venv/bin/python eval/run_eval.py " + " ".join(sys.argv[1:]) + "`.",
        "",
    ]
    types = [t for t in summ if t != "ALL"]
    if any("type" in r["q"] for r in rows):
        md += [
            "## By content type",
            "",
            "| Content type | n | answers correct | page hit@3 / hit@5 / MRR | evidence in context |",
            "|---|---|---|---|---|",
        ]
        for t in types + ["ALL"]:
            s = summ[t]
            ret = "n/a" if not s["n_paged"] else f"{s['hit3']}/{s['n_paged']} / {s['hit5']}/{s['n_paged']} / {s['mrr']:.2f}"
            evid = "-" if not s["n_ret"] else f"{s['evid']}/{s['n_ret']}"
            md.append(f"| {t} | {s['n']} | {s['pass']}/{s['n']} | {ret} | {evid} |")
        md.append("")
    md += ["## Per question", "", "| ID | Question | Answer | Pass | Gold rank | Retrieved (page, kind) | Filter |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        retrieved = list(zip(r["pages"], r["kinds"])) if r["pages"] else "-"
        md.append(
            f"| {r['id']} | {r['q']['question']} | {r['answer'].replace(chr(10), ' ').replace('|', '/')} | "
            f"{'yes' if r['pass'] else '**NO**'} | {r['rank'] or '-'} | {retrieved} | {', '.join(r['notes']) or '-'} |"
        )
    out = config.ROOT / "docs" / "results" / f"{label}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md) + "\n")
    print(f"wrote {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
