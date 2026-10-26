"""Repair text-extraction artifacts: ligature glyphs, line-end hyphens and - only for documents that
show the defect - the "Th" ligature losing its "h" ("Te" for "The")."""

import re

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}

# Words whose "Th" ligature came out as a bare "T". Only unambiguous non-words / known mappings.
_TH_WORDS = {
    "Te": "The", "Tis": "This", "Tese": "These", "Tey": "They", "Tat": "That", "Teir": "Their",
    "Tere": "There", "Tird": "Third", "Trough": "Through", "Tose": "Those", "Tus": "Thus",
    "Tough": "Though", "Tree": "Three", "Teory": "Theory", "Tan": "Than", "Tem": "Them",
    "Ten": "Then", "Teo": "Theo",
}
# These can be real words, so they are left alone.
_AMBIGUOUS = {"Tan", "Ten", "Tree", "Tough", "Trough", "Tem", "Teo"}
_TH_RE = re.compile(r"\b(" + "|".join(sorted(_TH_WORDS, key=len, reverse=True)) + r")\b")
_HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\n(?=[a-z])")

# A document has the defect when "Te" shows up like a word and "The" is rarer than it.
_MIN_DAMAGE_SIGNS = 10


def has_th_damage(sample: str) -> bool:
    bare = len(re.findall(r"\bTe\b", sample))
    return bare >= _MIN_DAMAGE_SIGNS and bare > len(re.findall(r"\bThe\b", sample))


def fix_ligatures(text: str) -> str:
    for src, dst in _LIGATURES.items():
        text = text.replace(src, dst)
    return text.replace("7T_", "Th")


def fix_th(text: str) -> str:
    return _TH_RE.sub(lambda m: m.group(1) if m.group(1) in _AMBIGUOUS else _TH_WORDS[m.group(1)], text)


def join_hyphenated(text: str) -> str:
    """'coordina-\\ncion' -> 'coordination'. Only lowercase-to-lowercase breaks are joined."""
    return _HYPHEN_BREAK.sub("", text)


def repair(text: str, th_damaged: bool = False) -> str:
    text = fix_ligatures(text)
    if th_damaged:
        text = fix_th(text)
    return join_hyphenated(text)
