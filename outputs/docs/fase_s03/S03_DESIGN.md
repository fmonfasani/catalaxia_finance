# S03 PARSE — Diseño (YPF GOLDEN CASE)

## 1. Objetivo

Convertir el RAW XBRL descargado por S02 en información estructurada y auditable
(facts / contexts / units / concepts / linkbase relations), SIN normalizar conceptos
financieros ni calcular métricas. La separación S03 (preservar y estructurar) vs
S04 (normalizar y decidir significado) es estricta.

```
S01 IDENTITY -> S02 FETCH -> RAW INMUTABLE -> S03 PARSE -> HECHOS/TAGS/CONTEXTOS/UNIDADES/RELACIONES -> S04 NORMALIZE
```

## 2. Entradas

- Checkpoint del último run S02 con `gate_status='PASS'` (`engine.checkpoints`, `engine.stage_runs`).
- Filas exitosas de `fetch_raw.download_log` de ese run: 189 archivos, sha256 verificado al vuelo.
- Snapshot `submissions` (metadatos por accession) y snapshot `companyfacts` (comparación §7).

## 3. Clasificación por filing

| Condición | Outcome | Tratamiento |
|---|---|---|
| Tiene instancia suelta o `-xbrl.zip` con instancia | `PARSED_XBRL` | parseo completo |
| Sin payload XBRL (FY2001–FY2017) | `PRE_XBRL` | registro explícito + documentos listados; conversión automática prohibida |
| Tiene payload pero 0 facts y sin error documentado | `REJECTED` | fuerza gate BLOCK |

Eras distintas NO se asumen homogéneas:
- FY2018–FY2020: instancia XML suelta + linkbases + schema custom `ypf`.
- FY2021+: iXBRL; la instancia canónica vive dentro de `-xbrl.zip`.
- FY2017 (primer año XBRL): estructura mixta.
- El inline `.htm` NO se parsea como fuente de hechos (duplica la instancia del zip);
  queda documentado como fuente no parseada.

## 4. Modelo de salida

Esquema PostgreSQL dev (5433) `parsed.*` — capa DERIVADA, determinista, replace-all
por corrida dentro de UNA transacción:

| Tabla | Contenido |
|---|---|
| `facts` | todos los hechos (numéricos, textuales, nil), con provenance completo |
| `contexts` | contextos con dimensiones explícitas/tipadas sin colapsar |
| `units` | unidades simples y divididas + conteo de uso |
| `concepts` | inventario desde schemas custom + conceptos observados (`INSTANCE_OBSERVED`) |
| `link_relations` | LABEL / PRESENTATION / CALCULATION / DEFINITION |
| `pre_xbrl_filings` | era pre-XBRL declarada |
| `companyfacts_compare` | comparación CF vs filing |
| `parse_errors` | errores/warnings con código y archivo |

## 5. Provenance obligatorio

Todo fact arrastra: `entity_id, cik, accession_number, form, filing_date, report_period,
source_kind, source_file, source_path (incluye miembro zip `!miembro`), source_hash,
run_id, stage_run_id`. El check C-S03-003 bloquea si hay alguno NULL.
No se aceptan hechos sin provenance.

## 6. XBRL técnico

- Instancias: `lxml.etree.fromstring`; namespaces xbrli/link/xsd/xbrldt; hechos =
  elementos con `contextRef`/`unitRef` fuera de esos namespaces.
- Contextos: período instant/duration/forever; `explicitMember` → dimensión explícita;
  `typedMember` Y elementos con atributo `dimension` → dimensiones tipadas (JSONB íntegro).
- Unidades: simple (`measure`) y dividida (`divide/numerator/denominator`).
- Valores numéricos como `Decimal` (precisión exacta en `NUMERIC`); `xsi:nil` preservado.
- Linkbases: resolución `loc href#fragment` → qname crudo (el namespace real requiere el
  XSD referenciado; se conserva la referencia resoluble, nunca se inventa).
- Arcroles estándar mapeados a linkbase; fallback por sufijo de archivo.
- Zip: selección de instancia por heurística puntuada (`zip_instance_candidates`);
  schemas/linkbases internos parseados con hash por miembro.

## 7. CompanyFacts vs filing

Índice por qname de ambas fuentes → clasificación AMBOS / SOLO_CF / SOLO_FILING +
diferencias de observaciones, períodos extremos y tipos de unidad. Diferencias se
REGISTRAN (columna notes), nunca se corrigen silenciosamente.

## 8. Validación (checks C-S03-*)

| ID | Alcance | Blocking |
|---|---|---|
| C-S03-001 | conciliación filings expected→parsed/rejected | sí |
| C-S03-002 | integridad sha256 del input S02 re-verificada | sí |
| C-S03-003 | provenance 100% en facts | sí |
| C-S03-004 | cobertura XBRL (≥9 filings FY2017–FY2025 con hechos) | sí |
| C-S03-005 | era pre-XBRL declarada explícitamente | sí |
| C-S03-006 | integridad referencial interna (context_ref/unit_ref) | sí |
| C-S03-007 | comparación CompanyFacts generada | sí |
| C-S03-008 | outputs escritos y no vacíos | sí |
| C-S03-009 | performance medida | no |

Gate PASS ⇒ `READY_FOR_S04`; cualquier blocking FAIL ⇒ `BLOCKED_S04`.

## 9. Performance

Streaming por filing (memoria O(filing)), inserción bulk `execute_values` page_size=1000,
transacción única (atomicidad total: si el gate bloquea, rollback). Medición:
`time.perf_counter` + `tracemalloc` (pico de objetos Python).

## 10. Fuera de alcance (prohibido en S03)

PER/EBITDA/ROE/márgenes/FCF/payout/EPS o cualquier métrica; selección de "mejor tag";
mapping a conceptos canónicos; deduplicación semántica; elección de períodos canónicos.
Todo eso es S04 NORMALIZE.
