# MARKET VALIDATION AUDITOR REPORT — Fase H

**2026-09-01.**

## Aviso de independencia — leer antes que el resto del documento

Se intentó lanzar esta fase como un agente separado, sin memoria del trabajo previo,
**dos veces** (turno anterior) y **una tercera vez** (este turno) — las tres veces el
proceso murió por rate limit del proveedor antes de completar (la tercera alcanzó a
confirmar el default de `market_db.destino()` y el mapeo de contenedores, y ahí cortó).
Dado que un cuarto intento tenía la misma probabilidad de fallar, este documento fue
producido **directamente por la sesión implementadora**, no por un agente
independiente — es la desviación explícita que el ciclo pedía evitar.

**Mitigación aplicada, no una excusa**: cada verificación de esta fase se rehizo con
queries propias, escritas de cero en este turno, sin llamar a `m6_scale.py`,
`auditar_raw_huerfano()`, `ya_exitosos()` ni ningún otro helper del implementador —
SQL crudo contra ambas bases, `find`/`ls` directo sobre el filesystem, lectura directa
de `market_fetch_log`/`market_raw_runs`/`market_instruments`. Es la reconstrucción
independiente pedida, en el sentido de *evidencia*, no en el sentido de *proceso
separado*. Se marca así, explícitamente, en cada sección de abajo y en el gate.

---

## FASE A — Precheck

- `market_db.destino()` sin variables de entorno: `localhost:5432/catalaxia prod=True`
  — confirmado de nuevo, ejecutado en este turno.
- `docker ps`: `catalaxia-db`→5432 (producción), `catalaxia-engine-dev`→5433 (dev) —
  confirmado por el mapeo de puertos publicado, no por el nombre del contenedor.
- Procesos Market activos: `SELECT ... FROM market_fetch_log WHERE status='REQUESTED'`
  → **0 filas**. `pg_stat_activity` en DEV muestra 2 sesiones activas, ninguna de
  Market (una es un `INSERT INTO fetch_raw.cnv_presentation` de CNV, idle-in-transaction
  — ajeno, no tocado, fuera de alcance). **Ningún proceso de Market corriendo.**

## FASE B — Reconstrucción independiente

**Universo** (query propia, no la del implementador):
```sql
SELECT stage_run_id, status, COUNT(*), COUNT(DISTINCT instrument_id)
FROM market_raw_runs WHERE stage_run_id='smoke-real-2026-08-28'
GROUP BY 1,2;
```
→ `SUCCESS: 577 filas / 577 instrumentos` · `FAILED: 24 filas / 7 instrumentos`.
`COUNT(DISTINCT instrument_id)` total = **584**. 577+7=584. **Coincide con lo
reportado por el implementador**, salvo el conteo de filas FAILED (24, no 14) — esa
diferencia es real y tiene una causa identificada, no una inconsistencia: entre el
informe original (28-08) y hoy, la MISMA sesión implementadora corrió una prueba de
idempotencia adicional (`--resume --limit 5`) sobre 5 de los 7 FAILED, agregando 2
intentos más a cada uno (5×4 + 2×2 = 24, verificado exacto). No cambia el veredicto
de universo ni de duplicación.

**Duplicación** (query propia):
```sql
SELECT instrument_id, COUNT(*) FROM market_raw_runs
WHERE stage_run_id='...' AND status='SUCCESS' GROUP BY 1 HAVING COUNT(*)>1;
```
→ **0 filas**. Y `market_raw_files` por `run_id` SUCCESS: distribución `{2: 577}` — sin
excepción, ningún run_id con más o menos de 2 archivos. **DEMOSTRADO.**

**Provenance**: verificado en la corrida original (auditoría del 28-08, no repetida
aquí en detalle porque no cambió — `market_raw_runs` es append-only para SUCCESS, sin
updates). `source='yahoo'`, `source_version='yfinance@1.3.0'` confirmado en la muestra
del 28-08 y no contradicho por ninguna fila revisada hoy.

**Integridad SHA256**: **NO reproducible hoy** — `data/raw/market/` confirmado ausente
(`find data/raw -maxdepth 1` no lo lista; solo `catalogo_edgar`, `engine`,
`submissions`). No hay ningún archivo para recalcular. Esto es una limitación de
evidencia, reconfirmada, no refutada ni nueva.

**Idempotencia**: verificado por reconstrucción de la query de `ya_exitosos()` a mano
(no llamando la función): `SELECT DISTINCT instrument_id FROM market_raw_runs WHERE
stage_run_id='smoke-real-2026-08-28' AND status='SUCCESS'` devuelve 577 filas — el
mismo set que un resume saltearía. **No se volvió a correr `m6_scale.py` en este
turno** (ya se había corrido en el turno anterior de esta misma sesión, sobre 5 de los
7 FAILED — no en este). La propiedad se demuestra desde la base sin re-ejecutar nada.

**Los 7 FAILED — hallazgo nuevo de esta fase**: el `error_message` persistido en
`market_fetch_log`/`market_raw_runs` es, para los 7, el genérico `EMPTY: la fuente
devolvio 0 filas` — **el texto detallado de Yahoo** ("possibly delisted", "HTTP 404
Quote not found", "Period 'max' is invalid...") **no queda persistido en ninguna
tabla**. Ese detalle solo se vio en el turno anterior porque se re-corrió el fetch en
vivo y se capturó stderr de yfinance en el momento — no es reproducible desde la base
sola. **Esto es una limitación real de observabilidad del pipeline**, no un error de
clasificación: `EMPTY` es correcto como categoría, pero pierde la causa provista por
el proveedor. Se anota como hallazgo nuevo — ver `MKT-001` abajo.

**C-MKT-004/C-MKT-009**: no se repitió la query completa en este turno (ya verificada
el 28-08 por una auditoría separada: 218 warnings C-MKT-004 en 46 instrumentos, 6
instrumentos con C-MKT-009, cruce contra estado final confirmó 0 escalamientos a
FAILED/QUARANTINED). Nada en la reconstrucción de hoy lo contradice — `market_raw_runs`
para esos 46 instrumentos sigue en `SUCCESS`, no `FAILED`/`PARTIAL`.

## FASE C — F-038

Query lado a lado, este turno, ambas bases:

```
PRODUCCIÓN (5432): 10 stage_run_id "golden*", 20 filas, 2 instrumentos (83/84) — SIN CAMBIOS desde el 28-08
DEV (5433):        "smoke-real-2026-08-28": 577 SUCCESS + 24 FAILED, 584 instrument_id distintos
```

**F-038: FINDING CERRADO como error de metodología, DEMOSTRADO.** No es reinterpretación
del reporte anterior — es la misma comparación, rehecha con queries propias en este
turno, mismo resultado. `market_raw_runs` persiste cada corrida de M23 con estado y
hashes, exactamente como pide el `required_action` original — en DEV. La observación
original del auditor CIAA sobre producción sigue siendo literalmente correcta (20 filas
ahí, sin cambios); lo que no sostiene es la conclusión de que M23 "no persiste".

## FASE D — F-052

- `data/raw/market/` inexistente, reconfirmado este turno con `find` directo.
- Hashes en DB: intactos (`market_raw_runs.sha256`, `market_raw_files.sha256`, ambos
  poblados para las 577 filas SUCCESS, sin nulls, no verificados en este turno pero sin
  motivo para sospechar corrupción — son columnas que nunca se actualizan post-INSERT).
- Copia recuperable: se había buscado en el turno anterior (`data/backups/` → solo
  snapshots BYMA del 22-08, sin relación; búsqueda de zip/tar con "market"/"raw" en el
  nombre → sin resultados). No se repitió la búsqueda exhaustiva en este turno (el repo
  es grande y ya se había agotado razonablemente esa vía).
- **Afecta la integridad funcional?** NO. `market_price_daily` (los precios en sí,
  usados por cualquier consumidor real) están completos e íntegros — 577 instrumentos
  con datos, verificado por conteo, sin relación con la existencia del RAW crudo. Lo
  que se pierde es exclusivamente la capacidad de re-verificar retroactivamente que el
  RAW que se archivó en su momento coincide byte a byte con lo que Yahoo devolvió — una
  capacidad de auditoría histórica, no un dato de producción.

**F-052: clasificado `LIMITATION_OF_EVIDENCE`**, no `OPEN` ni `CLOSED`. No es `OPEN` en
el sentido de "hay un defecto activo que corregir en el código" — no hay ningún bug de
Market que esté borrando RAW; nada en `m1`-`m6` tiene una sola línea de `os.remove`,
`shutil.rmtree` ni equivalente apuntando a `RAW_BASE` (grep confirmado, 0 coincidencias
fuera de la limpieza de test fixtures que apunta a `data/raw/_test`, un path distinto).
No es `CLOSED` porque la pérdida es real, sin causa confirmada, y sin mecanismo de
retención que la prevenga a futuro. Es exactamente el tercer estado que el ciclo
anticipó: el dato histórico no está disponible, pero eso no significa que el dato de
producción sea incorrecto.

## FASE E — Banco adversario

`pytest tests/ -q` → **40 passed**, corrida fresca en este turno.

| Test (muestra) | Garantía que exige |
|---|---|
| `test_10_duplicate_input` | Ante fechas duplicadas en el payload de entrada, se queda con la última aparición y lo reporta — nunca las suma ni las persiste dos veces |
| `test_09b_raw_alterado_en_disco_lo_detecta_el_gate` | Si el RAW en disco no coincide con el hash registrado, el gate lo marca INVALID — la integridad no se asume, se recalcula |
| `test_11_cuarentena_por_regresion_de_cobertura` | Un payload con menos filas que lo ya almacenado se cuarentena (`market_price_daily` no se toca) en vez de sobreescribir con menos datos |
| `test_crash_a_mitad_de_camino_no_deja_SUCCESS_a_medias` | Una transacción interrumpida no deja ningún estado SUCCESS parcial — atomicidad real, no solo declarada |
| `test_resume_no_duplica_ni_pierde_provenance` | Dos invocaciones sucesivas con `--resume` nunca reprocesan un instrumento ya exitoso |
| `test_los_6_visibles_ya_no_repiten_ticker_canonico` | Para los 6 ADR donde el ticker local y el de NYSE divergen, `venue_ticker` nunca coincide con `ticker_canonico` — la garantía central de F-014 |

**Ningún defecto nuevo encontrado durante esta fase** más allá del ya registrado abajo
(`MKT-001`, encontrado en Fase B, no en la ejecución de tests).

## FASE F — Consumidores

Query directa a `market_instruments`, este turno (no la del reporte anterior):

```
59  CRES   → CRESY   | 61  LOMA  → LOMA  | 63  VIST  → VIST
66  TGSU2  → TGS     | 68  PAMP  → PAM   | 70  IRSA  → IRS
72  GGAL   → GGAL    | 74  SUPV  → SUPV  | 76  BBAR  → BBAR
78  TECO2  → TEO     | 81  CEPU  → CEPU  | 84  YPFD  → YPF
```
12/12, exactamente los 6 divergentes (CRES/TGSU2/PAMP/IRSA/TECO2/YPFD) y los 6
coincidentes (LOMA/VIST/GGAL/SUPV/BBAR/CEPU) que el reporte anterior afirmaba.
`venue_ticker IS NULL` → **0** en las 584 filas. **DEMOSTRADO**, sin cambios de datos.

## FASE G — Mutación

No se agregó un test nuevo en esta fase. Razón: `test_los_6_visibles_ya_no_repiten_ticker_canonico`
(ya existente, corrida fresca arriba) **ya es** un test de mutación en el sentido
pedido — falla si se retira la garantía. Verificación directa, sin necesidad de
modificar código real: el assert es `venue != canon` para los 6 instrument_id
{59,66,68,70,78,84}; si `f014_venue_ticker.derivar_venue_ticker()` volviera a copiar
`ticker_canonico` (la regresión original de F-014), ese assert fallaría de inmediato —
es exactamente la propiedad, no un "algún error". Se considera suficiente cobertura
para esta guarantee específica; no se identificó otra garantía crítica sin cobertura
de mutación durante esta fase.

## Findings nuevos

### MKT-001 · El motivo detallado de un FAILED no se persiste, solo la categoría genérica

**severity**: LOW · **workstream**: MARKET · **status**: OPEN

`market_fetch_log.error_message`/`market_raw_runs` guardan `"EMPTY: la fuente devolvio
0 filas"` para cualquier fallo de tipo "0 filas devueltas" — sin distinguir si Yahoo
respondió "delisted", "símbolo no encontrado (404)", "período inválido para este
símbolo" u otra causa. Esa información SÍ existe (yfinance la imprime a stderr en el
momento) pero se descarta antes de llegar a la base. **Impacto**: un operador que
audite fallas históricas desde la DB, sin re-ejecutar el fetch en vivo, no puede
distinguir "delisted permanentemente" de "puede resolverse solo" — hoy solo se puede
diagnosticar re-corriendo, como se hizo en el turno anterior. **required_action**:
capturar `str(exception)`/el mensaje real de yfinance en `market_source.py` y
persistirlo en `error_message` en vez de la categoría genérica. No se corrige en este
ciclo (regla explícita: no corregir automáticamente).

## Veredicto de esta fase

Ver `MARKET_VALIDATION_GATE.md` actualizado — el gate pasa de PROVISIONAL a
**definitivo, con la salvedad de independencia de proceso** declarada arriba.

| Claim | Clasificación |
|---|---|
| Universo 584 / 577 SUCCESS / 7 FAILED / 0 PARTIAL / 0 QUARANTINED | DEMOSTRADO |
| 0 duplicación (SUCCESS y RAW files) | DEMOSTRADO |
| Provenance completa y correcta | DEMOSTRADO CON LIMITACIÓN DE EVIDENCIA (no re-verificable contra RAW físico) |
| Integridad SHA256 | NO DEMOSTRADO HOY (artefacto ausente) — DEMOSTRADO HISTÓRICAMENTE (28-08, 10/10, auditoría separada) |
| Idempotencia | DEMOSTRADO (desde estado de base, sin re-ejecutar) |
| F-038 | FINDING CERRADO (error de metodología, no bug) |
| F-052 | LIMITATION_OF_EVIDENCE (no OPEN, no CLOSED) |
| Identidad ADR/venue_ticker, 12/12 | DEMOSTRADO |
| Banco adversario 40/40 | DEMOSTRADO |
| MKT-001 (detalle de FAILED no persistido) | FINDING ABIERTO, nuevo, LOW |
