# engine/cnv/discovery.py — FICHA DEEP AUDIT

> FORMATE OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 04_PARSED. [VERIFICADO POR CÓDIGO — transforma HTML crudo de página empresa y visor en estructura tipada (Presentation/ViewerMeta); header discovery.py:1-11]. NO hace red ni fetch (el transporte vive en client.py).
SECUNDARIAS: 02_IDENTIDAD [VERIFICADO POR CÓDIGO — embebe reglas duras: identidad solo por CUIT descubierto en el título, NUNCA por nombre; discovery.py:1-11, 5-6]; 05_NORMALIZED [VERIFICADO POR CÓDIGO — normalize_cuit, fechas ISO, periodicidad normalizada TEXTO/CODIGO_CNV, ambario PROPIO/RELACIONADA/NO_FINANCIERO].

PLANOS →
- DATOS: entrada en memoria (HTML String provisto por client.py); salida Tipos Python (dataclasses), sin escritura a disco ni DB. [VERIFICADO POR CÓDIGO — discovery.py:48-77, 294-323; flags.csv flag=0 sin I/O].
- CONTROL: clasificación determinista por TEXTOS DECLARADOS por CNV (classify mira solo el título/sección, nunca infiere relación) [VERIFICADO POR CÓDIGO — discovery.py:153-175]; relación CONTROLADA/VINCULADA preservada y nunca asumida (BALANCE SUBSIDIARIA → rel=None, origen AUSENTE [discovery.py:223-226]); periodicidad con código sin mapeo marcado para revisión, no adivinado [discovery.py:122-137]; duplicados de GUID deduplicados conservando ambas secciones [discovery.py:276-291].
- EJECUCIÓN: función pura, determinista (regex + recorrido ordenado de eventos por posición [discovery.py:255-291]); sin red, sin estado global.
- INFRA: ninguna; no se conecta a DB ni red. Solo `re/json/dataclasses` [VERIFICADO POR CÓDIGO — imports discovery.py:14-16; imports.csv].

CICLO →
- DEFINIR: reglas duras C0/C1/C2 documentadas en el header [VERIFICADO POR CÓDIGO — discovery.py:1-11].
- IMPLEMENTAR: respeta capa 04; no decide negocio más allá de clasificar (el "qué hacer" con la clase vive en capas superiores).
- VERIFICAR: tests unitarios puros sin red ni DB (test_engine_cnv.py cubre canonical_sha256 y classify CONTROLADA/VINCULADA/PROPIO/NIIF/RELAC/OTRO) [VERIFICADO POR CÓDIGO — tests en repo; import engine.cnv.discovery en imports.csv].
- CERTIFICAR: sin certificación formal [NO DETERMINABLE].

HOY → Parsea página empresa CNV en inventario de presentaciones clasificadas (EEFF propio/controlada/vinculada/relac-otra/legacy, actas, ON, hechos relevantes) con CUIT/relación/periodicidad/fecha-cierre normalizados, y el visor en metadata+adjuntos con hash CNV. Funciona offline sobre HTML. [VERIFICADO POR CÓDIGO]
OBJETIVO → Punto canónico de Discovery CNV dentro de la cadena client→discovery→validate→rawstore→provenance, consumido por la capa CNV en lugar de los jobs legacy (job3/job4, build_fiscal_calendar, etc. listados como DEPRECATE/ADAPT en census). [VERIFICADO POR CÓDIGO — census CORE010 + CNVX038/039/042/045/046]
DEPENDENCIAS → engine.cnv.client (provee FetchResult HTML en memoria); python stdlib re/json/dataclasses; datos RAW de página empresa y visor (en memoria, no DB).

CONTRATO → INPUT: `html: str` (página empresa) → parse_empresa_page; `(html, guid)` → parse_viewer. OUTPUT: tuple(list[Presentation], resumen) con guids únicos y dedup por sección; ViewerMeta con attachments (blob_guid, nombre, tamano, hash_cnv, propiedad) y csrf_token. PRECONDICIONES: HTML de página/visor con estructura esperada (RE_ROW/RE_HEADER/RE_TD/RE_GUID/RE_UPLOADER); sin ella devuelve inventario vacío sin lanzar. POSTCONDICIONES: cada Presentation con clase/ambito/relación determinados por texto declarado; GUID lowercased; URL publicview canónica [discovery.py:199]. INVARIANTES: I-007 DETERMINISMO (mismo HTML → mismo resultado; sort por posición de evento [discovery.py:262]); I-004/005 implícito respeto fuente (no inventa relación ni CUIT); sin I/O multi-destino.

RIESGOS →
1. Clasificación por heurística textual (regex sobre título formateado por CNV): un cambio de layout/formato de etiquetas puede degradar silenciosamente la clasificación (e.g. corte del separador ` - ` en campos, discovery.py:140-150). [VERIFICADO POR CÓDIGO]
2. `_parse_fecha_es` y `_parse_fecha_dmy` retornan None ante formatos no reconocidos sin alertar (fecha_cierre/anio_cierre pueden quedar None y no se marca revisión). [VERIFICADO POR CÓDIGO — discovery.py:91-114]
3. Dedup de GUID "benigno" puede ocultar dos presentaciones distintas si CNV reutiliza GUIDs [NO DETERMINABLE — asunción documentada discovery.py:280-282, sin evidencia de contramedida].
4. Parser acoplado a la estructura del acordeón CNV (RE_HEADER define la sección) — frágil ante rediseño del portal [VERIFICADO POR CÓDIGO — discovery.py:255-273].
5. Los consumidores legacy (job3/job4/build_fiscal_calendar) duplican lógica de clasificación "a su manera", riesgo de divergencia semántica con esta versión canónica. [VERIFICADO POR CÓDIGO — census CNVX038/039/046 vs CORE010]

DECISIÓN → (FASE 1: NO ejecutar nada). KEEP. Planificar: (a) rutas de retiro/ADAPT de jobs legacy hacia discovery canónico; (b) tests de formato que alerten sobre cambios de layout CNV; (c) registrar revisión explícita cuando fecha/periodicidad no resuelta.

EVIDENCIA → VERIFICADO POR CÓDIGO: discovery.py:1-11 (reglas de identidad); :19-21 (versión parser); :80-84 (normalize_cuit); :91-137 (fechas/periodicidad); :140-150 (_field separador); :153-175 (classify); :178-232 (parse_presentation_row); :238-252 (helpers relacion/sigla); :255-291 (parse_empresa_page, dedup 276-291); :294-370 (parse_viewer, attrs/adjuntos). VERIFICADO POR TEST (existencia en repo): test_engine_cnv.py (classify + rawstore) [imports.csv]. VERIFICADO POR EJECUCIÓN: NO DETERMINABLE. NO DETERMINABLE: cobertura real de variantes de layout CNV no probada.

ESTADO: PASS (código limpio, puro, determinista y con tests-en-repo; los riesgos son de fragilidad de contrato externo, no de arquitectura).
