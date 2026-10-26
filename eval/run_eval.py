"""Evaluate a mode against its question set, through the same path the UI uses.

  PYTHONPATH=. .venv/bin/python eval/run_eval.py --mode report

Indexes the sample document into a throwaway library (data/eval/<mode>/ - never
your real one), asks every question via the mode's ChatSession, and writes
docs/results/<mode>.md. Embeddings come from the shared cache, so a document
whose vectors were imported (scripts/import_cache.py) costs no embedding calls.

Answer correctness is an automatic check (every must_contain group needs one of
its strings in the answer) - a convenience; read the printed answers to judge for
real. Retrieval is scored on the raw top-k, before the relevance floor.
"""

import argparse
import json
import shutil
import time
from pathlib import Path

from app import config
from app.embeddings import CachedEmbedder
from app.modes import Modes

DEFAULT_SAMPLES = {"report": "samples/GPO-Anual-report.pdf"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--mode", default="report")
    parser.add_argument("--pdf", type=Path, default=None, help="document to index (default: the mode's sample)")
    parser.add_argument("--questions", type=Path, default=None)
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between questions (rate limits)")
    args = parser.parse_args()

    pdf = args.pdf or config.ROOT / DEFAULT_SAMPLES[args.mode]
    questions = json.loads((args.questions or config.ROOT / "eval" / "questions" / f"{args.mode}.json").read_text())

    eval_dir = config.DATA_DIR / "eval" / args.mode
    shutil.rmtree(eval_dir, ignore_errors=True)  # a fresh library every run
    embedder = CachedEmbedder()  # the real shared cache, so imported vectors are reused
    modes = Modes(eval_dir, embedder)
    engine = modes.engine(args.mode)
    chat = modes.chat(args.mode)
    profile = engine.profile

    before = embedder.cache_size()
    doc = engine.load_file(pdf.read_bytes(), pdf.name)
    new_embeddings = embedder.cache_size() - before
    print(f"indexed {pdf.name}: {doc['chunk_count']} chunks, {new_embeddings} new embeddings (rest from cache)\n")

    k = profile.retrieval_k
    rows, ranks = [], []
    for q in questions:
        reply = chat.ask(q["question"], [])
        text = reply["reply"].strip()
        pages = []
        rank = None
        if q.get("refusal"):
            ok = text.startswith(profile.refusal)
        else:
            ok = all(any(s.lower() in text.lower() for s in group) for group in q["must_contain"])
            hits = engine.store.similarity_search(engine.embed_query(q["question"]), k)
            pages = [h["metadata"].get("page") for h in hits]
            rank = next((i + 1 for i, p in enumerate(pages) if p in q["gold_pages"]), None)
            ranks.append(rank)
        rows.append((q, text, ok, rank, pages))
        print(f"[{'PASS' if ok else 'FAIL'}] {q['id']} {q['question']}\n   -> {text}\n   pages {pages} gold-rank {rank}\n")
        time.sleep(args.pause)

    def hit(n):
        return sum(1 for r in ranks if r and r <= n) / len(ranks) if ranks else 0.0

    mrr = sum(1 / r for r in ranks if r) / len(ranks) if ranks else 0.0
    core = [r for r in rows if r[0].get("core")]
    ext = [r for r in rows if not r[0].get("core") and not r[0].get("refusal")]
    neg = [r for r in rows if r[0].get("refusal")]
    summary = (
        f"core {sum(r[2] for r in core)}/{len(core)}, extended {sum(r[2] for r in ext)}/{len(ext)}, "
        f"refusals {sum(r[2] for r in neg)}/{len(neg)}; hit@3 {hit(3):.2f}, hit@5 {hit(5):.2f}, MRR {mrr:.2f}"
    )
    print(summary)

    md = [
        f"# Results - {profile.label} mode",
        "",
        f"Document: `{pdf.name}` ({doc['chunk_count']} chunks). Config: k={k}, min score {profile.min_score}, "
        f"temperature {profile.temperature}, chat `{config.CHAT_MODEL}`, embeddings `{config.EMBEDDING_MODEL}`.",
        "",
        f"**{summary}**",
        "",
        "Answer correctness is an automatic substring check (a convenience); retrieval is the raw top-k before the "
        "relevance floor. Regenerate with `PYTHONPATH=. .venv/bin/python eval/run_eval.py --mode " + args.mode + "`.",
        "",
        "| ID | Question | Answer | Pass | Gold rank | Retrieved pages |",
        "|---|---|---|---|---|---|",
    ]
    for q, text, ok, rank, pages in rows:
        md.append(
            f"| {q['id']} | {q['question']} | {text.replace(chr(10), ' ').replace('|', '/')} | "
            f"{'yes' if ok else '**NO**'} | {rank or '-'} | {pages or '-'} |"
        )
    out = config.ROOT / "docs" / "results" / f"{args.mode}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md) + "\n")
    print(f"wrote {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
