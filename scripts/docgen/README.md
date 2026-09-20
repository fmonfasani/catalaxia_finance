# DocGen (v2) — generador de documentos Word con la marca webshooks

Integra varios `.md` en un único **DOCX branded**, usando el sistema de marca de
`docs/webshooks/brand/` (tema + logos). Reproducible con un comando.

## Qué hace la v2

- **Portada** con el **logo** de webshooks + título/subtítulo/metadatos + regla naranja.
- **Índice de Word real** (campo TOC con números de página; se actualiza con F9).
- **Encabezados** navy/azul, **negrita/cursiva/`código`/links** inline (ya no se ven los `**`).
- **Tablas** con header navy + texto blanco + filas zebra + bordes.
- **Bloques de código** monoespaciados con fondo, **citas** con borde azul, **imágenes** embebidas.
- **Footer** `webshooks.com` + número de página, con línea superior.
- Toma la marca de **`docs/webshooks/brand/theme_webshooks.json`** (colores/fuente) y los logos.

## Uso

```bash
python build.py \
  --input "docs/proyecto/*.md" "docs/proyecto/jira/*.md" \
  --output "docs/proyecto/Manual_Catalaxia_docgen.docx" \
  --title "Proyecto Catalaxia Screener" \
  --subtitle "Documentación interna del proyecto · webshooks → Catalaxia" \
  --meta "Cliente: Catalaxia S.A. · Julio 2026 · v1.0"
```

- `--input` — uno o más patrones/globs de `.md` (se ordenan por nombre).
- `--title / --subtitle / --meta` — la portada.
- `--theme` — por defecto usa el **tema de marca webshooks**; se puede pasar otro `.json`.
- `--ppt` — **opcional**: solo si querés que extraiga el tema de un `.pptx` en vez del tema fijo.

Al abrir el DOCX, actualizá el índice: **clic derecho sobre él → Actualizar campos (F9)**.

## Cómo está armado (para tocarlo)

```
build.py                         CLI + orquestación
src/docgen/
  theme/theme_manager.py         load_or_extract(): usa el tema de marca fijo o lo extrae del pptx
  parser/markdown_parser.py      .md -> bloques (heading/párrafo/tabla/lista/cita/código/imagen/hrule)
  renderer/inline.py             formato inline (negrita/cursiva/código/link)
  renderer/markdown_renderer.py  bloques -> Word aplicando el tema (tablas, código, imágenes)
  word/docx_builder.py           portada + índice + footer + ensamblado
```

Requisitos: `python-docx`, `python-pptx`, `Pillow`, `Pygments` (ver `requirements.txt`).

## Estado

- ✅ v2: portada/logo, índice real, footer, tablas branded, formato inline. **Genera documentos pulidos.**
- 🔜 Próximo: componentes (timeline/pipeline/flujo) y plantillas por tipo de documento (Fase 3–4 del brand-kit).
