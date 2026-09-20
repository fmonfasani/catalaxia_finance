from __future__ import annotations

from pathlib import Path

from docx import Document

from docgen.theme import ThemeManager
from docgen.word.docx_builder import WordDocumentBuilder


REPO_ROOT = Path(__file__).resolve().parents[3]
PPTX_PATH = REPO_ROOT / "docs" / "proyecto" / "Propuesta_webshooks_Catalaxia_v4.pptx"
MD_PATHS = [
    REPO_ROOT / "docs" / "proyecto" / "00_INDICE_Y_PLAN.md",
    REPO_ROOT / "docs" / "proyecto" / "01_ALCANCE_Y_DOD.md",
]


def test_extract_theme_from_powerpoint(tmp_path: Path) -> None:
    theme_path = tmp_path / "theme.json"
    manager = ThemeManager(theme_path)
    theme = manager.extract_from_pptx(PPTX_PATH)

    assert theme["fonts"]["primary"]
    assert theme["colors"]["primary"]
    assert theme_path.exists()


def test_build_document_creates_docx(tmp_path: Path) -> None:
    theme_path = tmp_path / "theme.json"
    output_path = tmp_path / "manual.docx"

    manager = ThemeManager(theme_path)
    manager.extract_from_pptx(PPTX_PATH)

    builder = WordDocumentBuilder(theme_path)
    built_path = builder.build(PPTX_PATH, MD_PATHS, output_path)

    assert built_path.exists()
    document = Document(built_path)
    assert len(document.paragraphs) >= 3
