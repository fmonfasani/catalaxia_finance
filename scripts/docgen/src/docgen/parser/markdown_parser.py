from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MarkdownBlock:
    type: str
    level: int | None = None
    text: str | None = None
    rows: list[list[str]] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    language: str | None = None


@dataclass
class MarkdownDocument:
    source: Path
    blocks: list[MarkdownBlock] = field(default_factory=list)


class MarkdownParser:
    """Parses a Markdown file into simple editorial blocks for Word rendering."""

    def __init__(self) -> None:
        self._heading_re = re.compile(r"^(#{1,6})\s+(.*)$")
        self._heading_attr_re = re.compile(r"\s*\{[^}]*\}\s*$")
        self._bullet_re = re.compile(r"^\s*[-*]\s+(.*)$")
        self._ordered_re = re.compile(r"^\s*\d+\.\s+(.*)$")
        self._quote_re = re.compile(r"^\s*>\s?(.*)$")
        self._table_split_re = re.compile(r"\s*\|\s*")
        self._image_re = re.compile(r"!\[(.*?)\]\((.*?)\)")

    def parse_file(self, source: str | Path) -> MarkdownDocument:
        path = Path(source)
        text = path.read_text(encoding="utf-8")
        return self.parse_text(text, path)

    def parse_text(self, text: str, source: Path | None = None) -> MarkdownDocument:
        lines = text.splitlines()
        blocks: list[MarkdownBlock] = []
        index = 0

        while index < len(lines):
            line = lines[index].rstrip()
            if not line.strip():
                index += 1
                continue

            if line.startswith("```"):
                language = line.replace("```", "").strip() or None
                code_lines: list[str] = []
                index += 1
                while index < len(lines) and not lines[index].startswith("```"):
                    code_lines.append(lines[index])
                    index += 1
                if index < len(lines):
                    index += 1
                blocks.append(MarkdownBlock(type="code", language=language, text="\n".join(code_lines)))
                continue

            heading = self._heading_re.match(line)
            if heading:
                level = len(heading.group(1))
                htext = self._heading_attr_re.sub("", heading.group(2).strip())
                blocks.append(MarkdownBlock(type="heading", level=level, text=htext))
                index += 1
                continue

            if self._is_table(lines, index):
                # junta TODAS las filas de la tabla (header + separador + cuerpo)
                table_lines = []
                while index < len(lines) and "|" in lines[index] and lines[index].strip():
                    table_lines.append(lines[index].strip())
                    index += 1
                blocks.append(self._parse_table(table_lines))
                continue

            if re.match(r"^(-{3,}|\*{3,}|_{3,})$", line.strip()):
                blocks.append(MarkdownBlock(type="hrule"))
                index += 1
                continue

            quote = self._quote_re.match(line)
            if quote:
                quote_lines = [quote.group(1).strip()]
                index += 1
                while index < len(lines) and self._quote_re.match(lines[index].rstrip()):
                    quote_lines.append(self._quote_re.match(lines[index].rstrip()).group(1).strip())
                    index += 1
                blocks.append(MarkdownBlock(type="quote", text="\n".join(quote_lines)))
                continue

            bullet = self._bullet_re.match(line)
            if bullet:
                items = [bullet.group(1).strip()]
                index += 1
                while index < len(lines) and self._bullet_re.match(lines[index].rstrip()):
                    items.append(self._bullet_re.match(lines[index].rstrip()).group(1).strip())
                    index += 1
                blocks.append(MarkdownBlock(type="bullet_list", items=items))
                continue

            ordered = self._ordered_re.match(line)
            if ordered:
                items = [ordered.group(1).strip()]
                index += 1
                while index < len(lines) and self._ordered_re.match(lines[index].rstrip()):
                    items.append(self._ordered_re.match(lines[index].rstrip()).group(1).strip())
                    index += 1
                blocks.append(MarkdownBlock(type="ordered_list", items=items))
                continue

            image = self._image_re.search(line)
            if image:
                blocks.append(MarkdownBlock(type="image", text=image.group(2).strip()))
                index += 1
                continue

            paragraph_lines = [line]
            index += 1
            while index < len(lines) and lines[index].strip() and not self._heading_re.match(lines[index].rstrip()) and not self._is_table(lines, index) and not self._quote_re.match(lines[index].rstrip()) and not self._bullet_re.match(lines[index].rstrip()) and not self._ordered_re.match(lines[index].rstrip()) and not lines[index].startswith("```"):
                paragraph_lines.append(lines[index].strip())
                index += 1
            blocks.append(MarkdownBlock(type="paragraph", text=" ".join(part for part in paragraph_lines if part)))

        return MarkdownDocument(source=source or Path("<memory>"), blocks=blocks)

    def _is_table(self, lines: list[str], idx: int) -> bool:
        if idx >= len(lines):
            return False
        line = lines[idx].strip()
        if not line or "|" not in line:
            return False
        separator = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
        return separator.startswith("---") or separator.startswith("|---")

    def _parse_table(self, table_lines: list[str]) -> MarkdownBlock:
        header = [cell.strip() for cell in self._table_split_re.split(table_lines[0].strip().strip("|").strip()) if cell]
        rows: list[list[str]] = []
        for row_line in table_lines[2:]:
            row = [cell.strip() for cell in self._table_split_re.split(row_line.strip().strip("|").strip()) if cell]
            rows.append(row)
        return MarkdownBlock(type="table", text="", rows=[header, *rows])
