# S03 PARSE — Reporte de ejecución (YPF GOLDEN CASE)

- run_id: `9a5d4205df364746bd6b42aa3064b8ab`
- git_commit: `2993918fd268d0ffa9184815626fa4e438a46327`
- input checkpoint: `S02:9a5d4205df364746bd6b42aa3064b8ab`
- generado: 2026-09-07T05:40:10.064619+00:00

## Resumen ejecutivo

- Filings procesados: 31/31 (PARSED_XBRL=17, PRE_XBRL=14, REJECTED=0)
- Facts extraidos: 90,398
- Contexts: 24,008 | Units: 181
- Conceptos inventariados: 14,934 (custom=14,934, standard=0)
- Relations (linkbases): 201,765
- Facts con dimensiones: 59,523 | sin dimensiones: 30,875
- Errores de parseo registrados: 0
- Cobertura filings: 100.0%

## Performance

- Tiempo total: 501.662s | facts/s: 180.2 | memoria pico aprox: 390.2 MB

## Checks

| check | blocking | resultado | detalle |
|---|---|---|---|
| C-S03-001 | True | PASS | conciliacion filings expected->parsed/rejected: filings=31/31 PARSED_XBRL=17 PRE_XBRL=14 REJECTED=0 inputs_corruptos=0 |
| C-S03-002 | True | PASS | integridad RAW de entrada: sha256 re-verificado contra download_log S02 ok=536/536 fallidos=0 |
| C-S03-003 | True | PASS | provenance completo fact->source_file->sha256->accession->entity->run: violaciones=0 sobre facts=90398 |
| C-S03-004 | True | PASS | cobertura XBRL: filings con hechos extraidos=17 (esperado>=5); sin hechos: ninguno |
| C-S03-005 | True | PASS | era pre-XBRL declarada explicitamente: filings=14, registrados como PRE_XBRL=14, sin registrar: ninguno |
| C-S03-006 | True | PASS | integridad referencial parser-output: context_refs colgantes=0, unit_refs colgantes=0 |
| C-S03-007 | True | PASS | comparacion CompanyFacts vs filing generada: conceptos=12787 (ambos=0, solo_cf=726, solo_filing=12061) |
| C-S03-009 | False | PASS | performance: total=501.662s facts/s=180.2 archivos/s=1.06 memoria_pico=390.2MB |

## Decisiones tomadas (no silenciosas)

1. Inline XBRL (.htm) NO se parsea como fuente de hechos: los filings iXBRL tienen su instancia canónica dentro de `-xbrl.zip`; los .htm quedan documentados como fuente duplicada no parseada.
2. Los hechos textuales/nil se preservan con `value_numeric=NULL`; NO se descartan.
3. NO se deduplica nada (norma S03); ocurrencias repetidas por tag quedan como métrica informativa.
4. Era FY2001–FY2017 clasificada `PRE_XBRL` con nota explícita; conversión automática HTML→XBRL prohibida.
5. Capa `parsed.*` es derivada y determinista: cada corrida reemplaza por entidad (delete+insert transaccional); la verdad permanece en RAW.
6. Conceptos observados en instancias sin esquema local se registran con `source_schema='INSTANCE_OBSERVED'` — nunca se descartan.

## Veredicto

Ver `S03_VALIDATION.json` → campo `verdict` (`READY_FOR_S04` / `BLOCKED_S04`).
