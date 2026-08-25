# RISK_REGISTER.md — Catalaxia Financial Data Engine

PHASE 0 deliverable · 2026-08-23 · Status: VIVO (se actualiza cada fase)

| ID | Riesgo | Severidad | Prob. | Mitigación | Estado |
|---|---|---|---|---|---|
| R-01 | `backend/requirements.txt` fija `yfinance==0.2.50`, versión declarada ROTA al 100% por EXT-053 | ALTA | vigente | bump de versión + guard sanidad s9 antes de aceptar datos; verificar en S07 | ABIERTO |
| R-02 | `PIPELINE_VALIDATION_SPECIFICATION.md` citado por el programa NO existe en repo | MEDIA | vigente | ✅ AUTORADO v1.0 (2026-08-23): gates, catálogo de checks por etapa, conciliación, certificación única | CERRADO |
| R-03 | 77% de facts XBRL son dimensionales: extraer solo consolidado destruye información | ALTA | estructural | PARSED guarda dimensiones completas (JSON por fact); NORMALIZED declara perimetro | CERRADO POR DISEÑO |
| R-04 | YPF cambia moneda de presentación ARS→USD entre FY2021/FY2022: mezcla de vintages rompe series | ALTA | verificada en piloto | guard unidad+moneda por período en S04/S05; series separadas por currency_original; jamás convertir silenciosamente | CERRADO POR DISEÑO |
| R-05 | 4 layouts XBRL distintos (XML plano / -xbrl.zip / iXBRL / linkbases en xsd) → parser frágil | ALTA | verificada FY2017–FY2025 | portar parser piloto que ya cubre los 4; test por layout como regression fixture | MITIGADO |
| R-06 | FY2010–FY2016 sin XBRL → hueco histórico si se exige XBRL-only | MEDIA | estructural | alcance v1 = XBRL era con null_reason=SOURCE_FORMAT para años previos; extensión HTML futura | ACEPTADO (v1) |
| R-07 | Fixes manuales incrustados en pipeline v1 sin correction_rule versionada (FASE2 §3.2) | MEDIA | vigente legacy | engine no hereda fix_*; correcciones via correction_log declarativo | MITIGADO |
| R-08 | Descargas SEC secuenciales: corridas FULL largas → interrupciones pierden trabajo | MEDIA | operativa | download_log append-only + resume por manifest; checkpoints por etapa | DISEÑADO |
| R-09 | Scraping benchmarks bloqueado (precedente Cloudflare investing) | MEDIA | alta según precedente | drop manual validado clase C con estándar admisión §2.2 (decisión D-006) | PENDIENTE DECISIÓN |
| R-10 | Dos definiciones de "certificado" conviven (validar_suite M2 vs b7 M4) hasta unificar | MEDIA | vigente | engine usa SOLO certificación estilo b7; sello viejo queda legacy read-only | MITIGADO |
| R-11 | Extractor vigente resuelve 4/32 métricas sobre YPF → expectativa de cobertura mal calibrada si se reutiliza tal cual | ALTA | verificada | mapping canónico ifrs-full/us-gaap nuevo en S04 con test contra universo tags del piloto | CERRADO POR DISEÑO |
| R-12 | Tickers SEC reciclados (GOLD/CHA) rompen identidad ticker→CIK | BAJA (v1 YPF) | documentada | identidad solo CIK; ticker es clasificación; discrepancia → revisión manual | CERRADO POR DISEÑO |
| R-13 | Contexto del agente: sesiones largas pierden memoria normativa | MEDIA | operativa | skill catalaxia-filosofia + outputs/docs/architecture/* como fuente de verdad + DECISION_QUEUE consultado al inicio de cada fase | MITIGADO |
| R-14 | D-002 exige PG desde día 1: desarrollo local depende de instancia docker `catalaxia-db` disponible | MEDIA | operativa | ✅ contenedor dev dedicado `catalaxia-engine-dev` (PG16, puerto 127.0.0.1:5433) creado y verificado; prod 5432 intocada; guarda EXT-010 en engine/config.py bloquea apuntar a 5432 | MITIGADO |
| R-15 | Colisión de nombres Windows/Python: directorio legacy `Engine/` impide importar paquete `engine/` (import case-sensitive sin PYTHONCASEOK) | BAJA | resuelta | legacy movido intacto a `_legacy/Engine/` (untracked, solo js vacío); registrado aquí por trazabilidad EXT-NEW-007 | CERRADO |
| R-16 | Catálogos legacy contienen CIKs podridos: 4 confirmados en S01 (YPF→1104659 inexistente; GGAL, BMA, CRESy desviados) → outputs del screener viejo pueden estar construidos sobre identidades equivocadas | ALTA | confirmada | engine siembra identidad SOLO desde fuente de registro SEC + cola identifier_reviews (EXT-NEW-012); antes de reutilizar cualquier comparación legacy, contrastar contra identity.entities | MITIGADO (engine) / ABIERTO (legacy) |

## Señales de alarma activas (de DO_NOT_REPEAT — cualquiera detiene el programa)

1. Conteo de filas cambia sin explicación tras una carga.
2. Ratio cambia >10% entre corridas sin cambio de datos subyacente.
3. Magnitud absurdamente distinta a la serie (×10, ×1000).
4. Doc viejo contradice al nuevo sin marca DEPRECATED/SUPERSEDED.
5. Script "terminó sin excepción" pero cobertura cayó.
