# IDENTITY V1 — REPORTE DE TESTS

**Fecha:** 2026-08-25
**Comando:** `python -m pytest tests/ -q`
**Resultado:** `38 passed in 7.24s` — 12 nuevos (Identity v1) + 26 preexistentes, sin regresiones.
**Base:** `catalaxia@127.0.0.1:5433/catalaxia`, schema `identity_v1`

---

## 1. Aislamiento

Cada test corre dentro de una transacción que hace `TRUNCATE` de `identity_v1`
al entrar y `ROLLBACK` al salir. En Postgres el `TRUNCATE` es transaccional, así
que los tests ven un schema limpio **y el piloto de 4 emisores queda intacto**:

```
antes:  4 entidades, 16 assertions, 5 reviews abiertas
pytest: 38 passed
después: 4 entidades, 16 assertions, 5 reviews abiertas
```

Esto no salió gratis. La primera versión del fixture no truncaba, y al correr la
suite completa **los 12 tests fallaron** porque los identificadores reales del
piloto (CIK, CUIT y LEI de YPF, CEPU, GGAL, TGSU2) colisionaban con los que los
tests insertan. La colisión era el comportamiento **correcto** del sistema — un
CUIT autoritativo no puede designar dos entidades — pero no lo que cada test
quería medir.

---

## 2. Los 12 tests exigidos

| # | Test | Verifica | Estado |
|---|---|---|---|
| 1 | `test_01_ypf_resuelve_correctamente` | YPF con CIK+CUIT+LEI correctos resuelve; toda assertion tiene cita, registro y autor | PASS |
| 2 | `test_02_ypf_con_cuit_de_cepu_es_rechazado` | **El error histórico.** `REJECTED` + conflict OPEN; el CUIT sigue en CEPU; YPF queda sin CUIT | PASS |
| 3 | `test_03_ggal_con_cuit_de_tercero_es_rechazado` | CUIT de TGSU2 atribuido a GGAL → `REJECTED`. Además, CUIT con checksum roto → `REJECTED` | PASS |
| 4 | `test_04_cuit_faltante_queda_en_review` | GGAL (`RA999999`, `registeredAs=null`) → `REVIEW_REQUIRED` con motivo, **no un CUIT inventado** | PASS |
| 5 | `test_05_cik_contradictorio_queda_en_review` | Legacy contradictorio → `CANDIDATE` (no disputa). Fuente autoritativa contradictoria → `REVIEW_REQUIRED`; el vigente no se pisa | PASS |
| 6 | `test_06_gleif_lei_a_cuit_valido` | TGSU2: `RA000010` + `registeredAs='30-65786206-8'` → CUIT `30657862068` `VERIFIED` | PASS |
| 7 | `test_07_sin_puente_cik_lei_no_hay_verificacion_automatica` | **G5.** Entidad anclada en CIK: el CUIT vía LEI queda `REVIEW_REQUIRED`. Con el puente humano registrado, la misma llamada consolida | PASS |
| 8 | `test_08_ticker_no_crea_entidad` | `link_symbol` sobre instrumento inexistente → `UnknownEntity`, 0 entidades y 0 instrumentos creados. Un TICKER afirmado nunca es autoritativo | PASS |
| 9 | `test_09_namespaces_de_ticker_no_se_mezclan` | `TICKER/US:YPF` y `TICKER/BYMA:YPF` apuntan a entidades distintas y conviven; dentro de un namespace el símbolo vigente es único | PASS |
| 10 | `test_10_resolucion_humana_deja_provenance` | Review cerrada con reviewer/decision/reason/resolved_at + assertion `HUMAN_DECISION` con autor y motivo. No se cierra dos veces ni sin revisor | PASS |
| 11 | `test_11_assertion_historica_es_inmutable_y_auditable` | Supersede cierra y encadena; la cita sobrevive; `UPDATE` de evidencia y de status → rechazados; `DELETE` de assertion vigente → rechazado | PASS |
| 12 | `test_12_identificador_autoritativo_duplicado_lo_rechaza_la_base` | Sin pasar por la capa de dominio: `ux_identifier_autoritativo_unico`, trigger de `VERIFIED` y `ck_ticker_no_autoritativo` | PASS |

### Nota sobre el test 12

Es el único que escribe SQL directo, a propósito: verifica que la garantía viva
en el **schema** y no en la capa de dominio. Si alguien mañana escribe en
`identity_v1` desde otro proceso, un script o psql, las tres barreras siguen ahí.

---

## 3. Prueba de mutación

Los 12 tests pasaron en la primera corrida. Eso amerita desconfianza, así que se
verificó que sean portantes desactivando la detección de conflictos:

```python
# engine/identity_v1.py
-    if autoritativo:
+    if False:
         dueno = entity_of(...)
```

```
3 failed, 9 passed
  FAILED test_02_ypf_con_cuit_de_cepu_es_rechazado
  FAILED test_03_ggal_con_cuit_de_tercero_es_rechazado
  FAILED test_05_cik_contradictorio_queda_en_review
```

Traceback del test 2 bajo mutación:

```
sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation)
duplicate key value violates unique constraint "ux_entity_un_autoritativo_por_tipo"
```

Dos conclusiones:

1. Los tests detectan la pérdida de la garantía (no pasan por vacuidad).
2. **Con la capa de dominio desactivada, la base sigue rechazando la escritura.**
   El código restaurado vuelve a 12/12.

---

## 4. Banco adversario sobre datos reales

`python scripts/engine/identity_v1_adversario.py` — **13 ataques, 13 rechazados
como corresponde, 0 fallas**, en transacción revertida sobre el piloto sembrado.

```
A) CUIT de CEPU -> YPF                      REJECTED         conflict #1
B) CIK de TGSU2 (ya asignado) -> YPF        REJECTED         conflict #2
   CIK libre pero contradictorio -> YPF     REVIEW_REQUIRED  vigente=0000904851 propuesto=0000320193
C) legacy completa el CUIT de GGAL          CANDIDATE        el CUIT autoritativo sigue vacío
D) CUIT con checksum roto                   REJECTED         módulo 11
E) ticker homónimo no crea identidad        CANDIDATE        is_authoritative=False
   símbolo YAHOO 'TGS' en dos instrumentos  rechazado        ux_symbol_vigente
   mismo texto en namespace distinto        aceptado         US/TGS ≠ YAHOO/TGS
F) borrar assertion vigente                 rechazado        tg_no_borrar_vigente
   editar assertion histórica               rechazado        tg_assertion_inmutable
G) VERIFIED sin cita                        rechazado        ck_verified_exige_evidencia
   regla derivada como AUTHORITATIVE        rechazado        ck_authoritative_metodo
```

### El banco encontró un bug en el piloto

La primera corrida dio **2 fallas**. Ninguna era del schema:

- **Falla 1 — expectativa mía equivocada.** Ataqué con el CIK de TGSU2, que ya
  era autoritativo de TGSU2. Esperaba `REVIEW_REQUIRED` y obtuve `REJECTED`, que
  es el resultado más fuerte y correcto. Se corrigió la expectativa y se agregó
  B2 para cubrir la rama que creía estar probando.

- **Falla 2 — bug real, en mi código.** El ataque "insertar `US/TGS` duplicado"
  fue *aceptado*, porque el piloto nunca había escrito `US/TGS`: había escrito
  `US/TGSU2` para el instrumento de NYSE. Al mirar por qué, apareció el problema
  de fondo: `market_instruments.ticker_canonico` repite el ticker **local** en la
  fila del ADR. El piloto estaba escribiendo símbolos falsos:

  ```
  MKT:84  ADR  NYSE  US/YPFD     ← FALSO: YPFD es el ticker de BYMA, no de NYSE
  MKT:66  ADR  NYSE  US/TGSU2    ← FALSO: el ticker de NYSE es TGS
  ```

  Corregido: para instrumentos no-BUE el piloto ya no deriva símbolo de
  `ticker_canonico`; escribe solo el símbolo `YAHOO` (que Market sí publica) y
  abre una review declarando la carencia. Registrado como **F-014**.

Esta es la razón por la que el banco adversario existe. El bug no lo habría
encontrado ningún test unitario: solo aparece al confrontar el modelo con los
datos reales de Market.

---

## 5. Cobertura de las garantías

12 de las 14 garantías del schema tienen test explícito. Las dos sin cobertura
propia:

| # | Garantía | Por qué no |
|---|---|---|
| 8 | `ck_ratio_obligatorio` (ADR/CEDEAR exige ratio) | Se ejerce indirectamente en el piloto (los 4 ADR traen `ratio_adr`), pero no hay test negativo |
| 11 | `ck_conflict_resolucion` | No se probó la transición de conflicto a resuelto; no hay todavía flujo de cierre de conflictos |

Ambas quedan como deuda declarada, no como cobertura implícita.

---

## 6. Reproducción

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia \
    -v ON_ERROR_STOP=1 -f /tmp/008_identity_v1.sql   # o engine.db.apply_migrations
python scripts/engine/identity_v1_pilot.py --reset   # siembra 4 emisores (GLEIF en vivo)
python scripts/engine/identity_v1_adversario.py      # 13 ataques, revierte
python -m pytest tests/test_identity_v1.py -q        # 12 tests
```

`--offline` en el piloto usa el snapshot GLEIF verificado del ciclo G4
(`scratchpad/g4_resumen.json`) y lo declara como tal en la cita.
