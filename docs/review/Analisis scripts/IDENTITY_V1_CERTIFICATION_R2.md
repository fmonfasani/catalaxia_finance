# IDENTITY V1 — RE-CERTIFICACIÓN POST-HARDENING (CICLO 6)

**Fecha:** 2026-08-26
**Objeto:** `identity_v1` @ `catalaxia-engine-dev` (5433), migraciones 008 + **009** + **010**
**Método:** ataque directo a PostgreSQL, arnés nuevo con exigencia de blanco real.

# VEREDICTO: `IDENTITY_V1_CERTIFIED` — con 1 residual declarado

---

## 1. Los cuatro blockers

| Finding | Estado | Prueba independiente contra PostgreSQL |
|---|---|---|
| **F-015** assertion vigente reescribible | **CERRADO** | D1–D4: reescribir `evidence`, reapuntar `entity_key`, promover `REVIEW_REQUIRED→VERIFIED`, cambiar `source_id` → los 4 rechazados por `tg_assertion_inmutable` |
| **F-016** firma humana falsa | **CERRADO** | C1: `proc:` firmando `HUMAN_DECISION` → rechazado por `ck_humano_no_es_proceso`. Y `SELECT count(*) … method='HUMAN_DECISION'` = **0**: los 4 bridges fabricados ya no existen |
| **F-017** procedencia borrable | **CERRADO** | E1–E7: borrar assertion vigente / histórica / `REVIEW_REQUIRED`, review abierta, identifier vigente, conflict abierto, y `TRUNCATE` → los 7 rechazados |
| **F-018** sin validación en la base | **CERRADO** | B1–B5: CUIT con checksum roto, CUIT con guiones, `CIK='YPF'`, `CIK='42'`, `LEI='no-es-un-lei'` → los 5 rechazados por `ck_formato_identificador` |

**Y el criterio central de la consigna del ciclo 5, que antes no se cumplía:**

```
A1  YPF + CUIT de CEPU (33650305499)  -> RECHAZADO  ux_identifier_autoritativo_unico
A2  CEPU + CUIT de YPF (30546689979)  -> RECHAZADO  ux_identifier_autoritativo_unico
A3  segundo CUIT para la misma entidad-> RECHAZADO  ux_entity_un_autoritativo_por_tipo
A4  reapuntar un identifier vigente   -> RECHAZADO  ux_entity_un_autoritativo_por_tipo
```

**32 ataques, 32 rechazados. Ningún `VERIFIED` silencioso.**
Suite: `38 passed`. Guardas desplegadas: **13 CHECK `ck_*` + 11 triggers** (antes 9 + 3).

---

## 2. Un defecto en mi propio arnés de auditoría, y un hallazgo falso del ciclo 5

Al re-correr la pasada 1 sobre el estado corregido, los ataques A1–A3 dieron `[HUECO]`.
No era una regresión: la migración 009 **retiró los CUIT** del piloto (`valid_to` poblado),
y los índices únicos son parciales sobre `valid_to IS NULL`. Sin blanco vigente, el INSERT
entra legítimamente.

Eso expuso un defecto estructural del arnés de los ciclos 5:

> Un `UPDATE`/`DELETE` que **no matchea ninguna fila** tampoco lanza excepción, y el arnés
> lo contaba como `[HUECO]`.

**Consecuencia concreta: el ataque 12e del ciclo 5 ("borrar un conflict abierto") corrió
contra una tabla `conflict` vacía.** Nunca demostró nada. La parte de **F-017 referida a
`conflict` era un hallazgo falso** y queda rectificada aquí — verificado ahora con blanco
real (E6: se siembra un conflicto y se intenta borrarlo → rechazado).

El arnés de la pasada 3 exige blanco real: si un ataque toca cero filas se reporta `[NULO]`,
no `[OK]` ni `[HUECO]`. Y monta sus propios objetivos en vez de depender del estado del
piloto. `docs/review/identity_v1_audit_pass3.sql`.

---

## 3. Lo que la corrección le costó al golden case

Esto es una **regresión visible y deliberada**:

```
                                     CIK          CUIT       LEI                   reviews
CENTRAL PUERTO S.A.                  0001717161   (vacío)    2549005JLIWQ6B7VNR38    3
GRUPO FINANCIERO GALICIA S.A.        0001114700   (vacío)    5299008H3AXIXV5G3C23    4
TRANSPORTADORA DE GAS DEL SUR S.A.   0000931427   (vacío)    5299002TRC7IFQYSW596    3
YPF SOCIEDAD ANONIMA                 0000904851   (vacío)    5493003N7447U18U5U53    3
```

**Los cuatro emisores perdieron el CUIT.** Antes tres lo tenían `VERIFIED`. Ese `VERIFIED`
descansaba en un puente CIK↔LEI que decía *"lo ratificó fmonfasani"* y lo había escrito un
script en bucle. Retirado el puente, la cadena `CIK → LEI → CUIT` vuelve a tener un eslabón
no demostrado, y el estado honesto es `REVIEW_REQUIRED`.

**No es una pérdida de información: es la información que siempre hubo, ahora declarada.**
El dato del CUIT sigue en GLEIF y el sistema lo dice en cada review; lo que no hay —y nunca
hubo— es la demostración de que ese LEI corresponde a ese CIK (G5).

**Para recuperarlo hace falta que una persona ratifique.** Es el único camino:

```bash
python scripts/engine/identity_v1_ratificar.py --listar
python scripts/engine/identity_v1_ratificar.py \
    --cik 0000904851 --lei 5493003N7447U18U5U53 --reviewer "tu.usuario" \
    --evidencia-cik "20-F FY20XX accession NNNN: denominación y domicilio legal ..." \
    --evidencia-lei "GLEIF lei-records/5493...: legalName, legalAddress, registeredAt ..." \
    --motivo "ambos registros declaran la misma razón social y domicilio"
python scripts/engine/identity_v1_pilot.py     # el CUIT se consolida por esa vía
```

El script exige evidencia de **los dos extremos** (≥30 caracteres cada una) y rechaza
cualquier `--reviewer` que empiece con `proc:`.

---

## 4. Qué cambió, exactamente

**`009_identity_v1_hardening.sql`** — primero corrige datos, después instala guardas; el
orden importa, porque una vez puestas la corrección ya no es posible.

| Paso | Qué hace |
|---|---|
| A.1 | Retira (no borra) los 3 CUIT que colgaban del puente fabricado → `valid_to`, `status='DISPUTED'` |
| A.2 | **Elimina** los 4 bridges fabricados. Se eliminan y no se supersedan: una assertion superseded seguiría diciendo *"fmonfasani lo verificó"*, y eso nunca pasó. Conservar una firma falsa en nombre de la trazabilidad sería peor que borrarla. Queda constancia del acto en la migración |
| A.3 | Abre 4 reviews: el puente necesita una persona |
| A.4 | Da procedencia a los 8 instrumentos (nueva fuente `MARKET_CATALOG`, `CORROBORATING`) |
| B.1 | `ck_formato_identificador` + `identity_v1.cuit_valido()` (módulo 11, `IMMUTABLE`) |
| B.2 | `ck_humano_no_es_proceso` |
| B.3 | `ck_supersede_no_circular`, `ck_vigencia_coherente` |
| B.4 | `fn_assertion_inmutable` reescrita: inmutabilidad **total**; sólo `valid_to` y `superseded_by`, y una sola vez cada uno |
| B.5 | `fn_prohibir_delete` en `assertion`, `review`, `conflict`, `identifier` |
| B.6 | Mismo bloqueo para `TRUNCATE` (statement trigger) |

**`010_…_instrument_provenance.sql`** — `instrument.assertion_id NOT NULL`.

**Código:** `resolve_or_create_entity()` (resuelve por identificador antes de crear),
`ratificar_bridge()`, `_exigir_persona()`, dedupe en `open_review` / `assert_bridge` /
`link_cuit_desde_gleif`, y `register_instrument(assertion_id=…)` ahora obligatorio.

**Idempotencia (F-023) verificada:** tres corridas seguidas del piloto →
`ent=4 assert=33 ident=12 rev=13 sym=12` idéntico las tres veces, mismos `entity_key`.
Ya no existe `--reset`: el `TRUNCATE` está prohibido.

---

## 5. Residual declarado — F-025

```sql
BEGIN; SET LOCAL session_replication_role = replica;
DELETE FROM identity_v1.assertion WHERE assertion_id = (SELECT min(assertion_id) …);
--> DELETE 1     (aceptado)
```

**`catalaxia` es superusuario** (`pg_roles.rolsuper = t`), y un superusuario desactiva todos
los triggers con `session_replication_role = replica`. Las guardas de F-015 y F-017 son
triggers. **Un superusuario puede saltearlas.**

Esto no se arregla con más constraints: es un problema de privilegios. El engine no debería
conectarse como superusuario. Se emite como **F-025 (MEDIUM)** y se toma en cuenta en el
orden de reactivación. No invalida la certificación —el modelo de amenaza de F-015/F-017 es
la escritura accidental o de un proceso mal escrito, no un superusuario deliberado— pero
**tiene que estar dicho.**

Los tests usan esta misma válvula para limpiar el schema, y la desactivan **antes** del
cuerpo de cada test (con `assert current_setting(...) = 'origin'`): la limpieza usa el
escape, la prueba corre con todas las guardas.

---

## 6. Findings — estado

| ID | Sev | Estado |
|---|---|---|
| F-015, F-016, F-017, F-018 | HIGH/HIGH/HIGH/MED | **CERRADOS** contra su `acceptance_test` |
| F-021 `instrument.assertion_id` | MEDIUM | **CERRADO** (010; F1 rechazado) |
| F-022 `superseded_by` / `valid_to` | LOW | **CERRADO** (D7, D8 rechazados) |
| F-023 idempotencia | MEDIUM | **CERRADO** (3 corridas idénticas) |
| F-019 review no bloquea el identificador | MEDIUM | **OPEN** — no era blocker; requiere vincular `review` con el identificador en disputa |
| F-020 D-I-04 mal contada | MEDIUM | **OPEN** — pendiente re-presentar sobre 13 puentes / 510 solapamientos |
| F-024 CIK en la columna `cuit` (BMA) | HIGH | **OPEN** — dato de origen; bloquea el backfill, no a Identity v1 |
| F-025 engine conecta como superusuario | MEDIUM | **NUEVO** |
| F-017 (parte `conflict`) | — | **RECTIFICADO**: el ataque del ciclo 5 corrió contra tabla vacía |

---

## 7. Orden para reactivar los tres workstreams

Con `IDENTITY_V1_CERTIFIED`, este es el orden y el porqué. **No es alfabético ni por
comodidad: sigue las dependencias de datos y el riesgo.**

### Antes de tocar cualquier workstream — 2 precondiciones

1. **F-025**: crear un rol `catalaxia_engine` NO superusuario con `INSERT/UPDATE/SELECT`
   sobre `identity_v1` y sin `TRUNCATE`, y apuntar el engine ahí. Mientras el engine sea
   superusuario, las garantías que acabo de certificar son revocables por accidente.
2. **F-001**: Market escribe a 5432 sin guarda anti-prod, y `m6_scale.py` existe. Sigue
   siendo el HIGH más antiguo abierto y toca el workstream que más filas mueve.

### 1º — **CNV** (riesgo bajo, desbloquea el resto)

Por qué primero: es el único con datos ya materializados que Identity v1 puede consumir
(9.305 presentaciones de Central Puerto), su fetcher no escribe en 5432, y **`fetch_raw.cnv_presentation.entity_key` guarda `'CIK:0001717161'`** — la clave derivada del CIK que Identity v1 existe para reemplazar. Migrar esa columna a `entity_key` opaco es el
primer test real de integración y no arriesga nada.
*Pendiente propio:* F-007 (`C-C3-007` con PASS vacuo) y F-008 (retención de RAW) antes de
`FINANCIERO`/`TODO`.

### 2º — **SEC** (alimenta la identidad, no depende de ella)

Por qué segundo: el CIK es el identificador autoritativo del 87 % del catálogo y ya está
resuelto. SEC sólo necesita **emitir** identidad, no consumirla, así que puede avanzar en
paralelo a la ratificación de puentes. Pendiente propio: F-009 (5 de 8 corridas sin estado
terminal) antes de S04.

### 3º — **MARKET** (el que más depende de decisiones abiertas)

Por qué último, y no por ser el menos importante:
- **F-001** debe estar cerrado antes de escalar a 584 instrumentos;
- **F-014** sigue OPEN en el origen: `ticker_canonico` repite el ticker local en la fila del
  ADR. Identity v1 lo mitiga rechazando el símbolo, pero cualquier consumidor que lea
  `market_instruments` directo publica un símbolo falso;
- **F-013**: la semántica de checkpoint de Market difiere de las otras dos.

### En paralelo, sin bloquear a nadie

- **Ratificar los puentes CIK↔LEI** de los 4 emisores (recupera el CUIT del golden case).
- **F-024**: corregir Banco Macro en `dim_entity` — el CIK está en la columna `cuit`.
- **F-020**: re-presentar D-I-04 sobre la población real, con la regla de fusión para los
  510 CIK solapados.

**La Fase 2 del backfill no arranca hasta que F-020 y F-024 estén cerrados.** Importar hoy
las 573 + 7.998 entidades produciría 510 conflictos de CIK duplicado sin regla de fusión, y
metería el CIK de BMA como si fuera su CUIT.

---

## 8. Alcance

- Escrituras del ciclo: `migrations/engine/009`, `010`, `engine/identity_v1.py`,
  `scripts/engine/identity_v1_pilot.py`, `identity_v1_ratificar.py` (nuevo),
  `tests/test_identity_v1.py`, `docs/review/`.
- **No se tocó** SEC, CNV ni Market. Market (5432) sólo se leyó, con `SET TRANSACTION READ ONLY`.
- Los 32 ataques corrieron en transacciones revertidas; estado verificado idéntico antes y
  después: **4 entidades / 33 assertions / 12 identifiers / 13 reviews / 0 conflicts**.
- **Conflicto de interés vigente:** el implementador y el auditor son el mismo agente. La
  mitigación fue no usar el código propio como fuente de verdad (todo el ataque es SQL crudo
  contra el catálogo desplegado) y publicar los errores propios — incluido el hallazgo falso
  del ciclo 5 y el defecto del arnés. **Sigue haciendo falta una revisión externa.**
