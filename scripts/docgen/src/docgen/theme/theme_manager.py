from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN


@dataclass
class ThemeFile:
    fonts: dict[str, str] = field(default_factory=dict)
    colors: dict[str, str] = field(default_factory=dict)
    tables: dict[str, Any] = field(default_factory=dict)
    headings: dict[str, Any] = field(default_factory=dict)
    footer: dict[str, Any] = field(default_factory=dict)
    header: dict[str, Any] = field(default_factory=dict)
    logo: dict[str, str] = field(default_factory=dict)
    images: dict[str, Any] = field(default_factory=dict)


class ThemeManager:
    """Extracts reusable visual identity from a PowerPoint file."""

    def __init__(self, theme_file: Path | str):
        self.theme_file = Path(theme_file)
        self.theme: dict[str, Any] = self._default_theme()

    def _default_theme(self) -> dict[str, Any]:
        return {
            "fonts": {
                "primary": "Aptos",
                "secondary": "Calibri",
                "title": "Aptos",
                "body": "Aptos",
            },
            "colors": {
                "primary": "#123C78",
                "secondary": "#4C88D8",
                "tertiary": "#E8EFFC",
                "title": "#1E1E1E",
                "links": "#0B5FFF",
                "code": "#F5F5F5",
                "highlight": "#FFF2CC",
                "table_header": "#123C78",
                "table_text": "#1E1E1E",
                "header": "#123C78",
                "footer": "#4C4C4C",
                "box": "#EAF0FF",
                "background": "#FFFFFF",
            },
            "tables": {
                "header_fill": "#123C78",
                "header_font": "#FFFFFF",
                "border": "#B7C6EA",
                "autofit": True,
            },
            "headings": {
                "h1": {"size": 24, "bold": True, "color": "#123C78"},
                "h2": {"size": 18, "bold": True, "color": "#1E1E1E"},
                "h3": {"size": 14, "bold": True, "color": "#123C78"},
            },
            "header": {"logo": True, "project_name": "Proyecto", "chapter": "Documento"},
            "footer": {"page_number": True, "doc_name": "Manual", "version": "v1.0"},
            "logo": {"path": "", "variant": "default"},
            "images": {},
        }

    def extract_from_pptx(self, pptx_path: str | Path) -> dict[str, Any]:
        pres = Presentation(Path(pptx_path))
        all_text_runs: list[str] = []
        color_counter: Counter[str] = Counter()
        font_counter: Counter[str] = Counter()

        for slide in pres.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        for run in paragraph.runs:
                            if run.text.strip():
                                all_text_runs.append(run.text.strip())
                                if run.font.name:
                                    font_counter[run.font.name] += 1
                                    if run.font.color and run.font.color.type == 1:
                                        color_hex = self._normalize_color(run.font.color.rgb)
                                        if color_hex:
                                            color_counter[color_hex] += 1

                if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.AUTO_SHAPE:
                    fill_color = self._shape_fill_color(shape)
                    if fill_color:
                        color_counter[fill_color] += 1

        primary = self._pick_most_common(color_counter) or self._default_theme()["colors"]["primary"]
        fonts = {
            "primary": self._pick_most_common(font_counter) or "Aptos",
            "secondary": "Calibri",
            "title": self._pick_most_common(font_counter) or "Aptos",
            "body": self._pick_most_common(font_counter) or "Aptos",
        }

        theme = self._default_theme()
        theme["fonts"] = fonts
        theme["colors"]["primary"] = primary
        theme["colors"]["secondary"] = self._derive_secondary(primary)
        theme["colors"]["tertiary"] = self._tint(primary, 0.85)
        theme["colors"]["links"] = self._derive_link_color(primary)
        theme["colors"]["table_header"] = primary
        theme["colors"]["header"] = primary
        theme["colors"]["footer"] = self._darken(primary, 0.45)
        theme["colors"]["code"] = self._default_theme()["colors"]["code"]
        theme["colors"]["box"] = self._tint(primary, 0.92)
        theme["colors"]["highlight"] = self._default_theme()["colors"]["highlight"]
        theme["images"] = {}
        self.theme = theme
        self.save_theme()
        return theme

    def save_theme(self) -> None:
        self.theme_file.parent.mkdir(parents=True, exist_ok=True)
        self.theme_file.write_text(json.dumps(self.theme, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_theme(self) -> dict[str, Any]:
        if self.theme_file.exists():
            self.theme = json.loads(self.theme_file.read_text(encoding="utf-8"))
        return self.theme

    def load_or_extract(self, pptx_path: str | Path | None = None) -> dict[str, Any]:
        """Si hay un tema de marca fijo (con 'brand'/'headings'), lo usa. Si no, lo extrae del pptx."""
        if self.theme_file.exists():
            data = json.loads(self.theme_file.read_text(encoding="utf-8"))
            if "brand" in data or ("headings" in data and "cover" in data):
                data["_base"] = str(self.theme_file.parent)
                self.theme = data
                return data
        return self.extract_from_pptx(pptx_path)

    @staticmethod
    def _pick_most_common(counter: Counter[str]) -> str | None:
        if not counter:
            return None
        return counter.most_common(1)[0][0]

    @staticmethod
    def _shape_fill_color(shape: Any) -> str | None:
        try:
            fill = shape.fill
        except Exception:
            return None
        if fill and fill.fore_color.type == 1 and fill.fore_color.rgb:
            return ThemeManager._normalize_color(fill.fore_color.rgb)
        return None

    @staticmethod
    def _normalize_color(color_value: Any) -> str | None:
        if isinstance(color_value, str):
            return color_value if color_value.startswith("#") else f"#{color_value}"
        if hasattr(color_value, "rgb"):
            rgb = getattr(color_value, "rgb")
            if isinstance(rgb, tuple) and len(rgb) == 3:
                return f"#{''.join(f'{channel:02X}' for channel in rgb)}"
        return None

    @staticmethod
    def _derive_secondary(primary: str) -> str:
        return primary if primary else "#4C88D8"

    @staticmethod
    def _derive_link_color(primary: str) -> str:
        return primary if primary else "#0B5FFF"

    @staticmethod
    def _tint(hex_color: str, factor: float) -> str:
        return ThemeManager._shift_hex(hex_color, factor)

    @staticmethod
    def _darken(hex_color: str, factor: float) -> str:
        return ThemeManager._shift_hex(hex_color, -factor)

    @staticmethod
    def _shift_hex(hex_color: str, factor: float) -> str:
        if not hex_color:
            return "#FFFFFF"
        if isinstance(hex_color, tuple):
            hex_color = f"#{''.join(f'{channel:02X}' for channel in hex_color)}"
        if not isinstance(hex_color, str):
            return "#FFFFFF"
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            return "#FFFFFF"
        channels = [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]
        output = []
        for channel in channels:
            adjusted = int(channel + (255 - channel) * factor if factor >= 0 else channel * (1 + factor))
            output.append(f"{max(0, min(255, adjusted)):02X}")
        return f"#{''.join(output)}"
