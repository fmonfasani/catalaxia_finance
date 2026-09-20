from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Seg:
    """Un fragmento de texto con su formato inline."""
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    link: bool = False


# **bold** | __bold__ | `code` | *italic* | _italic_ | [texto](url)
_PAT = re.compile(
    r"(\*\*(.+?)\*\*|__(.+?)__|`([^`]+?)`|\*(.+?)\*|(?<!\w)_(.+?)_(?!\w)|\[(.+?)\]\((.+?)\))"
)


def parse_inline(text: str) -> list[Seg]:
    """Convierte texto Markdown en segmentos con formato (negrita, cursiva, código, link)."""
    if not text:
        return [Seg("")]
    segs: list[Seg] = []
    i = 0
    for m in _PAT.finditer(text):
        if m.start() > i:
            segs.append(Seg(text[i:m.start()]))
        g = m.group(0)
        if g.startswith("**") or g.startswith("__"):
            segs.append(Seg(m.group(2) or m.group(3), bold=True))
        elif g.startswith("`"):
            segs.append(Seg(m.group(4), code=True))
        elif g.startswith("["):
            segs.append(Seg(m.group(7), link=True))
        else:  # *italic* o _italic_
            segs.append(Seg(m.group(5) or m.group(6), italic=True))
        i = m.end()
    if i < len(text):
        segs.append(Seg(text[i:]))
    return segs or [Seg(text)]
