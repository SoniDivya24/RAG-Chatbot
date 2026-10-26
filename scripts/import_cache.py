"""Seed the local embedding cache from a prototype repo's stored embeddings.

  PYTHONPATH=. .venv/bin/python scripts/import_cache.py chroma ../RAG-GPO-Annual-Report/data/index
  PYTHONPATH=. .venv/bin/python scripts/import_cache.py json   ../RAG-World-Bank-Economic-Report/data/embedding_cache.json

Writes to data/embedding_cache.sqlite (override the folder with DATA_DIR).
"""

import argparse
from pathlib import Path

from app.cache_import import import_chroma, import_json_cache
from app.embeddings import CachedEmbedder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="kind", required=True)
    chroma = sub.add_parser("chroma", help="a Chroma index whose documents are the embedded texts")
    chroma.add_argument("path", type=Path)
    chroma.add_argument("--collection", default=None)
    json_cmd = sub.add_parser("json", help="a {key: vector} JSON cache")
    json_cmd.add_argument("path", type=Path)
    args = parser.parse_args()

    embedder = CachedEmbedder()
    before = embedder.cache_size()
    if args.kind == "chroma":
        stored = import_chroma(args.path, embedder, args.collection)
    else:
        stored = import_json_cache(args.path, embedder)
    print(f"imported {stored} vectors; cache {before} -> {embedder.cache_size()} entries at {embedder.cache_path}")


if __name__ == "__main__":
    main()
