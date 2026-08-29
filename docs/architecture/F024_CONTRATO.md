# F-024 — CONTRATO DE TRATAMIENTO

**Fecha:** 2026-08-28 · **Alcance:** exclusivamente la entidad BMA (Banco Macro).
**Escrito antes de modificar nada.**

---

## 1. AS-IS

```
dim_entity 572   ticker_canonico='BMA'  grupo='adr'  cuit='0001347426'  cik=NULL
identity_v1      BMA no existe: el backfill piloto la RECHAZA porque '0001347426'
                 no pasa el modulo 11
```

El error se propagó: `adr_dividendos.cuit` tiene 25 filas con el mismo valor.

## 2. Qué es `0001347426` — evidencia, no inferencia

**Fuente primaria** (`data/raw/catalogo_edgar/company_tickers_2026-08-23.json`, descargado
de SEC):

```json
{"cik_str": 1347426, "ticker": "BMA", "title": "Macro Bank Inc."}
```

**Fuente primaria** (`data/raw/submissions/CIK0001347426.json`):

```
cik 0001347426 · name "Macro Bank Inc." · tickers ['BMA'] · exchanges ['NYSE']
sic 6029 Commercial Banks · domicilio AV. EDUARDO MADERO 1182, BUENOS AIRES
1000 filings: 941 6-K, 19 20-F
```

Corroboración en catálogos derivados: el mismo valor figura como **`cik`** en
`empresas` (`Macro Bank Inc.`, fuente `edgar`), `tickers`, `precios`, `ratios`,
`cnv_estados`, y sostiene 1.473 filas en `facts` y 4.101 en `facts_xbrl`.

**`0001347426` es el CIK de Macro Bank Inc.** No es un CUIT: tiene 10 dígitos y no pasa el
módulo 11.

### El vínculo NO es por nombre ni por ticker

La fila legacy 572 **contiene el valor `0001347426`**. SEC declara ese valor como CIK. El
identificador correcto ya estaba en la fila, en la columna equivocada. No se infiere nada de
la razón social ni del ticker: se lee el dato que la fila trae y se lo tipa bien.

## 3. Identidad demostrable de BMA

| Identificador | Valor | Fuente | Autoridad | Confianza | Estado Identity V1 |
|---|---|---|---|---|---|
| **CIK** | `0001347426` | `company_tickers.json` + `submissions/CIK0001347426.json` | `SEC_REGISTRY` — autoritativa para CIK | alta | **VERIFIED** |
| **LEI** | **ambiguo** | GLEIF (búsqueda por nombre = DISCOVERY) | — | — | **REVIEW_REQUIRED** |
| **CUIT** | **no demostrable** | — | — | — | **ausente** |

### Por qué el LEI queda ambiguo

GLEIF devuelve **dos** registros vigentes para `BANCO MACRO SOCIEDAD ANONIMA`:

| LEI | status | registeredAs | domicilio |
|---|---|---|---|
| `579100KKDKKIFEBKK040` | ACTIVE | `30-50001008-4` | MADERO EDUARDO AV. 1182, BUENOS AIRES |
| `579100KKDKKIFEBKK058` | NULL | `30500010084` | 447 SARMIENTO, CAPITAL FEDERAL |

El domicilio del primero coincide con el que SEC declara. **Eso es corroboración, no
autoridad**: ninguno de los dos menciona el CIK, y elegir por domicilio sería exactamente el
tipo de inferencia que el contrato prohíbe. Dos LEI vigentes para la misma razón social es
una **ambigüedad que decide una persona**.

El CUIT `30500010084` pasa el módulo 11, pero llega por una cadena
`nombre → LEI → CUIT` cuyo primer eslabón es DISCOVERY. **No se establece.**

## 4. TO-BE

```
identity_v1   entidad BMA, anclada en CIK 0001347426 (VERIFIED, fuente SEC_REGISTRY)
              CUIT ausente · LEI ausente
              1 conflicto abierto: el legacy declara como CUIT un valor que SEC
                declara como CIK
              1 review abierta: LEI ambiguo (2 candidatos GLEIF)
dim_entity    SIN MODIFICAR — es el registro histórico del error
```

## 5. Regla de identidad

- El CIK se establece porque **SEC lo declara**, no porque el nombre o el ticker coincidan.
- El valor `0001347426` **nunca** entra como CUIT: lo impide `ck_formato_identificador`
  (módulo 11) y ahora también el conflicto registrado.
- El LEI y el CUIT permanecen **ausentes** hasta que una persona resuelva la ambigüedad.

## 6. Tratamiento del valor `0001347426`

**Se conserva la evidencia histórica y se corrige la interpretación.**

- No se toca `dim_entity`: es el registro de lo que el legacy afirmó, y borrarlo destruiría
  la evidencia del error.
- En Identity v1 el valor entra **como CIK**, que es lo que es, con provenance de SEC.
- El error queda registrado como `conflict` explícito, citando la fila legacy.

## 7. Invariantes

1. `0001347426` no existe como CUIT autoritativo en `identity_v1`.
2. BMA tiene exactamente **un** CIK autoritativo.
3. BMA **no** tiene CUIT ni LEI autoritativos.
4. Existe al menos un `conflict` que documenta el mistyping del legacy.
5. `dim_entity` queda intacta.
6. El tratamiento es idempotente: ejecutarlo N veces no duplica nada.

## 8. Acceptance tests

| # | Verifica |
|---|---|
| 1 | BMA existe en `identity_v1` con CIK `0001347426` **VERIFIED** |
| 2 | `SELECT count(*) FROM identity_v1.identifier WHERE id_type='CUIT' AND id_value='0001347426'` = **0** |
| 3 | Intentar insertarlo como CUIT → rechazado por `ck_formato_identificador` |
| 4 | BMA sin CUIT y sin LEI autoritativos |
| 5 | Existe un `conflict` que cita `dim_entity#572` |
| 6 | `dim_entity` sin cambios (`cuit='0001347426'`, `cik=NULL`) |
| 7 | Dos ejecuciones del tratamiento dejan el mismo estado |
| 8 | No aparece una segunda entidad para el CIK `0001347426` |
