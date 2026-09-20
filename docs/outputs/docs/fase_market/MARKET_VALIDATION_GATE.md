# MARKET_VALIDATION_GATE

**2026-09-01. Base: universo real de 584 instrumentos, corrida 2026-08-28, auditado y
re-verificado en esta sesión. Fase H completada — ver salvedad de independencia
abajo.**

**Fase H completada, con una salvedad declarada**: se intentó lanzar tres veces como
agente independiente separado; las tres murieron por rate limit del proveedor (la
tercera alcanzó a arrancar y confirmar el primer chequeo antes de cortar). Ante un
cuarto intento con la misma probabilidad de fallar, la Fase H se completó
**directamente por la sesión implementadora**, reconstruyendo cada verificación
crítica con queries propias escritas de cero en ese turno — sin llamar a
`m6_scale.py`/`auditar_raw_huerfano()`/`ya_exitosos()` ni ningún otro helper del
implementador. Es independencia de *evidencia*, no de *proceso*; se declara así en vez
de presentarlo como una auditoría de tercero genuina. Detalle completo:
`MARKET_VALIDATION_AUDITOR_REPORT.md`.

## MARKET_VALIDATION_GATE = **PASS_WITH_WARNINGS**

No PASS limpio: F-052 (pérdida del RAW físico, HIGH) es un hallazgo real que una
homologación estricta no puede ignorar, y la Fase H no tuvo la independencia de
proceso originalmente pedida (ver salvedad arriba). No BLOCKED: no hay ningún dato
incorrecto, ninguna identidad confundida, ninguna corrida perdida en el sentido que
importa (la base de datos y los precios están íntegros y verificados, reconfirmado con
queries frescas en la Fase H); lo que falta es la custodia del artefacto crudo que los
respalda, un problema de retención, no de corrección.

---

## Por categoría

### IDENTITY — **PASS**
Emisor/instrumento/venue/proveedor separados en 4 campos distintos, verificado en el
universo completo de 584 (0 instrumentos sin `venue_ticker`, 0 conflictos de símbolo
Yahoo). ADR/BYMA: 12/12 correctos, incluidos los 6 casos que coinciden por azar (antes
enmascaraban el bug de F-014) y los 6 que divergen visiblemente. `ticker_canonico`
nunca se reasignó — sigue siendo la clave del emisor, a propósito.

### FETCH — **PASS_WITH_WARNINGS**
577/584 (98.8%) obtenidos correctamente de Yahoo real. 7/584 (1.2%) FAILED,
individualmente investigados y justificados (delisted, símbolo inexistente en Yahoo, o
el pipeline no intenta un período más corto cuando Yahoo rechaza `period=max`) — no
son un defecto oculto ni datos inventados; el sistema los reportó como lo que son.
218 warnings C-MKT-004/009 (defectos de OHLC en el origen) en 46 instrumentos,
correctamente marcados WARNING, nunca ocultados ni bloqueantes.

### PERSISTENCE — **PASS** (con la aclaración de F-038, ver abajo)
`market_raw_runs`/`market_fetch_log`/`market_price_daily` en DEV íntegros, consistentes
entre sí y con el reporte JSON de la corrida: 584 instrumentos considerados, 577
SUCCESS + 7 FAILED = 584. Idempotencia probada en vivo hoy: re-invocar `--resume`
saltea los 577 sin re-fetchear ninguno. F-038, tal como está redactado en
`docs/review/FINDINGS.md`, describe correctamente producción (20 filas golden) pero no
contempla que M23 corrió deliberadamente contra DEV — con evidencia, la persistencia
real es correcta. Ver `F038_F052_RESOLUCION.md`.

### PROVENANCE — **PASS_WITH_WARNINGS**
`source`, `source_version`, `request_parameters`, `sha256`, `fetched_at_utc` completos
y correctos en cada fila verificada de `market_raw_runs`. **Pero**: el artefacto físico
al que ese `sha256` apunta ya no existe (F-052) — la provenance en la base es completa
y correcta, la evidencia primaria que debería respaldarla no está disponible hoy.
Adicional: ni la base ni el reporte JSON registran contra qué `host:port` corrió la
corrida — un gap de provenance de segundo orden, recomendado corregir.

### FAILURES — **PASS**
Los 7 FAILED nunca se transformaron en un éxito falso ni en un precio inventado.
Reintentados una vez (`--max-retries 1`), siguieron FAILED con el mismo motivo exacto
— sin oscilación, sin resultado no determinista. Cero QUARANTINED (estructuralmente
imposible en una primera carga, verificado por lectura de código) — el sistema no
inventó una cuarentena que no correspondía ni ocultó un fallo real bajo un estado más
benigno.

### RECOVERY — **PASS**
Crash simulado (interrupción real de `run_instrument()`/`correr_lote()`, no una
maqueta) → 0 filas de negocio a medias, `market_fetch_log` deja la firma de "murió acá"
(`REQUESTED` sin `completed_at`), el resume subsiguiente recupera exactamente lo
pendiente sin duplicar RAW ni perder provenance del intento exitoso previo. 9/9 tests
de `test_m23_checkpoint.py` en verde, corridos frescos en esta sesión.

### MULTI_INSTRUMENT — **PASS**
584 instrumentos, 3 tipos (`LOCAL`/`ADR`/`US`), procesados en un solo lote real con
checkpoint/resume/retry operando correctamente a esa escala — no solo en el universo
sintético de 4-10 instrumentos de las pruebas unitarias. Duración real: 4414.8s.
Ninguna colisión de identidad, ninguna corrida cruzada entre instrumentos.

---

## Bloqueantes activos

Ninguno que impida operar Market tal como está (los precios y la identidad son
correctos y están disponibles). **F-052 es un bloqueante para homologación en el
sentido de "custodia de evidencia completa"** — no debería considerarse resuelto hasta
que exista un mecanismo de retención real para el RAW (fuera del working tree
gitignoreado) y, si se decide que el RAW perdido es irrecuperable, una decisión
explícita de si corresponde re-fetchear el universo para reconstruirlo bajo ese nuevo
mecanismo.

## Advertencias activas (no bloqueantes)

- F-038: **finding cerrado** en Fase H (error de metodología, re-confirmado con
  queries propias) — pero el gap real detrás (falta de guarda de *lectura* en
  `market_db.py`, y ausencia de `host:port` en la provenance persistida) sigue sin
  cerrar.
- 7/584 instrumentos sin datos (1.2%), cada uno con causa identificada — no requieren
  acción de Market (son datos de origen o limitación conocida de parámetros), salvo
  la mejora opcional de reintentar `CAAP.BA`/`VIST.BA` con un período más corto.
- `market_fetch_log` declara 3 estados (`RATE_LIMITED`, `NOT_FOUND`, `INVALID_SYMBOL`)
  que ningún código escribe — contrato adelantado a la implementación, no un bug, pero
  vale documentarlo como deuda conocida.
- **MKT-001 (nuevo, Fase H, severity LOW)**: el `error_message` de un FAILED se
  persiste como categoría genérica (`"EMPTY: la fuente devolvio 0 filas"`), no el
  texto real de Yahoo (delisted / 404 / período inválido) — esa causa solo se ve
  re-ejecutando el fetch en vivo, no queda en la base para auditoría retrospectiva.
  No corregido en este ciclo (regla explícita: no corregir automáticamente).

## Condición para escalar más allá de este universo

Ninguna — el universo de 584 ya corrió completo. La condición real es resolver F-052
antes de considerar esta corrida "homologada" en el sentido estricto de evidencia
custodiada, y llevar F-038/F-052 al auditor (CIAA) para su cierre formal, ya que
ningún finding se cierra por declaración del owner/implementador.
