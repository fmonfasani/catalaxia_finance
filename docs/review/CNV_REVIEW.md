# CNV — AUDIT REVIEW

Auditor: **CIAA** · Ciclo **AUDIT-02** · Baseline `444ee1a`
Objeto: **C3 Fetcher** tras los fixes · checkpoint `8db8692ebce9439c8be69cbaf5c82979`,
corrida vigente `eb05375b34434923a69cf34a59591c5c` (run6)

## VEREDICTO

**BLOCK LEVANTADO → PASS_WITH_WARNINGS.**

En AUDIT-01 bloqueé la certificación de C3 porque un gate bloqueante de identidad
(`C-C3-007`) no podía fallar. **Ese defecto está corregido y lo verifiqué funcionando.**
El bloqueo se levanta.

Quedan tres condiciones abiertas que **no justifican bloquear** pero sí impiden certificar
sin reservas: F-003 (residual), F-007, F-008.

---

## `C-C3-007` — corregido en lo esencial, incompleto en lo estructural

**Antes** (AUDIT-01): leía `estado_c2`/`estado`, columnas inexistentes → todo `None` →
`cerradas` estructuralmente vacío → **falso PASS**.

**Ahora** (`c3_cnv_fetch.py:549`): lee `status` primero. Simulación sobre el CSV real:

| # | Escenario | Resultado | |
|---|---|---|---|
| 1 | CSV intacto | PASS leyendo `OPEN`/`RESOLVED`/`PARTIAL` | **mide de verdad** |
| 2 | `C1-R-001` → `CLOSED` | **FAIL** | **el gate ya puede fallar** ✓ |
| 3 | columna renombrada | PASS silencioso | ✗ |
| 4 | CSV ausente | PASS con *"3/3 intactas"* | ✗ |

El escenario 2 es lo que levanta el BLOCK: el control **ya detecta lo que existe para
detectar**. Los escenarios 3 y 4 muestran que la *clase* de defecto sigue alcanzable, ahora
por ausencia de datos en vez de por nombre equivocado (**F-007**).

Falta también la red de regresión: los 8 tests nuevos **no cubren `C-C3-007`**.

---

## `canonical_sha256` — bien diseñado y verificado independientemente

Reimplementé los dos regex sin importar el módulo del worker, para no heredar un eventual
defecto de esa misma implementación.

**Diseño** (`engine/cnv/rawstore.py:59-79`): dos patrones (`?v=GUID` de cache-busting y
`RequestVerificationToken`), aplicados sólo a `EMPRESA_PAGE`/`VISOR`, con la nota explícita
*"NOT used for RAW storage/addressing"*. Acotado exactamente a lo que AUDIT-01 demostró que
era ruido, sin ampliar el alcance.

**Pruebas sobre 75 pares de capturas reales:**

```
P1  hash CRUDO igual        :  0/75      (confirma el problema original)
    hash CANÓNICO igual     : 74/75      (confirma que converge)
P3  RAW con token real      : 74/75
    RAW con 'CANON' escrito :  0/75      <- EL RAW NO FUE REESCRITO
```

**P3 era el riesgo mayor del fix** — que la canonicalización contaminara el RAW — y quedó
descartado empíricamente. La inmutabilidad del RAW se sostiene.

### El 1/75 que no converge es correcto, y es la mejor prueba de sensibilidad

`EMPRESA_PAGE` no converge. Investigado: tras canonicalizar quedan **198 líneas de
diferencia**, y el contenido es **real** — una presentación nueva publicada por CNV entre
capturas (*"24 ago. 2026 · Banco Comafi S.A."*).

La canonicalización **dejó pasar un cambio genuino**. Es mejor evidencia de que no enmascara
sustancia que cualquier mutación sintética que yo pudiera fabricar. También revela una
propiedad del dominio: `EMPRESA_PAGE` es un recurso **vivo**, de modo que su idempotencia es
inherentemente acotada en el tiempo y romperla es el comportamiento esperado cuando CNV
publica.

---

## `C-C3-006` — corregido, con la premisa redefinida y declarada

Resultado en run6:
```
comparados contra corrida previa=75/75 · sin_precedente=0
idénticos en sustancia=75 · cambios reales=0 (esperado 0)
```

Y a continuación, en el mismo `detail`:
```
escrituras RAW nuevas=75 de todos modos
   -- eso ya NO es lo que este check mide
```

**Esa franqueza es lo que permite adjudicar F-004 como SUPERSEDED en vez de dudoso.** El
check no fue arreglado para dar PASS: fue redefinido —de identidad de bytes a identidad de
sustancia— y el cambio de premisa quedó escrito en la propia evidencia. Es una decisión
legítima y bien implementada.

El residual (el RAW sigue creciendo) se traslada a **F-008**, verificado:

```
data/raw/engine/cnv    AUDIT-01: 152 archivos
                       AUDIT-02: 377 archivos · 51 MB     (3 corridas × 75)
```

---

## Lo verificado que se sostiene

| Claim | Verificación |
|---|---|
| 8 tests agregados | **8 passed** · 4 de canonicalización + 4 de perímetro |
| 3 corridas reales adicionales | `39d072db`, `74c2e4f3`, `eb05375b` en `cnv_download_log` |
| PASS 10/10 | run6, los 10 checks en PASS |
| Idempotencia 75/75 | verificada **en sustancia** |
| RAW intacto | 0/75 con `CANON`; 74/75 con token real |
| Checkpoint reutilizado | mismo `checkpoint_id`, `run_id` actualizado a run6 |
| C-C3-002 integridad RAW | 75/75 sin mismatch |
| Scope | 1.861/1.861 filas y 150/150 artefactos de un solo CUIT |

**Frontera del fix visible en los datos:** las 3 corridas previas al cambio tienen
`canonical_sha256` NULL; las 3 posteriores lo tienen 75/75. La transición es limpia y
auditable.

---

## Hallazgos abiertos

- **F-003 (MEDIUM)** — residual: sin aserción de contrato ni test de regresión.
- **F-007 (MEDIUM)** — `C-C3-007` admite PASS vacuo por columna renombrada o CSV ausente.
  `load_open_reviews()` devuelve `[]` si el archivo no existe (`:108-109`) y el check emite
  *"3/3 intactas"* sin haber leído nada.
- **F-008 (MEDIUM)** — crecimiento del RAW sin política de retención. Un CUIT ≈ 17 MB por
  corrida; extrapolado a `FINANCIERO`/`TODO` es lineal y sin techo.
- **F-005 (LOW)** — el stage report sigue sin embeber el manifest; los 75 `sha256`/`raw_path`
  sólo existen en `fetch_raw.cnv_download_log`@5433.
- **F-010 (LOW)** — `created_at` del checkpoint congelado en 04:29:01 mientras `run_id`
  apunta a una corrida de las ~13:52.

## Condición para CERTIFIED

C3 puede considerarse **CHECKPOINTED con reservas**. Para **CERTIFIED** hacen falta F-007
(aserción de contrato + test de regresión de `C-C3-007`) y una decisión registrada sobre
F-008 antes de escalar a `FINANCIERO`/`TODO`, donde el crecimiento se multiplica por el
universo de empresas.

## Evidencia consultada

- `scripts/engine/c3_cnv_fetch.py:107-110, 505-568` · `engine/cnv/rawstore.py:59-79`
- `outputs/docs/fase_cnv/C3_CNV_STAGE_REPORT_run6_rerun_PASS_fixed.json`
- `catalaxia`@5433 · `fetch_raw.cnv_download_log`, `engine.checkpoints`
- `data/raw/engine/cnv/**` (377 archivos, 75 pares comparados)
- `tests/test_engine_cnv.py` (corrida propia)
