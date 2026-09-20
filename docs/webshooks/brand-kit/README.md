# webshooks brand-kit — generador de documentos

Kit para producir documentos **con la marca webshooks** desde Markdown, con un solo comando.
Estandariza fuente, colores, encabezados, tablas, portada y footer.

## Qué hay acá

```
brand-kit/
  GUIA_ESTILO_WEBSHOOKS.md   la guía de marca (colores, fuente, formatos)
  webshooks_docx.py          genera reference.docx branded (motor de estilo)
  build_docx.py              arma el Word consolidado del proyecto (pandoc)
  plantilla_webshooks.md     esqueleto para documentos nuevos
  reference.docx             estilos Word (lo regenera el script; no editar)
```

## Requisitos (una vez)

- **Python** con `python-docx`:  `pip install python-docx`
- **pandoc**:  `winget install JohnMacFarlane.Pandoc`  (el script lo encuentra solo)

## Generar el Word consolidado del proyecto

```bash
cd docs/webshooks/brand-kit
python build_docx.py
# -> docs/proyecto/Proyecto_Catalaxia_Interno.docx
```

Junta: portada branded + **índice automático de Word** + los 12 documentos de `docs/proyecto/`
(00…10 + guía de Jira) + un anexo con los archivos de infra (Docker). Al abrir el Word, actualizá
el índice con **F9** (o clic derecho → *Actualizar campos*).

**Para PDF:** abrí el `.docx` en Word → *Guardar como PDF* (o LibreOffice `--convert-to pdf`).

## ¿Es reproducible? Sí, del todo

Todo el documento se arma con **dos scripts** y **pandoc**. No hay maquetado manual:
1. `webshooks_docx.py` construye el `reference.docx` con los estilos de marca.
2. `build_docx.py` concatena los `.md` y los convierte con pandoc usando ese estilo.

Editás cualquier `.md` → corrés `python build_docx.py` → Word actualizado. Fin.

## Usarlo para OTRO documento

`webshooks_docx.py` es genérico (el motor de estilo). Para un documento nuevo:

- **Rápido (un solo .md):**
  ```bash
  python webshooks_docx.py                 # crea reference.docx
  pandoc mi_doc.md -o mi_doc.docx --reference-doc reference.docx
  ```
- **Compuesto (varios .md, portada, índice):** copiá `build_docx.py`, cambiá la lista `FILES`,
  el `COVER` y la ruta `OUT`. El resto (estilo, footer, índice) ya está resuelto.

## Paleta (referencia rápida)

navy `#1A2744` · azul `#3B82F6` · naranja `#F5821F` · verde `#43A047` · gris `#3A4458` · Calibri.
Ver `GUIA_ESTILO_WEBSHOOKS.md` para el detalle.
