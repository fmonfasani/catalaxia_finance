# CROSS-WORKSTREAM — AUDIT REVIEW (Level 2)

Auditor: **CIAA** · Ciclo **AUDIT-02** · 2026-08-25 · Baseline `444ee1a`

## EJECUTADA — precondición cumplida por primera vez

| Workstream | Requerido | Real | Califica |
|---|---|---|---|
| SEC | CHECKPOINTED / CANDIDATE | S03 CHECKPOINTED, gate PASS 9/9, `READY_FOR_S04` | **Sí** |
| MARKET | GOLDEN / CANDIDATE | `MKT-GOLDEN-20260825-89c2f00f26c0` intacto | **Sí** |
| CNV | CHECKPOINTED / CANDIDATE | C3 checkpoint `8db8692e…`, run6 PASS 10/10 | **Sí** |

En AUDIT-01 SEC no calificaba y el Level 2 no se ejecutó. Ahora sí.

---

## 1 · IDENTITY — el hallazgo central del ciclo

Es el eje sobre el que se apoya cualquier capa canónica, y es donde el programa está
**más lejos** de estar listo. La conclusión no es que la identidad sea incorrecta: es que
**no es canónica**.

### Lo que hay, verificado

```
SEC     identity.entities @5433
        7998 entidades · TODAS con CIK · CUIT poblado en 0
        YPF -> entity_id='CIK:0000904851'  cuit=NULL

CNV     fetch_raw.cnv_download_log @5433
        entity_key='CIK:0001717161'  cuit='33650305499'   (CENTRAL PUERTO)
        -> resuelve CUIT a una identidad CIK: el puente EXISTE y es correcto

MARKET  market_instruments @5432
        instrument_id 83 (YPFD/BUE/ARS) y 84 (YPF/NYSE/USD)
        AMBOS -> entity_id = 72        (entero)

LEGACY  dim_entity @ SQLite screener.db
        entity_id=72  cuit=30546689979  cik=0000904851  ticker=YPFD
```

### Tres espacios de identidad, sin contrato entre ellos

| Sistema | Clave | Almacenamiento |
|---|---|---|
| SEC / CNV | `'CIK:0000904851'` (string) | PostgreSQL 5433, esquema `identity` |
| MARKET | `72` (entero) | PostgreSQL 5432, sin FK |
| Puente CUIT↔CIK | fila de `dim_entity` | **SQLite** `screener.db` |

**El join de tres puntas es reconstruible pero no está declarado en ninguna parte.**
`market_instruments.entity_id` **no tiene foreign key** (verificado: `pg_constraint` devuelve
0 filas) y apunta a una tabla que **no existe en PostgreSQL** — `dim_entity` vive únicamente
en el SQLite legacy, de donde `m1_symbol_mapping.py:64-67` la importó por `LEFT JOIN`.

### Lo que sí está bien

- **CNV puentea correctamente.** Resolver CUIT `33650305499` a `CIK:0001717161`
  (CENTRAL PUERTO S.A., presente en `identity.entities`) es exactamente lo que debe hacer,
  y lo hace sin inventar entidades (`0 entidades creadas por C3`, verificado).
- **`ticker ≠ identidad` se respeta en los tres.** Market separa instrumento de entidad:
  83 y 84 son **el mismo emisor** (72) en dos mercados y dos monedas, con `ratio_adr=1.0`.
  Eso es modelado correcto, no un atajo por ticker.
- **R-16 se atenúa para YPF.** El registro de riesgos advierte CIKs podridos en catálogos
  legacy nombrando a YPF. Verificado: el CIK legacy de la entidad 72 es `0000904851`, que
  **coincide** con el registro SEC (`YPF SOCIEDAD ANONIMA`). Para el golden case la identidad
  legacy es correcta. No se auditó GGAL/BMA/CRESY.

### Lo que falta para una capa canónica

`identity.identifiers` admite **tres** tipos: `CIK` (7998), `TICKER` (10414), `YF_SYMBOL`
(10414). **No existe el tipo `CUIT`.** El modelo de identidad no sabe que los CUIT existen;
la única asociación CUIT↔CIK vive dentro del log de descargas de un workstream y en un
SQLite fuera del engine. Ver **F-011**.

---

## 2 · DB ISOLATION

```
5433  catalaxia-engine-dev   engine · fetch_raw · identity · parsed     SEC + CNV
5432  catalaxia-db           public: market_* (10) + legacy (21)        MARKET
```

Sin contaminación materializada — confirmado en ambos ciclos. Pero el aislamiento
**sigue siendo circunstancial**: Market escribe por defecto en el puerto que
`engine/config.py:41` define como producción y no tiene guarda (**F-001**, agravado ahora
que `m6_scale.py` existe). El engine sí respeta 5433 por defecto.

Efecto colateral de la separación: **ningún join SQL puede cruzar Market con SEC/CNV.**
Están en servidores distintos. Cualquier capa canónica deberá resolver eso explícitamente.

---

## 3 · UNITS / CURRENCY — sin observaciones adversas

```
MARKET   instrument 83  currency=ARS  (BUE)      6634 ruedas, 100% ARS
         instrument 84  currency=USD  (NYSE)     8345 ruedas, 100% USD
         legacy entity 72: moneda_funcional=USD
SEC      parsed.units = 369 · parse_errors = 0
```

**Ninguna conversión silenciosa.** Market conserva la moneda por instrumento y no normaliza;
la moneda funcional de la entidad se mantiene separada de la moneda de cotización — que es
la distinción correcta. SEC preserva las unidades XBRL como dimensión propia.

---

## 4 · FISCAL PERIODS vs MARKET DATES — coherentes, sin cruzar todavía

```
SEC      27 filings · 9 PARSED_XBRL + 18 PRE_XBRL · 0 REJECTED
         23.478 contexts (instant/duration preservados)
MARKET   83: 2000-01-03 .. 2026-08-24 · tz America/Argentina/Buenos_Aires
         84: 1993-06-29 .. 2026-08-24 · tz America/New_York
         100% de las ruedas en estado FINALIZED
CNV      fecha_publicacion / fecha_cierre / periodicidad_norm en el inventario
```

Cada capa maneja su tiempo con la semántica correcta y sin off-by-one detectable. **Pero
todavía no se cruzan**: no existe un artefacto que empareje un período fiscal SEC con una
fecha de mercado ni con un cierre CNV. La coherencia *entre* capas no puede afirmarse
porque el cruce aún no se produjo — no es un defecto, es una etapa no alcanzada.

---

## 5 · PERIMETER — correcto donde es observable

```
CNV   78 relaciones declaradas: CONTROLADA=51 · VINCULADA=27
      relacion_origen=DECLARADA en el 100% · 0 relaciones asumidas
      scope: 1861/1861 filas y 150/150 artefactos de un solo CUIT
SEC   consolidado por filing; sin mezcla detectada
```

Sin mezcla de perímetros. Los 4 tests nuevos de `TestClassifyRelacion` cubren
CONTROLADA vs VINCULADA y los casos de no-reconocimiento.

---

## 6 · PROVENANCE

Cadena verificable en las tres capas, con calidad **desigual**:

| | Manifest en disco | Hashes por archivo | Auditable sin la DB |
|---|---|---|---|
| MARKET | `MANIFEST.json` + `provenance.csv` | 11 + 26 verificados | **Sí** |
| SEC | `S03_MANIFEST.json` + `S03_VALIDATION.json` | `source_file`/`source_hash` en relations | Parcial |
| CNV | — | sólo en `fetch_raw.cnv_download_log` | **No** (F-005) |

Market fija el estándar: su paquete permitió verificación íntegra sin tocar la base en
ambos ciclos. CNV depende de que 5433 sobreviva.

Los tres declaran `git_commit = 444ee1ad0e…` en sus reportes. **Pero HEAD sigue en
`444ee1a` y todo el trabajo posterior está sin commitear** — los reportes atribuyen su
código a un commit que ya no describe el árbol que los produjo. Ver **F-012**.

---

## 7 · REPRODUCIBILITY / IDEMPOTENCY

| | Evidencia | Veredicto |
|---|---|---|
| MARKET | 3 registros de cambio en ~10 corridas; único CHANGED = restatement real; `batch_hash` reproducido por el auditor | **Demostrada** |
| SEC | 3 corridas CHECKPOINTED con totales idénticos; `parsed.*` es replace-all | **Razonable**, con limitación declarada por el propio worker |
| CNV | 75/75 idénticos en sustancia por hash canónico | **Demostrada en sustancia**, no en bytes (F-008) |

SEC merece una precisión: el log documenta que la comparación de determinismo se hizo
**contra stdout de dos corridas**, no contra dos snapshots simultáneos, porque `parsed.*`
borra y reescribe. Que el worker declare esa limitación en vez de ocultarla es exactamente
la conducta que esta auditoría busca.

---

## 8 · RAW IMMUTABILITY — verificada en las tres

```
MARKET  26/26 archivos con sha256 y bytes coincidentes
CNV     0/75 archivos con 'CANON' escrito · 74/75 conservan el token real
        canonical_sha256 documentado como "NOT used for RAW storage/addressing"
SEC     source_file / source_hash poblados en link_relations
```

**El RAW no fue reescrito por la canonicalización.** Ése era el riesgo mayor del fix de CNV
y quedó descartado empíricamente.

---

## 9 · CHECKPOINT SEMANTICS — inconsistente entre workstreams

```
SEC   checkpoint_id = '971ce5d999a2499b-s03'   derivado del run ganador
      1 fila, ON CONFLICT sobre ux_checkpoints_reuse -> apunta al run más nuevo

CNV   checkpoint_id = '8db8692ebce9439c8be69cbaf5c82979'   ID original reusado
      run_id actualizado a run6, pero created_at congelado en 04:29:01  (F-010)

MARKET checkpoint_id = 'MKT-GOLDEN-20260825-89c2f00f26c0'  con state_digest propio
      fuera de engine.checkpoints (vive en su paquete golden)
```

Tres convenciones distintas para el mismo concepto. Ninguna es incorrecta en sí, pero
**no hay contrato común**: un consumidor de capa canónica no puede tratar "checkpoint"
como una noción uniforme. Ver **F-013**.

---

## 10 · FAILURE HANDLING — el punto más débil

```
S00_bootstrap   FAILED registrado 9 veces      la máquina de estados contempla el fallo
S01_identity    FAILED registrado 9 veces
C3_CNV_fetch    FAILED registrado 2 veces      + negativo de CUIT inexistente correcto
S03_parse       FAILED: 0 veces                5 corridas colgadas en RUNNING   (F-009)
```

CNV maneja bien el caso negativo (CUIT inexistente → BLOCK con error limpio, verificado en
AUDIT-01). SEC no marca sus abortos: cinco corridas quedaron sin estado terminal, lo que
hace que `stage_runs` no distinga *"corriendo"* de *"murió"*.

---

## VEREDICTO DE NIVEL 2

**NOT_READY para la Canonical Economic Layer.**

No es un juicio sobre la calidad del trabajo — las tres capas tienen evidencia real,
verificable y en buena parte reproducible. Es un juicio sobre **las precondiciones de
integración**, y hay tres que no se cumplen:

1. **No existe un contrato de identidad canónico.** El join CIK↔CUIT↔instrumento es
   reconstruible pero atraviesa tres sistemas de almacenamiento (PG 5433, PG 5432, SQLite),
   sin foreign key, sin tipo `CUIT` en el modelo, y apoyado en una tabla legacy que no
   existe en PostgreSQL. Una capa canónica **se construye exactamente sobre esa junta**.

2. **Market está físicamente separado y sin guarda.** No hay join posible con SEC/CNV
   (servidores distintos) y su destino de escritura por defecto es la base que el engine
   protege — con el script de escalamiento ya escrito (F-001).

3. **La semántica de checkpoint no es común.** Tres convenciones divergentes para el
   artefacto que la capa canónica debería consumir como unidad de confianza.

Ninguna de las tres es difícil de resolver; todas requieren una decisión explícita que hoy
no está tomada. **El dictamen se emite ahora —y no se difiere— porque las tres precondiciones
son verificables y las tres dieron negativo**, no por falta de evidencia.
