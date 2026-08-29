# BACKFILL PILOTO DE IDENTITY V1 — CONTRATO

**Fecha:** 2026-08-28 · **Alcance:** piloto de 12 emisores. **NO** las ~8.000 entidades.
**Escrito antes de implementar.** Estado del schema al momento: 13 CHECK `ck_*`, 11 triggers,
3 índices únicos parciales.

---

## 0. Qué mide este piloto

No es una carga: es una **medición**. La pregunta es cuánto del universo real puede Identity
v1 resolver con evidencia, y cuánto queda honestamente en manos de una persona.

---

## 1. Identificadores que se incorporan

| `id_type` | `id_namespace` | Puede ser autoritativo |
|---|---|---|
| `CIK` | `SEC` | sí |
| `CUIT` | `AFIP` | sí |
| `LEI` | `GLEIF` | sí |
| `TICKER` | `US`, `BYMA` | **nunca** (`ck_ticker_no_autoritativo`) |
| `YF_SYMBOL` | `YAHOO` | **nunca** |
| `CNV_ENTITY_ID` | `CNV` | no (`CNV_PORTAL` es `DISCOVERY_ONLY`) |
| `LEGACY_ENTITY_ID` | `LEGACY` | **nunca** |

---

## 2. Qué fuente puede producir qué

La autoridad es propiedad de la **fuente por tipo de identificador**, no del dato.

| Fuente | Nivel | Autoritativa para | Fundamento |
|---|---|---|---|
| `SEC_REGISTRY` | AUTHORITATIVE | `CIK` | es el registro que lo asigna |
| `SEC_20F` | AUTHORITATIVE | `CIK`, `CUIT` | sólo si el documento declara el bloque; cobertura medida 1/4 (ciclo 3C) |
| `GLEIF` | AUTHORITATIVE | `LEI`, `CUIT` | `CUIT` sólo si `registeredAt ∈ {RA000009, RA000010}` |
| `AFIP` | AUTHORITATIVE | `CUIT` | máxima autoridad; **no automatizable** (captcha) |
| `CNV_PORTAL` | DISCOVERY_ONLY | — | **no declara el CUIT del emisor**, sólo el del auditor |
| `LEGACY_DIM_ENTITY` | CORROBORATING | — | sin autor ni evidencia; ya falló (F-024) |
| `MARKET_CATALOG` | CORROBORATING | — | propone entidad↔instrumento, no identidad jurídica |
| `HUMAN` | AUTHORITATIVE | — | capacidad permanente (G5) |

---

## 3. La relación CIK ↔ CUIT

**Ninguna fuente automática puede producirla.** G5 lo estableció y este contrato lo asume:

- SEC no publica el LEI del registrante (0/6 en el control sobre XBRL/DEI, 20-F, 13D/13G).
- GLEIF no publica el CIK.
- **Un LEI coincidente NO demuestra que un CIK y un CUIT sean la misma entidad.** GLEIF
  vincula `LEI → CUIT`; nada vincula `CIK → LEI` salvo una persona.

Por lo tanto la cadena `CIK → LEI → CUIT` tiene **un eslabón no demostrado**, y el CUIT
obtenido por esa vía **no puede ser autoritativo** sobre una entidad anclada en CIK sin un
bridge `HUMAN_DECISION` ratificado con evidencia de ambos extremos.

Las únicas vías admisibles para un CUIT autoritativo:
1. `SEC_20F` que declare el CUIT del registrante → `VERIFIED`.
2. `GLEIF` sobre una entidad **no anclada en CIK** → `VERIFIED`.
3. `GLEIF` sobre una entidad anclada en CIK **con bridge ratificado** → `VERIFIED`.
4. `AFIP` (hoy manual) → `VERIFIED`.

---

## 4. Estados

| Estado | Cuándo | Qué se puede hacer con el dato |
|---|---|---|
| `OBSERVED` | una fuente `DISCOVERY_ONLY` lo menciona | nada; sólo rastrear |
| `CANDIDATE` (= CORROBORATED) | una fuente `CORROBORATING` lo propone | corroborar; **nunca** establecer |
| `REVIEW_REQUIRED` | ambigüedad, contradicción, o eslabón no demostrado | nada, hasta que decida una persona |
| `VERIFIED` | fuente autoritativa **para ese tipo** + cita + autor | usar |
| `REJECTED` | el identificador ya pertenece autoritativamente a otra entidad | nada; queda conflicto abierto |

`OBSERVED` y `CANDIDATE` se materializan ambos como `status='CANDIDATE'` con
`confidence='WEAK'`; se distinguen por `source_id` y su `authority_level`.

---

## 5. Prohibiciones duras

- **El nombre no crea identidad.** Ninguna coincidencia de razón social produce un bridge.
- **El ticker no crea identidad.** Bloqueado por `ck_ticker_no_autoritativo`.
- **No hay fuzzy matching.** Ninguna comparación aproximada entra al backfill.
- **`entity_id` legacy coincidente no es evidencia**; entra como `LEGACY_ENTITY_ID`.
- **LEI coincidente no demuestra `CIK ↔ CUIT`** (§3).

---

## 6. Provenance mínima

Todo identificador exige una assertion (`identifier.assertion_id NOT NULL`) con
`source_id`, `source_record` (localizable), `evidence` (cita reproducible por un tercero) y
`resolved_by`. Un `VERIFIED` sin los tres últimos es imposible (`ck_verified_exige_evidencia`).
Un proceso no puede firmar `HUMAN_DECISION` (`ck_humano_no_es_proceso`).

---

## 7. Comportamiento ante casos límite

| Caso | Comportamiento |
|---|---|
| El identificador ya es autoritativo de **otra** entidad | `REJECTED` + `conflict` abierto |
| La entidad ya tiene **otro** valor autoritativo del mismo tipo | `REVIEW_REQUIRED` + `conflict` + `review` |
| **CUIT de un tercero** hallado en un documento | no se atribuye al emisor del documento: es un CUIT *observado*, no *del emisor*. `CNV_PORTAL` publica el CUIT del **auditor** — nunca entra como CUIT del emisor |
| **GLEIF con `registeredAs = null`** (o `registeredAt ∉ {RA000009, RA000010}`) | no se deriva CUIT. `REVIEW_REQUIRED` con el motivo escrito. **No se infiere del nombre del registro** |
| CUIT con checksum inválido | `REJECTED` (`ck_formato_identificador`, módulo 11 en la base) |
| CIK almacenado en la columna `cuit` (F-024) | `REJECTED` por checksum + se registra el conflicto. **No se “arregla” moviéndolo de columna por inferencia** |
| Entidad sin ningún identificador autoritativo posible | queda `UNRESOLVED`, no se crea |

---

## 8. Reversibilidad y auditabilidad

- El piloto escribe **sólo** en `identity_v1`, con `entity_key` opaco y provenance completa.
- Es **idempotente**: resuelve por identificador autoritativo antes de crear.
- Es **reversible** por su `run_id`: todo lo que escribe queda etiquetado.
- No escribe en `data/raw/`, ni toca SEC, CNV ni Market.

---

## 9. Composición del piloto — 12 emisores, por clase de dificultad

| Clase | Emisores | Por qué está |
|---|---|---|
| CIK + CUIT + LEI | YPF, CEPU, TGSU2 | caso completo; CUIT vía GLEIF |
| CIK + LEI, **sin CUIT** | GGAL | `RA999999`, `registeredAs = null` |
| **Conflicto histórico** | YPF ↔ CEPU | el CUIT `33650305499` atribuido a YPF |
| **Ticker US ≠ BYMA** | YPF (`YPFD`/`YPF`), TGSU2 (`TGSU2`/`TGS`) | colisión de namespace |
| **CUIT sin CIK** (argentinas) | CAAP, GGALB, SUPVB, YPFLUZ | no hay ancla SEC; el bridge no aplica |
| **Dato corrupto en origen** | BMA | CIK guardado en la columna `cuit` (F-024) |
| **Sólo CIK** (US puro) | AAPL, MSFT | el CUIT no aplica; mide el costo real del universo US |

Cobertura de fuentes: SEC (`derived.fact`, 1 CIK real), GLEIF (API), CNV
(`fetch_raw.cnv_presentation`, 1 CUIT real), Market (`market_instruments`, 584 en catálogo).

---

## 10. Criterio de aceptación del piloto

1. Ningún identificador autoritativo sin provenance completa.
2. Ninguna entidad con dos identificadores autoritativos del mismo tipo.
3. El pairing YPF + CUIT de CEPU **rechazado por la base**.
4. Cero bridges `CIK↔LEI` en `VERIFIED` sin ratificación humana.
5. Cero CUIT derivados de nombre, ticker o fuzzy.
6. El piloto reproducible: dos corridas dejan el mismo estado.
7. Todo lo no demostrable, contado y clasificado — no omitido.
