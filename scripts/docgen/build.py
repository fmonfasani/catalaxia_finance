from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from docgen.word.docx_builder import WordDocumentBuilder

# Tema de marca fijo (webshooks). Si existe, se usa; si no, docgen lo extrae del pptx.
BRAND_THEME = (ROOT / ".." / ".." / "docs" / "webshooks" / "brand" / "theme_webshooks.json").resolve()


def build_document(pptx_path, input_patterns, output_path, theme_path,
                   title="Documento", subtitle="", meta="") -> Path:
    markdown_files = WordDocumentBuilder.collect_markdown_files(input_patterns)
    if not markdown_files:
        raise FileNotFoundError("No se encontraron archivos Markdown válidos en el patrón indicado.")
    builder = WordDocumentBuilder(theme_path)
    return builder.build(pptx_path, markdown_files, output_path, title=title, subtitle=subtitle, meta=meta)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de documentación técnica a DOCX (webshooks)")
    parser.add_argument("--ppt", required=False, default=None,
                        help="PowerPoint del que extraer el tema (opcional si se usa el tema de marca)")
    parser.add_argument("--input", nargs="+", required=True,
                        help="Uno o más patrones Markdown, p.ej. docs/proyecto/*.md")
    parser.add_argument("--output", required=True, help="Ruta del DOCX resultante")
    parser.add_argument("--theme", default=str(BRAND_THEME),
                        help="Ruta al tema (por defecto el tema de marca webshooks)")
    parser.add_argument("--title", default="Documento", help="Título de la portada")
    parser.add_argument("--subtitle", default="", help="Subtítulo de la portada")
    parser.add_argument("--meta", default="", help="Línea de metadatos (cliente/fecha)")
    args = parser.parse_args()

    output = build_document(args.ppt, args.input, args.output, args.theme,
                            title=args.title, subtitle=args.subtitle, meta=args.meta)
    print(f"Documento generado: {output}")


if __name__ == "__main__":
    main()
