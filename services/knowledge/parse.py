"""Reads a manual into pages, then into a section and leaf hierarchy."""

import re
from dataclasses import dataclass, field
from pathlib import Path

PAGE_MARK = re.compile(r"<!--\s*page\s+(\d+)\s*-->")
MD_HEADING = re.compile(r"^#{2,4}\s+(\d+(?:\.\d+)*)\s+(.+)$")
PDF_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s+([A-Z][^|]{2,70})$")


@dataclass
class Leaf:
    section: str
    title: str
    page: int
    lines: list[str] = field(default_factory=list)

    @property
    def body(self) -> str:
        return "\n".join(line for line in self.lines if line.strip()).strip()


@dataclass
class Section:
    section: str
    title: str
    page: int
    leaves: list[Leaf] = field(default_factory=list)


def read_pages(path: Path) -> list[tuple[int, str]]:
    if path.suffix.lower() == ".pdf":
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return [(i + 1, page.extract_text() or "") for i, page in enumerate(pdf.pages)]
    return split_markdown(path.read_text())


def split_markdown(text: str) -> list[tuple[int, str]]:
    parts = PAGE_MARK.split(text)
    if len(parts) == 1:
        return [(1, text)]
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]


def hierarchy(pages: list[tuple[int, str]]) -> list[Section]:
    sections: list[Section] = []
    leaf: Leaf | None = None
    for page, text in pages:
        for line in text.splitlines():
            match = MD_HEADING.match(line) or PDF_HEADING.match(line.strip())
            if not match:
                if leaf:
                    leaf.lines.append(line)
                elif sections:
                    leaf = Leaf(sections[-1].section, sections[-1].title, page, [line])
                    sections[-1].leaves.append(leaf)
                continue
            number, title = match.group(1), match.group(2).strip()
            if "." not in number:
                sections.append(Section(number, title, page))
                leaf = None
            elif sections:
                leaf = Leaf(number, title, page)
                sections[-1].leaves.append(leaf)
    return [s for s in sections if s.leaves]
