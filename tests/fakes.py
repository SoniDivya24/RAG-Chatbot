"""Deterministic stand-ins for the embedding API, shared by the offline tests."""

import hashlib
import math
import re

FAKE_DIM = 64


def fake_vector(text: str) -> list[float]:
    """Bag-of-words embedding (hashing trick): similar wording gives similar
    vectors, so retrieval order is meaningful without any API call."""
    vec = [0.0] * FAKE_DIM
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % FAKE_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
