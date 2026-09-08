# EXTRACTION_CHECKLIST.md

**Checklist ejecutable por corrida de extracción — Catalaxia Finance**
v1.0 · 2026-08-22 · Norma: "corre sin error" ≠ extracción exitosa.
Copiar este bloque al log de cada corrida (`data/logs/`) y marcar. Cualquier ⛔ = ABORTAR antes de continuar.

---

## FASE 0 — PRE-FLIGHT

- [ ] **DB destino correcta** (¿dev o prod? jamás default silencioso a prod — EXT-010)
- [ ] Entorno verificado (una sola instancia; SQLite WAL pero sin paralelo)
- [ ] **Snapshot/hash de fuentes tomado ANTES** (`snapshot_byma.py` u equivalente) — regla 18
- [ ] Backup verificado si hay migración/escritura masiva (precondiciones + conteos pre/post)
- [ ] Esquema/PK de destino confirmado contra DATA_CONTRACT_EXTRACTION.md (dimensiones de unicidad)
- [ ] git commit registrado en el log
- [ ] Universo esperado definido (571 screener / 73 audit / subset 72 CUITs / full 556)
- [ ] **Expectativa de datos definida ANTES** (conteos esperados por etapa; EXT-036)
- [ ] Cache revisado: ¿refetch necesario? ¿lastFiled nuevo? (jamás saltar "porque ya tengo fecha" — EXT-019)
- [ ] Rate limit planificado (SEC secuencial+UA real · CNV sleep/backoff/una instancia · yfinance tolerante)

## FASE 1 — EXTRACCIÓN

- [ ] HTTP OK en todas las respuestas; 403/429/timeout → backoff, no ignorar
- [ ] Respuestas vacías o inesperadamente pequeñas detectadas (umbral vs histórico)
- [ ] Documentos con guid/accession identificados; form_type clasificado (es_eeff)
- [ ] Período del documento leído (`PeriodoBalance` / start/end) — no asumido
- [ ] Unidad leída por documento (`UnidadMedida`; 339 sin unidad → monto total)
- [ ] Moneda por-fact registrada (nunca supuesto global)
- [ ] Identidad por clave canónica (CUIT/CIK); discrepancia de ticker → revisión manual (GOLD/CHA)
- [ ] Duplicados detectados y contados (no silenciosos)
- [ ] **RAW guardado ANTES de parsear** (html/json crudo inmutable)
- [ ] Hash del crudo registrado (o snapshot lo cubre)

## FASE 2 — PARSING

- [ ] Cobertura medida vs universo (no solo filas insertadas)
- [ ] Parser + parser_version registrados en el log
- [ ] Errores/descartes listados CON motivo (INSERT OR IGNORE prohibido sin log — EXT-002)
- [ ] Ambas taxonomías buscadas (us-gaap + ifrs-full) donde aplique
- [ ] Dedup serie XBRL por `end` verificada

## FASE 3 — NORMALIZATION

- [ ] factor_unidad aplicado y unit_original conservada
- [ ] Moneda normalizada con método/tasa/fecha si hubo conversión
- [ ] Perímetro resuelto explícito (tipo_balance NOT NULL; perimetro_preferido)
- [ ] Identidad canónica confirmada post-normalización
- [ ] Calendario fiscal propio aplicado (PeriodoBalance; no asumir diciembre)
- [ ] Cross-período corrió (escala rota se MARCA, no borra)

## FASE 4 — DERIVED

- [ ] Lineage citable por métrica (inputs → fórmula → valor; patrón traza L0-L5)
- [ ] formula_version registrada (cambio de fórmula = nueva versión + re-run comparativo)
- [ ] Flags cargados para todo caso especial (ni_fy, NOMINAL_sin_deflactar, fallbacks…)
- [ ] Todo NULL derivado tiene null_reason/motivo

## FASE 5 — POST-RUN / PUBLICACIÓN

- [ ] Conciliación completa (toda diferencia con explicación):
```
rows_expected    = ______   ← definido en PRE-FLIGHT
rows_downloaded  = ______
rows_parsed      = ______
rows_rejected    = ______   ← motivo por tipo
rows_normalized  = ______
rows_derived     = ______
rows_published   = ______
```
- [ ] **Conteo NO es validación suficiente** — verificar además: columnas, valores (muestra+sumas de control), NULLs, claves, hashes, rangos, fechas, distribución `[EXT-NEW-004]`
- [ ] Cobertura por universo reportada (ej.: PER sp500 X/499, no "571 filas OK")
- [ ] Cambios de escala/unidad/moneda/perímetro vs corrida anterior: ninguno sin explicación
- [ ] Staleness revisada (`staleness_dias`, `cnv_last_status.json`: deferred/stale_days)
- [ ] Sin regresión: cobertura y valores vs snapshot anterior comparados; historia no destruida ni duplicada (MERGE, nunca REPLACE)
- [ ] Contrato respetado (PK/columnas/cardinalidad de DATA_CONTRACT_EXTRACTION.md)
- [ ] API/producción: solo si corresponde publicar estado certificado o flaggeado; swap atómico cuando exista

## FIRMA DE CORRIDA

```
fecha/hora        :
script(s)         :
git_commit        :
snapshot_id       :
universo          :
resultado         : OK / OK-con-alertas / ABORTADO
conciliación      : pegar bloque FASE 5
alertas abiertas  :
```

---

### Señales de alarma = detener y auditar (de DO_NOT_REPEAT.md)

1. Conteo cambia sin explicación tras una carga.
2. Ratio cambia >10% entre corridas sin cambio de datos subyacente.
3. Magnitud absurdamente distinta a la serie (×10, ×1000).
4. Doc viejo contradice al nuevo sin marca de deprecación.
5. Script "terminó sin excepción" pero cobertura cayó.
