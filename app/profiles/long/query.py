"""Question -> metadata filter. Conservative: a wrong filter hides the answer, so a region is applied
only when exactly one region is named, and a chapter only when explicitly named.

The words that mean something (regions, their aliases, chapter titles, named front sections) come
from a per-document vocabulary stored with the document - the reference report ships a rich one
(countries per region), other documents get whatever their outline reveals.
"""

import re
from dataclasses import dataclass, field

_CHAPTER_RE = re.compile(r"\bchapter\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", re.I)
_WORD_NUM = {w: i for i, w in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"])}
_EXEC_SUMMARY = re.compile(r"\bexecutive summary\b", re.I)


@dataclass
class Vocabulary:
    chapters: dict[int, str] = field(default_factory=dict)
    regions: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)  # lower-case name / country -> region
    named_sections: dict[str, str] = field(default_factory=dict)  # "executive summary" -> its heading path

    def to_json(self) -> dict:
        return {
            "chapters": {str(k): v for k, v in self.chapters.items()},
            "regions": self.regions,
            "aliases": self.aliases,
            "named_sections": self.named_sections,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Vocabulary":
        return cls(
            {int(k): v for k, v in data.get("chapters", {}).items()},
            data.get("regions", []),
            data.get("aliases", {}),
            data.get("named_sections", {}),
        )

    @classmethod
    def merge(cls, vocabularies: list["Vocabulary"]) -> "Vocabulary":
        out = cls()
        for v in vocabularies:
            out.chapters.update(v.chapters)
            out.regions += [r for r in v.regions if r not in out.regions]
            out.aliases.update(v.aliases)
            out.named_sections.update(v.named_sections)
        return out


@dataclass
class QueryFilter:
    region: str | None = None
    chapter: int | None = None
    section_path: str | None = None  # an exact heading path, e.g. the executive summary
    bad_chapter: int | None = None  # a chapter the document does not have (e.g. "Chapter 7")
    notes: list[str] = field(default_factory=list)

    @property
    def where(self) -> dict | None:
        conds = []
        if self.region:
            conds.append({"region": self.region})
        if self.chapter:
            conds.append({"chapter": self.chapter})
        if self.section_path:
            conds.append({"heading_path": self.section_path})
        if not conds:
            return None
        return conds[0] if len(conds) == 1 else {"$and": conds}


def understand(question: str, vocab: Vocabulary) -> QueryFilter:
    f = QueryFilter()
    if vocab.aliases:
        pattern = re.compile(
            r"(?<![\w-])(" + "|".join(sorted(map(re.escape, vocab.aliases), key=len, reverse=True)) + r")(?![\w-])", re.I
        )
        regions = {vocab.aliases[m.group(1).lower()] for m in pattern.finditer(question)}
        if len(regions) == 1:
            f.region = regions.pop()
            f.notes.append(f"region={f.region}")
        elif len(regions) > 1:
            f.notes.append("several regions named: no region filter")

    m = _CHAPTER_RE.search(question)
    if m and vocab.chapters:
        n = _WORD_NUM.get(m.group(1).lower()) or int(m.group(1))
        if n in vocab.chapters:
            if f.region and n != 2:
                f.region = None  # "Chapter 3 ... India": the chapter wins, drop the region
            f.chapter = n
            f.notes.append(f"chapter={n}")
        else:
            f.bad_chapter = n

    if not f.region and not f.chapter:
        for name, path in vocab.named_sections.items():
            if re.search(rf"\b{re.escape(name)}\b", question, re.I):
                f.section_path = path
                f.notes.append(name)
                break
    return f
