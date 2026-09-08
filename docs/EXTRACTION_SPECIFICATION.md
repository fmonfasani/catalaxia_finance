# EXTRACTION_SPECIFICATION.md

**Especificación definitiva de extracción — Catalaxia Finance**
v1.0 · 2026-08-22 · Fase diagnóstico/especificación (NO modifica código).
Fuente normativa base: `EXTRACTION_KNOWLEDGE_BASE.md` + `DO_NOT_REPEAT.md` (memoria acumulada; estas reglas se integran, no se reemplazan).
Etiquetado: `[DOCUMENTADO]` evidenciado en repo · `[INFERENCIA]` · `[RECOMENDACIÓN]` · `[NO DETERMINADO]`.

---

## 1. Principios

**Secuencia rectora** (`[DOCUMENTADO]`, adoptada como política):
```
PRESERVAR → TRAZAR → VALIDAR → REPRODUCIR → COMPARAR → CERTIFICAR → SIMPLIFICAR
```
La simplificación es la última etapa y JAMÁS elimina un control sin reemplazarlo.

**Tres principios rectores** (norma del proyecto):
1. *"Un número sin origen demostrable no es un dato confiable."*
2. *"Una corrección que no queda registrada es una pérdida de información."*
3. *"Una extracción exitosa es aquella que puede reconstruirse y explicarse, no simplemente aquella que terminó sin error."*

**Diferencia fundamental**: "el dato está correcto" ≠ "podemos demostrar por qué el dato está correcto". Catalaxia persigue la segunda.

**Taxonomía de error A–E** (obligatoria al investigar cualquier valor extraño — no mezclar niveles):

| Nivel | Definición | Ejemplos históricos |
|---|---|---|
| **A. Fuente mal** | El emisor/regulador publicó mal | XBRL corrupto (NMR shares ×10⁶), TM/VALE stale, filing incompleto, NIC-29 ambiguo |
| **B. Extractor mal** | Parser tomó el dato equivocado | tag equivocado (CAT sin NetIncomeLoss), código↔valor desalineado (CNV_margen TXAR) |
| **C. Normalización mal** | Transformación incorrecta | MILES vs MILLONES (EXT-001), ARS vs USD asumido (EXT-025), perímetro cruzado (EXT-008) |
| **D. Cálculo mal** | Fórmula/alineamiento temporal | TTM mal armado, PER con shares inconsistentes, payout ventana fiscal (TXAR 149%) |
| **E. Publicación mal** | Lo publicado no refleja lo calculado | ratios sin `per` tras transform parcial (EXT-005), migración destructiva (EXT-004) |

**Doctrina NULL**: NULL con motivo > dato dudoso > dato parcheado. Nunca estimar lo que falta (regla de oro de ESPEC_TAGS_RATIOS).

## 2. Fuentes

### 2.1 Clasificación primaria/secundaria/terciaria `[RECOMENDACIÓN — formalizar]`

| Rol | Fuentes | Uso permitido |
|---|---|---|
| **Primaria** (genera el dato) | SEC EDGAR (EEFF US/ADR), CNV aif2 (EEFF BYMA-only), yfinance (precios) | Única fuente de valores del gold |
| **Secundaria** (contrasta) | investing.com (manual validada), IAMC, Comafi, JPM adr.com | SOLO contraste s6/job7-style; conserva `primary_value`, `secondary_value`, `difference`, `comparison_method/date/source`. **Nunca parchea un primario faltante** |
| **Terciaria** (contextualiza) | INDEC IPC (deflactor oficial), BYVA/TIKR (descartadas) | Deflactación sí (transformación declarada, no parcheo); resto: contexto |

Detalle operativo completo por fuente (endpoints, rate limits, trampas): `EXTRACTION_KNOWLEDGE_BASE.md` §3.

### 2.2 Estándar de admisión de una fuente nueva `[RECOMENDACIÓN — bloqueante]`

Una fuente NO entra al sistema sin definir y documentar:
1. **Identidad**: mapeo a CUIT/CIK canónico (jamás razón social/ticker aislado).
2. **RAW storage**: qué crudo se persiste y dónde (inmutable).
3. **Snapshot + hash** del contenido descargado.
4. **Timestamps separados**: published/downloaded/extracted + period_start/end + as_of.
5. **Moneda y unidad originales** por dato (nunca supuesto global).
6. **Documento identificable**: guid/accession/form_type.
7. **Provenance fields** (PROVENANCE_SPECIFICATION.md) cubiertos.
8. **Parser versionado** + regla de extracción declarada.
9. **Validaciones mínimas**: identidad contable o equivalente, duplicados, schema drift.
10. **Política de errores/retry/backoff/cache/incrementalidad** escrita.
11. **Reproducibilidad**: clase A/B/C/D asignada desde el día uno.
12. **Controles post-run**: conciliación expected→downloaded→parsed→normalized→published.

Antecedentes que motivan este gate: BYVA/TIKR descartadas, scraping investing fallido (Cloudflare), `TipoDeDocumento` ausente en CNV (fuente sin campo = callejón sin salida detectado tarde).

## 3. Identidad

- **Clave canónica**: CUIT (BYMA-only/CNV) · CIK (US/ADR). Prefijos sintéticos `BYMA-{ticker}` solo para entidades sin CUIT mapeable, y SIEMPRE en columna propia de clasificación. `[DOCUMENTADO]`
- **Identidad ≠ Clasificación** `[EXT-NEW-002]`: identidad responde "¿qué entidad es?"; clasificación responde "¿qué instrumento/mercado es?" (instrument, exchange, grupo sp500/adr/byma_only). Columnas separadas; jamás inferir una de la otra. El prefijo `BYMA-*` NO prueba que la fila sea BYMA; el ticker NO prueba mercado (EXT-006: AGRO/CELU/COUR/INTR/HAVA cotizan en dos mercados).
- **Prohibido como clave**: razón social (EXT-023), nombre comercial, ticker aislado (GOLD/CHA reciclados por SEC → revisión manual explícita ante discrepancia), cik=CUIT sin columna discriminadora.
- Convención vigente con deuda abierta: CNV-nuevo usa `cik`=CUIT y `ticker`=nombre vs resto de la base (`00_VISION_GENERAL.md` §2) → normalización previa obligatoria antes de cruzar. `[DOCUMENTADO]`

## 4. RAW

- **RAW es inmutable**: HTMLs CNV (`eeff/eeff_html/{guid}.html`, `div_html/`), JSONs EDGAR (`data/raw/*.json`), respuestas crudas. Fuente de verdad; re-parseo local en segundos sin volver a tocar la fuente. `[DOCUMENTADO — lección estructural v2]`
- **Desacoplar bajar de parsear**: toda descarga guarda crudo ANTES de parsear. job5 v1 no lo hizo y obligó a re-bajar ~3 horas. `[DOCUMENTADO]`
- **Corrección protocolizada**: si hay que corregir un valor, nunca corrección silenciosa:
```
raw_value + correction_rule + correction_reason + corrected_value + corrected_at + corrected_by(version)
```
El original sobrevive siempre. Antecedente: reparación EXT-007 posible SOLO porque existía raw cache. `[EXT-NEW-005]`
- Git: solo procesado sube; crudo y DB gitignoreados (`00_VISION_GENERAL.md` §6).

## 5. Parsing

- Buscar SIEMPRE ambas taxonomías us-gaap + ifrs-full (mapeo canónico `construir_base.py::CANONICO`, prioridades `calcular_ratios_base.py::PRIORIDAD`). `[DOCUMENTADO]`
- Dedup de serie XBRL **por `end`**, jamás por `fy`. Flujo (start+end) vs foto (solo end). `[DOCUMENTADO]`
- Fallbacks declarados por concepto (NetIncomeLoss→ProfitLoss; D&A estrecho→AmortizationOfIntangibleAssets; CapEx→PaymentsToAcquireProductiveAssets). Si falta componente → ratio NULL. `[DOCUMENTADO]`
- CNV: códigos universales 7 dígitos + catálogo formtypes (`es_eeff`); ratios pre-calculados `CNV_*` PROHIBIDOS sin auditar parser propio (EXT-051).
- Parser versionado: todo cambio de layout incrementa `parser_version` (template CNV cambió ~2024+ → FASE A diagnóstica antes de re-extraer, lección PLAN_V2). `[DOCUMENTADO]`
- Bancos: plantilla distinta → detectar y rutear (parser aparte / exclusión flaggeada). `[DOCUMENTADO]`

## 6. Normalización

- Conceptos canónicos como única interfaz del motor de ratios; los tags crudos mueren en PARSED. `[DOCUMENTADO]`
- `factor_unidad()` por documento (MILES ×10³, MILLONES ×10⁶, `$`=1) — EXT-001.
- Perímetro único por ratio vía `perimetro_preferido()` (el que contiene Revenue) — EXT-008.
- Calendario fiscal propio desde `PeriodoBalance` (s2a) — 8 empresas no-calendario.
- Vintage NIC-29 = `period_end`; deflactación IPC INDEC base dic-2016=100 con flag cuando no aplica. `[DOCUMENTADO]`
- Toda normalización conserva `unit_original` + `scale_factor` (PROVENANCE §3). Hoy es gap parcial. `[DOCUMENTADO]`

## 7. Unidades

- Única verdad: `UnidadMedida` por documento CNV (`$`=1, MILES ×10³, MILLONES ×10⁶). La convención cambió ~2021; cualquier serie histórica sin `factor_unidad()` es inválida. `[DOCUMENTADO]`
- Form 339 dividendos SIN unidad → monto directo total (no por acción). `[DOCUMENTADO]`
- NIC-29 rompe unidades relativas (EBITDA TXAR/MOLA off ×4000): flag obligatorio.
- XBRL: unidad explícita por fact (`shares`, `USD-per-shares`, moneda local); nunca asumir USD.
- **Validar escala ANTES de calcular per-share** (EXT-014/050: NMR ×10⁶, DGCE ×1000).

## 8. Monedas

- **Moneda por-fact**, jamás por fuente. 11/13 ADR argentinos reportan en ARS dentro de EDGAR. `[DOCUMENTADO]`
- Bimoneda BYMA en paralelo (s1_bimoneda); conversión solo vía MEP pareado (dif_check 56/56 OK).
- CAGR dolarizado: deflactación IPC INDEC primero, MEP después; flag `NOMINAL_sin_deflactar`. S&P nominal USD.
- Diseño CCL existente NO verificado contra realidad → prohibido sin validar. `[DOCUMENTADO]`
- Valuación US/ADR: market cap + FX en `precios_y_valuacion.py`; ARS flaggeada por inflación (`fx` flag). `[DOCUMENTADO]`

## 9. Períodos

- **Tres planos temporales NUNCA mezclables** `[EXT-NEW-003 — validación automática requerida]`:
  | Plano | Campos |
  |---|---|
  | Tiempo del dato | `period_start`, `period_end`, `fiscal_year`, `fiscal_period` |
  | Tiempo de la fuente | `published_at`/`filing_date`/`filed` |
  | Tiempo del pipeline | `downloaded_at`, `extracted_at`, `as_of_date` |
  Antecedentes: `fecha_facts` pisada (EXT-019), `ultimo_periodo` falso (EXT-037), staleness invisible pre-b4.
- Ejercicio fiscal propio desde `PeriodoBalance`; TTM = estrategia C (4 trimestres exactos) con `period_ref` obligatorio. Q4 vive dentro del 10-K.
- EPS anual = último FY completo (no TTM): faltan shares trimestrales confiables. `[DOCUMENTADO]`
- `fy` XBRL = año del filing; dedup por `end`. 659 `period_end` intermedios tolerados con normalización.

## 10. Perímetros

- INDIVIDUAL vs CONSOLIDADO resuelto explícitamente en NORMALIZED (`tipo_balance` NOT NULL desde migración 002).
- Regla `perimetro_preferido()`: Revenue/COGS viven en consolidado; NI/Equity casi siempre individual; elegir el perímetro que contiene Revenue y agotarlo completo — jamás cruzar partidas de perímetros distintos (EXT-008: HAVA/GCLA/GARO contaminados; GCLA 16× de diferencia).
- PK histórica sin tipo_balance colisionaba perímetros → 13,7% documentos mutilados. Control actual: PK compuesta incluye tipo_balance.

## 11. Incrementalidad

- Re-descarga hace **MERGE incremental, nunca REPLACE con ventana** (EXT-007 borró 1.483 filas).
- Patrón correcto ya existe `[DOCUMENTADO — OPERACION.md §3]`: `run_update.py --quarterly` compara `lastFiled` de SEC vs `empresas.fecha_facts` **por CIK** y solo dispara con forms fundamentales (10-K/10-Q/20-F y /A), no 8-K/Form 4.
- ✅ Matiz EXT-019 `[RESUELTO 2026-08-22]`: `construir_base.py` ya NO salta por `fecha_facts` — invalida POR FECHA vía `_caducidad.py` (índice de presentaciones; BLOCK si el módulo falta, fin del fallback silencioso) y expone `--force-refresh` (también en `run_all.py`). `run_update.py` conserva su incremental por `lastFiled`. Deuda P1 restante: una sola capa de fetching compartida (mapa §21).
- CNV incremental: subset 72 CUITs, resume-safe por logs `log_job5_done.txt`/`log_job6_done.txt`; si CNV cae → **difiere** y registra `cnv_last_status.json` (`deferred`, `stale_days`) en vez de arrastrar dato viejo. `[DOCUMENTADO]`

## 12. Cache

- Raw cache permanente = fuente de verdad; invalidación SIEMPRE por fecha explícita de filing nuevo, jamás "si ya tengo fecha, salto" (EXT-019).
- Requerimiento pendiente: invalidación automática unificada (flag `--force-refresh` + comparación lastFiled en TODOS los entry points). `[RECOMENDACIÓN]`
- Cache de precios yfinance: staleness visible (`staleness_dias`); refresco diario `run_update.py --daily` (<1 min para 571). `[DOCUMENTADO]`

## 13. Rate limits y cortesía

| Fuente | Regla operativa |
|---|---|
| SEC EDGAR | 10 req/s compartidos declarados; pipeline usa sleep 0.15s (~6 req/s). **Nunca paralelo**. User-Agent real "Nombre email" obligatorio (403 verificado). CIK zfill(10) |
| CNV aif2 | ~0,3s/página real; sleep 0.3s extract / 1s download; tope práctico ~800 req/corrida; **una sola instancia**; paralelizar solo con `--rango` disjuntos; respiro 1–2 min entre corridas; reintentos backoff 5/10/20s; `aif.cnv.gov.ar` geo-bloqueado (usar aif2) |
| yfinance | Tolerante a fallos por ticker (`no_data` sigue); 429 → reintentar después; versión fijada tras ruptura total de la 0.2.50 (cambio de API de Yahoo sin aviso — EXT-053) |

## 14. Validaciones

1. **Identidad contable** (job7): Activo = Pasivo + PN por filing; suspects excluidos del gold (21 detectados: 11 purgados, 10 preservados bancos PCGA distinto). `[DOCUMENTADO]`
2. **Cross-período** (nueva en v2): cada período vs orden de magnitud de la historia propia → marca escala rota (no borra). Base de los checks ESCALA_JUMP de b2 (178 ALTA). `[DOCUMENTADO]`
3. **Guards yfinance** (s9): sanidad antes de aceptar precio; NULL ante duda.
4. **Expectativa primero**: toda auditoría define expectativa ANTES de ejecutar (EXT-036).
5. **Contraste externo** (s6): investing manual + IAMC + Comafi; conserva ambos valores y diferencia.
6. **Detección schema drift**: columnas nuevas/renombradas de fuente = alerta bloqueante.

## 15. Quality Gates

- Gates s5 pre-export; flags_calidad (`ni_fy`, `roe_ns`, `fx`, `mktcap_rev`) con regla de screening `WHERE flags IS NULL` (429/553 limpias). `[DOCUMENTADO]`
- Auditoría v3: b6 validación_mat (OK/WARN/INFO/FAIL por empresa×ratio) → b7 certificación (CERTIFIED/NOT_CERTIFIED + motivos: PER_2PATH_desvio, ESCALA_ALTA_xN, IDENTIDAD_balance, MARGEN_ALTA_CNV). Estado actual 487/72. Certificado = consistencia interna + provenance, NO veracidad externa. `[DOCUMENTADO]`
- **NULL sin explicación = defecto de calidad**: todo NULL derivado lleva `null_reason`/flag (hoy parcial → gap).
- "Corre sin error" ≠ "extracción exitosa": verificar cobertura por universo siempre (regla de oro OPERACION.md §5).

## 16. Provenance

Especificación completa en **PROVENANCE_SPECIFICATION.md** (7 tipos: documento/hecho/transformación/cálculo/publicación/snapshot/código + campos OBLIGATORIOS/RECOMENDADOS/OPCIONALES).

Principio nuevo `[EXT-NEW-001]`: **la huella nace en el dato crudo y viaja con él**, no se construye solo para el ratio final. Si no, dentro de un año habrá `ROE=12%` bien explicado pero imposible de rastrear al filing/tag/unidad/parser que produjo NetIncome y Equity (exactamente lo que señalan los 11 gaps vigentes).

## 17. Lineage

Cadena canónica reconstruible (ejemplo real CNV):
```
CNV doc GUID → concept 3049999 → raw_value → UnidadMedida=MILES
   → factor=1000 → NetIncome_normalized → TTM(4 trim, period_ref)
   → EPS → PER(mcap_ars/NI_ttm_ars) → screener/export/API
```
Implementaciones vivas: `payout_source`, traza LLM L0→L5 (`traza_13ratios.csv`, patrón a generalizar), motivos b7 citando check fallado. Regla: DERIVED sin lineage citable no entra al gold.

## 18. Snapshots

Un snapshot responde *"¿qué datos exactos usó esta corrida?"*:

| Campo | Estado actual |
|---|---|
| snapshot_id + timestamp | ✅ `snapshot_byma.py` certifica fuentes SHA256 antes del pipeline audit |
| files + hashes por fuente | ✅ en flujo byma/b0-b9 |
| estado DB | ⚠️ implícito; falta hash formal de tablas |
| pipeline_version + git_commit | ⚠️ parcial (no persistido en cada tabla) |
| producción | ❌ sin swap atómico ni screener_hist (EXT-040); snapshots solo locales |

Cadena exigible: FUENTE PUBLICADA → DESCARGADA → RAW LOCAL → PIPELINE → DATABASE → API, distinguible en cada eslabón. `[RECOMENDACIÓN — cerrar gaps]`

## 19. Reproducibilidad

| Clase | Definición | Componentes | Razón si no es A |
|---|---|---|---|
| **A** Rebuildable-total | Sin red, determinista desde RAW/PARSED | s0,s1,s2,s2a,s4,s7*,s8 · b1–b9 · traza LLM · calcular_ratios_base | — |
| **B** Red-determinista | Reconsulta fuente, idempotente por clave canónica | jobs CNV 1–8 · extractores EDGAR (01–07, construir_base) · yfinance s3/s3b/s3c/s9 · run_update | necesita red; rate limits |
| **C** Manual-dependiente | Intervención humana o fuente opaca | carga investing validada · IAMC slug · Comafi scraping · monitoreo INDEC manual | irreproducible sin humano |
| **D** Irreproducible | No reconstruible | (a) precios .BA no bajados a tiempo (retroactivo limitado); (b) contraste investing histórico puntual; (c) datos sobrescritos sin raw previo (solo se salvó lo que tenía cache — EXT-007); (d) PDFs CNV nunca descargados (solo HTML público) | cada una documentada en KB §19.2 |

Regla: toda pieza nueva nace declarando su clase. Clase C/D exige mitigación (guardar crudo, timestamp, hash) para degradar su impacto.

## 20. Publicación

- Cadena: SQLite local → `deploy/sincronizar_a_produccion.py` → PostgreSQL VPS (docker catalaxia-db PG16) → API FastAPI (11 endpoints). Export versionado: `data/screener_export.csv`. `[DOCUMENTADO]`
- Provenance de publicación exigible: qué snapshot + pipeline_version + git_commit produjo lo publicado (`[RECOMENDACIÓN]` hoy ausente).
- Deudas conocidas: swap atómico inexistente (riesgo de publicar estado mixto), `screener_hist`/`/v2/hist` prometido y nunca implementado (500), producción/local desalineados hasta migraciones 002/003 del 2026-08-22.
- Regla: producción recibe SOLO estados certificados (b7-style) o con flags visibles; jamás estados intermedios de transform.

## 21. No regresión

Patrones de recurrencia detectados (problema → cómo volvió → control faltante → cómo hacerlo imposible):

| Problema original | ¿Cómo volvió a ocurrir? | Control que faltó | Imposibilidad propuesta |
|---|---|---|---|
| Clave sin discriminador (precios EXT-006: moneda) | Misma clase en EEFF: PK sin tipo_balance → EXT-002 mutiló 13,7% docs | Test de unicidad por dimensiones de negocio al diseñar PK | Contrato de tabla con dimensiones de unicidad declaradas + test de colisión I/C en CI |
| Overwrite parcial (EXT-005 borra `per`) | `calcular_ratios_base` dropea `ratios`; patrón repetido en fixes manuales | Apareo obligatorio + verificación de cobertura post-transform | run_all aparea; gate post-transform verifica columnas/cobertura esperadas |
| Cache eterno (EXT-019) | Solución correcta (`run_update` incremental) convivió con path roto (`run_all` saltea cacheados) sin consolidarse | Un solo entry point de descarga | Capa única de fetching compartida; prohibido duplicar lógica skip/refetch |
| Descarte silencioso (INSERT OR IGNORE, EXT-002) | Duplicación masiva por cambio de formato de clave (EXT-009, 190.737 filas) | Log obligatorio de descartes/duplicados | Toda carga reporta rows_inserted/rejected/duplicated con motivos |
| Unidad mal interpretada (EXT-001) | Reapareció como ambigüedad NIC-29 en EBITDA (EXT-029) | Flag sistemático cuando la unidad es derivable-no-explícita | Regla: unidad SIEMPRE columna, jamás contexto; flag NOMINAL/ambiguo |
| Migración destructiva (EXT-004) aprobada en papel | Doc de plan viejo decía "listo producción" y se ejecutó tal cual | Checklist pre-migración + marca SUPERSEDED en docs | EXTRACTION_CHECKLIST PRE-FLIGHT + política documental (KB §22/§25) |
| Cambio de fórmula sin re-validación (payout TXAR 149%→516%) | Ventana cambiada sin re-corrida comparativa histórica | Fórmulas versionadas + diff automático | `formula_version` obligatorio + re-run comparativo ante cualquier cambio |

Lección general `[INFERENCIA]`: casi toda regresión fue un problema YA documentado que volvió por (1) segundo entry point sin el control, (2) clave/contrato débil, o (3) corrección manual no scriptificada. Los controles EXT-NEW-001..012 existen para cerrar exactamente esas tres vías.

## 22. Auditoría

Método canónico (validado en audit v3): snapshot/hash ANTES → universo b0 → partidas b1 → anomalías con expectativa declarada (b2) → TTM/mercado/métricas (b3-b5) → validación matricial empresa×ratio (b6) → certificación con motivos (b7) → reporte vivo (`docs/10-auditoria-*.md`) → traza L0–L5 verificable (b9).
Reglas: expectativa antes de ejecutar; "corre sin error" ≠ éxito; cobertura por universo como métrica principal; todo hallazgo clasificado por taxonomía A–E.

## 23. Contratos

Toda tabla compartida entre scripts exige contrato: PK + dimensiones de unicidad, columnas/tipos/nullability, semántica, raw_reference, provenance mínima, writer(s), reader(s), validaciones, cardinalidad esperada. Definiciones por dataset en **DATA_CONTRACT_EXTRACTION.md**. Tabla compartida sin contrato = riesgo activo (antecedentes EXT-002/005).

## 24. Checklist

Checklist ejecutable por corrida en **EXTRACTION_CHECKLIST.md**: PRE-FLIGHT → EXTRACTION → PARSING → NORMALIZATION → DERIVED → PUBLICATION, con conciliación `rows_expected→downloaded→parsed→rejected→normalized→derived→published` y explicación obligatoria de cada brecha. `[EXT-NEW-008]`

## 25. Reglas no negociables

Fuente normativa: **DO_NOT_REPEAT.md** (reglas 1–20 + señales de alarma) — se integra íntegramente, no se reemplaza. Se agregan las reglas derivadas del análisis de no-regresión y provenance:

| ID | Regla nueva | Origen |
|---|---|---|
| EXT-NEW-001 | La huella nace en el dato crudo y viaja con él hasta la publicación | 11 gaps de provenance |
| EXT-NEW-002 | Identidad ≠ Clasificación; columnas separadas, jamás inferidas | EXT-006 + prefijos BYMA-* |
| EXT-NEW-003 | Tres planos temporales separados y validados automáticamente | EXT-019/037 |
| EXT-NEW-004 | El conteo nunca es validación suficiente (columnas/valores/nulls/hashes) | EXT-002/004 |
| EXT-NEW-005 | Toda corrección registrada (rule/reason/by/at); jamás silenciosa | Reparación EXT-007 |
| EXT-NEW-006 | Fuente secundaria nunca parchea primario; contraste conserva ambos valores | s6/investing manual |
| EXT-NEW-007 | Doc viejo se marca DEPRECATED/SUPERSEDED al publicar el nuevo | Contradicciones 7 y 11 |
| EXT-NEW-008 | Conciliación expected→…→published con explicación por brecha | EXT-036 + job5 whitelist 630/2145 |
| EXT-NEW-009 | Estándar de admisión bloqueante para fuentes nuevas (§2.2) | BYVA/TIKR/scraping/TipoDeDocumento |
| EXT-NEW-010 | Taxonomía de error A–E obligatoria al investigar anomalías | §1 |
| EXT-NEW-011 | Dependencia externa puede romperse sin aviso: versión fijada + guard de sanidad previo | EXT-053 (yfinance 0.2.50 roto 100%) |
| EXT-NEW-012 | Mapping ticker→CIK exige revisión manual ante discrepancia (tickers reciclados) | GOLD/CHA |

### Criterio de éxito (respuestas hoy)

| Pregunta | Respuesta | Evidencia / gap |
|---|---|---|
| A ¿De dónde salió cualquier dato? | 🟡 PARCIAL | OBLIGATORIO cubierto desde migr 002; accn/decimales no propagados (gap 1-2) |
| B ¿Distinguir original vs transformado? | 🟢 SÍ en diseño RAW/PARSED/N/D | falta correction_log formal |
| C ¿Reconstruir cualquier métrica? | 🟢 SÍ para BYMA v3 (traza L0-L5) | generalizar a US/ADR |
| D ¿Detectar destrucción de historia? | 🟢 SÍ si hubo snapshot/raw | sin snapshot previo = NO |
| E ¿Detectar duplicación? | 🟢 SÍ con log de descartes; ❌ sin él | EXT-009 |
| F/G ¿Cambios de escala/unidad? | 🟢 SÍ | b2 ESCALA_JUMP + cross-período |
| H/I ¿Cambios de moneda/perímetro? | 🟢 SÍ | moneda por-fact + tipo_balance NOT NULL |
| J ¿Datos stale? | 🟢 SÍ | staleness_dias + cnv_last_status.json |
| K ¿Regresión vs versión anterior? | 🟡 PARCIAL | requiere screener_hist + diff versionado |
| L ¿Comparar contra fuente primaria posterior? | 🟢 SÍ | s6/job7 conservando ambos valores |
| M ¿Qué código produjo un valor? | 🟡 PARCIAL | git_commit/parser_version no persistidos (gaps 4-6) |
| N ¿Reproducir una corrida antigua? | 🟢 SÍ en flujo b* con snapshot_id | producción sin swap atómico |

Gaps abiertos A/M/N → ver PROVENANCE_SPECIFICATION.md §8 y KB §18 backlog.

---
*Cierre de fase: este documento es especificación, no código. La consolidación de capas/scripts se decidirá en segunda fase sobre el mapa de duplicaciones (KB changelog v2).*
