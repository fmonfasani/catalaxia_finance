# -*- coding: utf-8 -*-
"""Genera el Word consolidado del proyecto, con la marca webshooks.
Ensambla: portada + índice (TOC de Word) + los 12 documentos de docs/proyecto +
anexo de infra, y lo convierte con pandoc usando el reference.docx branded.

    python build_docx.py

Requiere: python-docx + pandoc (webshooks_docx.py se encarga del estilo).
"""
import os, sys, subprocess
import webshooks_docx as ws

PROY = r"D:/Software Development/Porfolio/catalaxia-cedears-prod/docs/proyecto"
OUT  = os.path.join(PROY, "Proyecto_Catalaxia_Interno.docx")

# --- bloques openxml crudos (pandoc los pasa tal cual al .docx) ---
PAGEBREAK = '\n\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n\n'
TOC = ('\n\n```{=openxml}\n'
       '<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
       '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\u </w:instrText></w:r>'
       '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
       '<w:r><w:t>Actualizá el índice: clic derecho sobre él → Actualizar campos (o F9).</w:t></w:r>'
       '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>\n```\n\n')

COVER = ('::: {custom-style="WSWordmark"}\n'
         '[web]{custom-style="WSBlue"}[shooks]{custom-style="WSNavy"}[.]{custom-style="WSOrange"}\n'
         ':::\n\n'
         '::: {custom-style="WSCoverTitle"}\nProyecto Catalaxia Screener\n:::\n\n'
         '::: {custom-style="WSCoverSub"}\nDocumentación interna del proyecto · webshooks → Catalaxia\n:::\n\n'
         '::: {custom-style="WSCoverMeta"}\nCliente: Catalaxia S.A.\n:::\n\n'
         '::: {custom-style="WSCoverMeta"}\nFecha: Julio 2026 · v1.0 · Documento interno / confidencial\n:::\n'
         + PAGEBREAK +
         '::: {custom-style="WSLabel"}\nÍndice\n:::\n' + TOC + PAGEBREAK)

FILES = [os.path.join(PROY, f) for f in [
    "00_INDICE_Y_PLAN.md", "01_ALCANCE_Y_DOD.md", "02_ROLES_RACI.md", "03_ARQUITECTURA_Y_BD.md",
    "04_CONTRATO_API.md", "05_SETUP_DEV.md", "06_INFRA_DEPLOY_VPS.md", "07_PLAN_ENTREGAS_SEMANAL.md",
    "08_ESTANDARES_TRABAJO.md", "09_COORDINACION_CLIENTE.md", "10_QA_Y_RIESGOS.md",
    "jira/GUIA_JIRA.md"]]


def anexo():
    infra = os.path.join(PROY, "infra")
    out = [PAGEBREAK, "# Anexo A — Archivos de infraestructura (Docker)\n\n",
           "Los archivos listos para desplegar en la VPS (ver capítulo *Infra / Deploy VPS*).\n\n"]
    for fn, lang in [("docker-compose.yml", "yaml"), ("backend.Dockerfile", "dockerfile"),
                     ("nginx-catalaxia.conf", "nginx"), (".env.example", "")]:
        p = os.path.join(infra, fn)
        if os.path.exists(p):
            body = open(p, encoding="utf-8").read().rstrip()
            out.append(f"## {fn}\n\n~~~{lang}\n{body}\n~~~\n\n")
    out.append("> El backlog de Jira (`jira/jira_import.csv`, 7 épicas · 34 historias · 108 pts) "
               "se importa según la *Guía de Jira*.\n")
    return "".join(out)


def main():
    ref = ws.build_reference()
    bodies = [open(f, encoding="utf-8").read() for f in FILES]
    combined = COVER + PAGEBREAK.join(bodies) + anexo()
    tmp = os.path.join(ws.HERE, "_combined.md")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(combined)
    pandoc = ws.find_pandoc()
    cmd = [pandoc, tmp, "-o", OUT, "--reference-doc", ref, "-f", "markdown", "--wrap=none"]
    print("»", os.path.basename(pandoc), "->", os.path.basename(OUT))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDERR:\n", r.stderr[-2500:]); sys.exit("pandoc falló")
    os.remove(tmp)
    print(f"OK -> {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
