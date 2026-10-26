"""Seed the embedding cache from vectors another project already computed, so
indexing a document those vectors cover costs no embedding calls.

The Gemini free tier allows only ~1000 embeddings a day, and the three
prototype repos (see ../CLAUDE.md) already embedded the reference documents.
Sources are only ever read: a Chroma index is copied to a temp folder first,
because merely opening one can write to it.
"""

import json
import shutil
import tempfile
from pathlib import Path

import chromadb
from chromadb.config import Settings

from app.embeddings import CachedEmbedder


def import_chroma(index_dir: Path, embedder: CachedEmbedder, collection: str | None = None) -> int:
    """Import every (document text, embedding) pair of a Chroma collection.

    Only valid when the collection stored exactly the text it embedded - true
    for a plain page-chunk index, not for one that embedded "heading + text".
    """
    index_dir = Path(index_dir)
    if not index_dir.is_dir():
        raise FileNotFoundError(f"No Chroma index at {index_dir}")

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "index"
        shutil.copytree(index_dir, copy)
        client = chromadb.PersistentClient(
            path=str(copy), settings=Settings(anonymized_telemetry=False)
        )
        names = [c.name if hasattr(c, "name") else str(c) for c in client.list_collections()]
        if collection is None:
            if len(names) != 1:
                raise ValueError(f"Pass a collection name; the index has: {names}")
            collection = names[0]
        data = client.get_collection(collection).get(include=["documents", "embeddings"])

    return embedder.add_texts(
        list(data["documents"]), [list(map(float, v)) for v in data["embeddings"]]
    )


def import_json_cache(path: Path, embedder: CachedEmbedder) -> int:
    """Import a {key: vector} JSON cache whose keys are sha256("<model>\\n<text>")
    - the scheme this app and the prototypes share."""
    raw = json.loads(Path(path).read_text())
    return embedder.add_keyed({k: [float(x) for x in v] for k, v in raw.items()})
