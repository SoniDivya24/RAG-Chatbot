from dataclasses import dataclass


@dataclass
class Section:
    chapter: int | None  # 1-n, or None for front matter / appendix / documents without chapters
    chapter_title: str
    region: str | None
    kind: str  # body | box | annex | references | front | appendix | table
    path: tuple[str, ...]  # heading path, top level first
    segments: list[tuple[int, str]]  # (PDF page, repaired text of this section on that page)
    header: str = ""  # kind == "table": caption + subtitle + column-header rows, repeated on every chunk

    @property
    def pages(self) -> list[int]:
        return [p for p, _ in self.segments]

    @property
    def text(self) -> str:
        return "\n".join(t for _, t in self.segments)

    @property
    def heading_path(self) -> str:
        return " > ".join(self.path)
