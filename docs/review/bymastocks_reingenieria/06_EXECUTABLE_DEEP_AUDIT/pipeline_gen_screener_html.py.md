# scripts/pipeline/gen_screener_html.py — FICHA DEEP AUDIT

> FORMATO OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 12_PUBLICACION. [VERIFICADO POR CÓDIGO — genera el artefacto público autocontenido desde `screener_gold`]  
SECUNDARIAS: 11_CERTIFICACION (solo AGRUPA los sellos ya presentes en `screener_gold` para el masthead; NO certifica ni recalcula ratios). Sin capa de cálculo. [VERIFICADO POR CÓDIGO — gen_screener_html.py:10-18]

PLANOS →
- DATOS: lee `screener_gold` por `SELECT *` (gen_screener_html.py:8); escribe `docs/producto/screener.html` (gen_screener_html.py:313-316). [VERIFICADO POR CÓDIGO]
- CONTROL: solo conteos agregados (Counter de nivel_certificacion y grupo, gen_screener_html.py:10-18) para el masthead; la presentación (filtros/orden) ocurre en JS a runtime sobre datos ya certificados. NO dimensiona sobre datos crudos.
- EJECUCIÓN: script plano sin `main_guard`; determinismo PARCIAL (ver RIESGOS 1); reproduce tras `run_pipeline` (docstring gen_screener_html.py:4); sin retries/manejo de error. [VERIFICADO POR CÓDIGO]
- INFRA: SQLite local + filesystem (escritura directa del HTML con `open(...'w')`, gen_screener_html.py:315). Sin red. [VERIFICADO POR CÓDIGO]

CICLO →
- DEFINIR: cara pública del producto, autocontenida (datos embebidos), universo AR+ADR+US (gen_screener_html.py:2-5). [VERIFICADO POR CÓDIGO]
- IMPLEMENTAR: respeta capa 12 — solo lee `screener_gold` certificado y lo empaqueta; no recalcula ratios ni certifica. [VERIFICADO POR CÓDIGO]
- VERIFICAR: sin tests de contrato para el artefacto (HTML/JS). [VERIFICADO POR CÓDIGO — ausencia]
- CERTIFICAR: hereda la certificación de `screener_gold` (los sellos se muestran tal cual); sin certificación propia. [NO DETERMINABLE]

HOY → Lee todas las filas de `screener_gold`, agrupa por nivel/grupo para el masthead, serializa el payload a JSON y lo inyecta en una plantilla HTML/JS autocontenida (búsqueda, orden, filtros y vistas Anual/TTM client-side). El artefacto embebe una fecha de generación y los sellos con que f5/f6 dejaron cada fila. [VERIFICADO POR CÓDIGO — gen_screener_html.py:8-22, 195, 313-316]
[OBJETIVO] → Publicar EXCLUSIVAMENTE filas de `screener_gold` que pasaron su certificación (ya ocurre: filas con sello parcial se marcan y no se muestran ratios no cross-validados, gen_screener_html.py:249-255); congelar contrato de columnas para evitar fragilidad por `SELECT *`; hacer el artefacto reproducible byte-a-byte.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → DB:screener.screener_gold (`SELECT *`); file:docs/producto/screener.html (destino). Generado tras `run_pipeline` (f5/f6 población `screener_gold`). [VERIFICADO POR CÓDIGO/CENSO PIP019]

CONTRATO →
- INPUT: tabla `screener_gold` (todas las columnas).
- OUTPUT: `docs/producto/screener.html` (autocontenido, JSON embebido en `<script id="data">`).
- PRECONDICIONES: `screener_gold` poblada y certificada por f5/f6 previos.
- POSTCONDICIONES: artefacto público desplegable con sellos y ratios filtrados por confiabilidad.
- INVARIANTES: I-001 RAW (NO aplica); I-006 PROVENANCE (solo la información que ya está en `screener_gold` se muestra; no agrega ni derivación); I-007 DETERMINISMO (PARCIAL — timestamp `dt.date.today()` rompe idempotencia byte a byte, ver RIESGOS 1); I-008 IDEMPOTENCIA (sí: re-escribe el mismo path). [VERIFICADO POR CÓDIGO — gen_screener_html.py:22, 315]

RIESGOS →
1. No reproducible byte-a-byte: `'generado': dt.date.today().isoformat()` (gen_screener_html.py:22) cambia entre corridas → rompe I-007 DETERMINISMO/IDEMPOTENCIA del ARTEFACTO aunque los datos no cambien (P2, determinismo/no-dato). [VERIFICADO POR CÓDIGO — gen_screener_html.py:22]
2. `SELECT *` sin contrato fijo (gen_screener_html.py:8): un ADD COLUMN o rename en `screener_gold` puede romper silenciosamente el frontend (columnas usadas en JS, COLS/r[], gen_screener_html.py:199-205, 242-256) (P1). [VERIFICADO POR CÓDIGO]
3. Estadística hardcodeada `['c0','0','Inventadas']` (gen_screener_html.py:231): un "0" constante presentado como datapoint del masthead, no derivado — riesgo de parecer inventado/malentendido vs. el claim "nada se inventa" (P2). [VERIFICADO POR CÓDIGO — gen_screener_html.py:231]
4. La vista TTM confía en columnas `*_ttm`/`ttm_cierre`/`ttm_no_confiables` si existen (gen_screener_html.py:218-224); si esas columnas no estuvieran (SELECT * las incluiría igual), el front no las muestrearía correctamente sin test (P2). [VERIFICADO POR CÓDIGO — gen_screener_html.py:218-224]
5. Sin tests del artefacto ni validación del HTML generado (P2). [VERIFICADO POR CÓDIGO — ausencia]

DECISIÓN → (FASE 1: NO EJECUTAR NADA) **KEEP** (censo: KEEP). Acción a planificar: congelar contrato de columnas del artefacto (evitar SELECT *), derivar o quitar el "0" hardcodeado, y fechar el artefacto por hash de datos en vez de fecha wall-clock para reproducibilidad.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: gen_screener_html.py:8 (SELECT * screener_gold); :10-18 (agregación niveles/grupo); :19-22 (payload + fecha generado); :195 (JSON embebido); :199-224 (columnas del front / vista TTM); :231 ("0" hardcodeado); :249-255 (marcado de ratios no cross-validados); :313-316 (escritura del HTML).
- VERIFICADO POR EJECUCIÓN: CENSO PIP019 (genera docs/producto/screener.html tras run_pipeline).
- NO DETERMINABLE: tests de contrato del HTML/JS; estado de despliegue del artefacto.

ESTADO: **PASS_WITH_WARNINGS** (respeta capa 12; determinismo del artefacto + SELECT * + "0" hardcodeado).

