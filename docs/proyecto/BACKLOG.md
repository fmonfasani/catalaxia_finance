# Backlog — Catalaxia CEDEARs

Cosas identificadas para hacer más adelante (no se resuelven ahora, quedan anotadas).

## Trazabilidad / cadena de custodia (solo para actualizaciones NUEVAS)

**Estado actual:** el crudo (`eeff_html/{guid}.html`) se guarda por GUID → es rastreable a la URL
exacta de la CNV (`aif2.cnv.gov.ar/presentations/publicview/{guid}`). Reproducible.

**Corrección (2026-07-16):** la tabla **`ingest_log` YA EXISTE** con el esquema completo
(`source, cuit, url, http_status, sha256, bytes, path, fetched_at, error`). El mecanismo de cadena
de custodia **está construido**. PERO solo tiene **50 filas** = las descargas recientes de páginas
de empresa (`cnv_page`, 2026-07-13). Los **documentos históricos de `eeff_html` NO están logueados
ahí** → el histórico sigue sin hash/timestamp (rastreable por GUID→URL, pero sin prueba de cuándo
se bajó ni de integridad). `descargas_log` (SEC) está vacía.

**Decisión:** **NO se toca lo histórico** (lo que está, está). Como el `ingest_log` ya existe, la
tarea es chica: hacer que el **fetch de estados** del flujo de actualización (`job5_v2` / `fetch_dgce`)
**escriba en `ingest_log`** cada doc nuevo (guid, url, sha256, bytes, http_status, ts). Así el
histórico queda como está y las actualizaciones nacen con cadena de custodia completa. No hay que
crear tabla nueva — solo cablear la escritura.

Anotado: 2026-07-16.
