# -*- coding: utf-8 -*-
"""Genera el Manual de Operaciones de Catalaxia en un solo documento con la marca
webshooks: portada + índice + las 18 Partes (I a XVIII), en tres formatos:

  python build_manual_docx.py
    -> docs/manual/Catalaxia_Manual_de_Operaciones.docx  (Word, TOC automático, footer)
    -> docs/manual/Catalaxia_Manual_de_Operaciones.html  (abre en cualquier navegador)
    -> docs/manual/Catalaxia_Manual_de_Operaciones.odt   (Word/LibreOffice)

Requiere: python-docx + pandoc (webshooks_docx.py hace el estilo de Word).
"""
import os, sys, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "webshooks", "brand-kit"))
import webshooks_docx as ws

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DOCX = os.path.join(HERE, "Catalaxia_Manual_de_Operaciones.docx")
OUT_HTML = os.path.join(HERE, "Catalaxia_Manual_de_Operaciones.html")
OUT_ODT  = os.path.join(HERE, "Catalaxia_Manual_de_Operaciones.odt")
COMBINED = os.path.join(HERE, "_combined_manual.md")

ORDER = ["MANUAL_PART_I.md", "MANUAL_PART_II.md", "MANUAL_PART_III.md", "MANUAL_PART_IV.md",
         "MANUAL_PART_V.md", "MANUAL_PART_VI.md", "MANUAL_PART_VII.md", "MANUAL_PART_VIII.md",
         "MANUAL_PART_IX.md", "MANUAL_PART_X.md", "MANUAL_PART_XI.md", "MANUAL_PART_XII.md",
         "MANUAL_PART_XIII.md", "MANUAL_PART_XIV.md", "MANUAL_PART_XV.md", "MANUAL_PART_XVI.md",
         "MANUAL_PART_XVII.md", "MANUAL_PART_XVIII.md",
         "MANUAL_PART_XIX.md", "MANUAL_PART_XX.md", "MANUAL_PART_XXI.md",
         "MANUAL_PART_XXII.md"]

PAGEBREAK = '\n\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n\n'
TOC = ('\n\n```{=openxml}\n'
       '<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
       '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\u </w:instrText></w:r>'
       '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
       '<w:r><w:t>Actualizá el índice: clic derecho sobre él → Actualizar campos (o F9).</w:t></w:r>'
       '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>\n```\n\n')

COVER_DOCX = ('::: {custom-style="WSWordmark"}\n'
              '[web]{custom-style="WSBlue"}[shooks]{custom-style="WSNavy"}[.]{custom-style="WSOrange"}\n'
              ':::\n\n'
              '::: {custom-style="WSCoverTitle"}\nCatalaxia\n:::\n\n'
              '::: {custom-style="WSCoverSub"}\nManual Operativo Catalaxia\n:::\n\n'
              '::: {custom-style="WSCoverMeta"}\nProcesos · Datos · Validación · Resultados\n:::\n\n'
              '::: {custom-style="WSCoverMeta"}\nSEC EDGAR · CNV · Market · TIKR — operaciones E2E y gobernanza de datos\n:::\n\n'
              '::: {custom-style="WSCoverMeta"}\nVersión 2.0 · Septiembre 2026 · Documento interno / confidencial\n:::\n'
              + PAGEBREAK +
              '::: {custom-style="WSLabel"}\nÍndice\n:::\n' + TOC + PAGEBREAK)

COVER_HTML = ('''<div class="cover">
<p class="wordmark"><span class="b">web</span><span class="n">shooks</span><span class="o">.</span></p>
<h1 class="title">Catalaxia</h1>
<p class="subtitle">Manual Operativo Catalaxia</p>
<p class="meta">Procesos &middot; Datos &middot; Validaci&oacute;n &middot; Resultados<br>
SEC EDGAR &middot; CNV &middot; Market &middot; TIKR — operaciones E2E y gobernanza de datos<br>
Versi&oacute;n 2.0 &middot; Septiembre 2026 &middot; Documento interno / confidencial</p>
</div>
<div style="page-break-after: always;"></div>
''')

HTML_BREAK = '\n\n<div style="page-break-after: always;"></div>\n\n'


def _bodies():
    return [open(os.path.join(HERE, f), encoding="utf-8").read() for f in ORDER]


def _pandoc(args):
    pandoc = ws.find_pandoc()
    cmd = [pandoc] + args
    print("»", os.path.basename(pandoc), "->", os.path.basename(args[args.index("-o") + 1]))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDERR:\n", r.stderr[-2500:])
        sys.exit("pandoc falló")


def main():
    bodies = _bodies()

    with open(COMBINED, "w", encoding="utf-8") as fh:
        fh.write(COVER_DOCX + PAGEBREAK.join(bodies))
    ws.build_reference()
    _pandoc([COMBINED, "-o", OUT_DOCX, "--reference-doc",
             os.path.join(ws.HERE, "reference.docx"), "-f", "markdown", "--wrap=none"])

    with open(COMBINED, "w", encoding="utf-8") as fh:
        fh.write(COVER_HTML + HTML_BREAK.join(bodies))
    _pandoc([COMBINED, "-s", "--toc", "--toc-depth=2", "-c", "manual_style.css", "-f", "markdown", "-o", OUT_HTML])

    _pandoc([OUT_DOCX, "-f", "docx", "-o", OUT_ODT])

    os.remove(COMBINED)
    for p in (OUT_DOCX, OUT_HTML, OUT_ODT):
        print(f"OK -> {p}  ({os.path.getsize(p)/1024:.0f} KB)")


if __name__ == "__main__":
    main()