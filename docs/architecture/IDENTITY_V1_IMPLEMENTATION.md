# IDENTITY V1 — IMPLEMENTACIÓN

**Ciclo 4.** Estado: implementado, probado y sembrado con 4 emisores reales.
**Fecha:** 2026-08-25

---

## 1. La pregunta y la respuesta

> ¿Cómo sabe Catalaxia que el CIK X, el CUIT Y y el instrumento Z representan la
> misma entidad económica?

Respuesta de Identity v1 para YPF, leída del sistema y no de esta prosa:

```
entity_key = E01M0X99…            (opaco, no derivado de ningún identificador)

CIK  0000904851  ← SEC_20F, accession 0001193125-17-115552          VERIFIED
LEI  5493003N7447U18U5U53 ← GLEIF lei-records/…                     VERIFIED
     puente CIK↔LEI ← HUMAN_DECISION, fmonfasani, motivo registrado VERIFIED (STRONG)
CUIT 30546689979 ← GLEIF registeredAt=RA000009 (AFIP)
                          registeredAs='30-54668997-9'              VERIFIED
MKT:83 EQUITY BUE ARS  → BYMA/YPFD, YAHOO/YPFD.BA
MKT:84 ADR    NYSE USD → YAHOO/YPF        (símbolo NYSE: review #1)
CNV: sin fetch para este CUIT
```

Ningún eslabón depende de coincidencia de nombre, de ticker, de SQLite legacy ni
de conocimiento humano no registrado. El único eslabón humano — el puente
CIK↔LEI — **está declarado como humano**, con autor y motivo, porque el ciclo G5
demostró que no existe fuente primaria que lo publique.

---

## 2. Qué se construyó

| Artefacto | Qué hace |
|---|---|
| `migrations/engine/008_identity_v1.sql` | Schema `identity_v1`: 8 tablas, 21 CHECK, 3 índices únicos parciales, 3 triggers, 1 vista, catálogo de fuentes |
| `engine/identity_v1.py` | Capa de dominio: estados, normalización, detección de conflictos, resolución humana |
| `tests/test_identity_v1.py` | Los 12 tests exigidos |
| `scripts/engine/identity_v1_pilot.py` | Siembra los 4 emisores con evidencia real de las 4 fuentes |
| `scripts/engine/identity_v1_adversario.py` | 13 ataques contra el piloto, en transacción revertida |

**No se modificó** el parser SEC, el fetcher de Market ni el de CNV. Market
(5432) se leyó con `SET TRANSACTION READ ONLY` explícito.

---

## 3. Los cinco estados

| Estado | Cuándo | Qué se puede hacer con el dato |
|---|---|---|
| `UNRESOLVED` | La entidad no tiene identificador autoritativo del tipo requerido | Nada que dependa de ese identificador |
| `CANDIDATE` | Una fuente `CORROBORATING`/`DISCOVERY_ONLY` lo propone | Corroborar; **nunca** establecer identidad |
| `REVIEW_REQUIRED` | Hay ambigüedad, contradicción o falta un eslabón demostrado | Nada, hasta que un humano decida |
| `VERIFIED` | Fuente autoritativa para ese tipo + cita + autor | Usarlo |
| `REJECTED` | El identificador ya pertenece autoritativamente a otra entidad | Nada; queda el conflicto abierto |

La regla operativa que se sigue de esto: **la ausencia de dato produce un
`REVIEW_REQUIRED` con motivo escrito, jamás un valor plausible.** GGAL termina el
piloto sin CUIT y con la review #3 abierta que dice `registrationAuthority
'RA999999' no asigna CUIT`. Eso es el resultado correcto, no una falla.

---

## 4. Cómo se decide el estado (`assert_identifier`)

```
1. ¿La entidad existe?            no → UnknownEntity (no se crea al vuelo)
2. Normalizar (CIK 10 dígitos, CUIT 11, LEI ISO 17442)
3. ¿CUIT pasa el módulo 11?       no → REJECTED
4. ¿La fuente es AUTHORITATIVE PARA ESTE id_type?
      sí + método REGISTRY/REGULATORY_DOCUMENT → AUTHORITATIVE / VERIFIED
      método HUMAN_DECISION (exige motivo)     → STRONG / VERIFIED
      resto                                    → WEAK / CANDIDATE
5. ¿id_type ∈ {TICKER, YF_SYMBOL, LEGACY_ENTITY_ID}? → forzar CANDIDATE, no autoritativo
6. Si va a ser autoritativo:
      a. ¿el identificador ya es autoritativo de OTRA entidad?
             → conflict + assertion DISPUTED/REJECTED  → REJECTED
      b. ¿la entidad ya tiene otro valor de este tipo?
             → conflict + review + assertion REVIEW_REQUIRED
      c. ¿mismo valor, misma entidad? → idempotente
7. Escribir assertion, después identifier (FK NOT NULL)
```

El paso 4 es donde vive la lección del ciclo G4: **una fuente puede ser
autoritativa para un tipo de identificador y no serlo para otro.** GLEIF
establece LEI y CUIT; no dice nada sobre el CIK. `source_authority()` consulta
`authoritative_for` y devuelve `CANDIDATE` cuando la fuente es seria pero no
competente para ese campo.

---

## 5. La resolución humana es permanente, no transitoria

El ciclo G5 cerró con `CIK_LEI_PRIMARY_BRIDGE = NOT_AVAILABLE`: ni SEC publica el
LEI del registrante (0/6 en el control sobre XBRL/DEI, 20-F y 13D/13G), ni GLEIF
publica el CIK. La consecuencia de diseño es que `identity_v1.review` **no es un
mecanismo de arranque que se apaga cuando el pipeline madura**: es un componente
permanente del sistema.

`resolve_review()` deja, en una sola operación:

- la review con `reviewer`, `decision`, `decision_reason`, `resolved_at` y
  `resolution_assertion_id` (`ck_cierre_exige_reviewer` lo hace obligatorio);
- una assertion con `method = HUMAN_DECISION`, `confidence = STRONG`,
  `resolved_by` y `resolution_reason` (`ck_humano_exige_autor` lo hace obligatorio);
- el identificador materializado, si el revisor decidió aplicarlo.

`confidence = STRONG` y no `AUTHORITATIVE` es deliberado: mantiene visible la
diferencia entre *"un registro lo declaró"* y *"una persona lo estableció con
evidencia"*. `ck_authoritative_metodo` impide que un humano se auto-promueva a
registro.

---

## 6. El piloto: 4 emisores, evidencia real

`python scripts/engine/identity_v1_pilot.py --reset`

| | CIK | LEI | CUIT | CNV | Market |
|---|---|---|---|---|---|
| **YPF** | ✔ 20-F `0001193125-17-115552` | ✔ | ✔ GLEIF RA000009 | sin fetch | 2 instrumentos |
| **CEPU** | ✔ submissions | ✔ | ✔ GLEIF RA000009 | ✔ **9.305 presentaciones** | 2 instrumentos |
| **GGAL** | ✔ submissions | ✔ | ✖ **REVIEW #3** | bloqueado (sin CUIT) | 2 instrumentos |
| **TGSU2** | ✔ submissions | ✔ | ✔ GLEIF RA000010 | sin fetch | 2 instrumentos |

Resultado: **0 conflictos abiertos, 5 reviews abiertas, 0 identificadores inventados.**

El golden case end-to-end completo con las **cuatro** fuentes lo cumple **CEPU**,
no YPF: es el único de los cuatro con datos CNV materializados
(`fetch_raw.cnv_presentation` tiene 9.305 filas y un solo CUIT). YPF recorre
SEC + GLEIF + Market pero no CNV, porque **el fetch CNV de YPF todavía no se
ejecutó**. Se deja consignado en vez de presentarlo como logrado.

---

## 7. El banco adversario

`python scripts/engine/identity_v1_adversario.py` — 13 ataques, **13 rechazados
correctamente**, todo dentro de una transacción revertida.

| Ataque | Resultado |
|---|---|
| A — El CUIT de Central Puerto atribuido a YPF (**el error histórico**) | `REJECTED` + conflict; el CUIT sigue en CEPU |
| B1 — Un CIK ya asignado a otra entidad | `REJECTED` + conflict |
| B2 — Un CIK libre pero contradictorio | `REVIEW_REQUIRED` (vigente 0000904851, propuesto 0000320193) |
| C — El legacy `dim_entity` completando el CUIT de GGAL | `CANDIDATE`; el CUIT autoritativo sigue vacío |
| D — CUIT con dígito verificador roto | `REJECTED` (módulo 11) |
| E — Ticker homónimo / símbolo duplicado / mismo texto en otro namespace | `CANDIDATE` / rechazado / aceptado |
| F — Borrar assertion vigente, editar assertion histórica | rechazado por trigger |
| G — `VERIFIED` sin cita, regla derivada declarada `AUTHORITATIVE` | rechazado por CHECK |

### Dos hallazgos que salieron del banco adversario

**El banco encontró un bug real en mi propio piloto.** La primera versión escribía
`instrument_symbol(US, ticker_canonico)` para los instrumentos de NYSE. Pero
`market_instruments.ticker_canonico` repite el ticker **local** en la fila del
ADR: para `MKT:84` (YPF en NYSE) dice `YPFD`, que es el símbolo de BYMA. El
piloto estaba escribiendo un símbolo falso. Corregido: para instrumentos
no-BUE solo se escribe el símbolo `YAHOO` (que Market sí publica) y se abre una
review declarando que Market no expone el ticker de NYSE como campo. Ver
**F-014**.

**Dos "fallas" del banco eran expectativas mías equivocadas, no fallas del
sistema.** Esperaba `REVIEW_REQUIRED` al atribuir a YPF un CIK que ya pertenecía
a TGSU2; el sistema devolvió `REJECTED`, que es el resultado **más fuerte y
correcto**. Se corrigió la expectativa y se agregó el caso B2 para cubrir la
rama que yo creía estar probando.

---

## 8. Verificación de que los tests no pasan por casualidad

Con 12/12 en verde en la primera corrida, se corrió una **prueba de mutación**:
desactivar la detección de conflictos de la capa de dominio y volver a correr.

```
mutación: `if autoritativo:` → `if False:`
resultado: 3 failed, 9 passed
   test_02_ypf_con_cuit_de_cepu_es_rechazado
   test_03_ggal_con_cuit_de_tercero_es_rechazado
   test_05_cik_contradictorio_queda_en_review
```

Los tests son portantes. Y el error que se ve en el traceback de la mutación es
`UniqueViolation: ux_entity_un_autoritativo_por_tipo` — es decir, **con la capa
de dominio desactivada la base sigue rechazando la escritura.** La garantía no
depende del código de aplicación.

---

## 9. Limitaciones conocidas

1. **CNV solo tiene un CUIT materializado** (Central Puerto). El golden case de
   4 fuentes se demuestra sobre CEPU, no sobre YPF.
2. **El CUIT de GGAL no está resuelto.** GLEIF no lo publica y AFIP no es
   automatizable. Requiere resolución humana; la review está abierta.
3. **El puente CIK↔LEI de los 4 emisores está registrado como `HUMAN_DECISION`
   con la misma cita genérica.** Para los 584 instrumentos esto no escala como
   está: hace falta o bien un procedimiento de verificación documento por
   documento, o bien aceptar `REVIEW_REQUIRED` masivo. Es una decisión de
   producto, no técnica, y está abierta.
4. **`ck_ratio_obligatorio` no tiene test propio** (garantía 8).
5. **El backfill de las ~8.000 entidades no se ejecutó**, por diseño: el ciclo 4
   pedía probar 4 emisores primero.
