"""Repair text-extraction artifacts: ligature glyphs, soft hyphens, line-end hyphens."""

import re

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}
_HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\n(?=[a-z])")


def repair(text: str) -> str:
    for src, dst in _LIGATURES.items():
        text = text.replace(src, dst)
    text = text.replace("­", "").replace("\t", " ")
    return _HYPHEN_BREAK.sub("", text)
