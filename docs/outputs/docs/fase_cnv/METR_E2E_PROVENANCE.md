# METR E2E — PROVENANCE

**Fecha:** 2026-09-02 · fixture aislado `cnvmig` + RAW en disco

Todo lo que sigue es reproducible por un tercero abriendo el archivo HTML.

---

## 1 · Ficha de un dato — `Revenue` FY2025 CONSOLIDADO

```
METR · Metrogas S.A.
  ↓
CUIT 30657863676
  ↓
entity_id      CUIT:30657863676
entity_key     EY9TRR9RPRVSV916PD0CB9Z93NT
identificador  CUIT:AFIP:30657863676 · autoritativo · ACTIVE
  ↓
Documento CNV · Presentación #3487124
accn           d96fd259-c5ce-431f-8e14-17af592b99f9
archivo        d96fd259-c5ce-431f-8e14-17af592b99f9.html
SHA-256        460d167241febbe3a3be8142c44be60c6c5eebfd4dc76c53a71b3dfca9b6b191
  ↓
Concepto CNV   código 3000100 · "INGRESOS DE ACTIVIDADES ORDINARIAS"
qname          cnv:Revenue
  ↓
Ocurrencia
fact_key       e270dfb8681a133b088b38a677bdc3bb0e828d1072f208a50c6df247160a57f3
               = sha256(entity_key | accn | qname | context_id | unit_measure)
  ↓
Identidad económica
econ_key       9b0c12ce7825100d46e6c61bd80a26cd40f563064472e3ba56eb67be18e1a7c6
               = sha256(entity_id | qname | perímetro | period_kind
                        | start_date | end_date | unit_measure | measurement_date)
  ↓
Período        DURATION · 2025-01-01 → 2025-12-31
context_id     CONSOLIDADO|DURATION|2025-01-01|2025-12-31|2025-12-31
measurement_date  2025-12-31   (FechaCierre declarada por el documento)
  ↓
Perímetro      CONSOLIDADO   (TipoBalance declarado en el documento)
  ↓
Unidad         unit_measure = iso4217:ARS
               unit_ref     = ars@1e6      ← la escala, como provenance
               decimals     = NULL         ← la CNV no declara precisión
  ↓
Valor
   impreso en el documento      1.217.305,00
   UnidadMedida declarada       "Millones de $"  →  factor 10⁶
   normalizado                  1.217.305.000.000
  ↓
source_kind    CNV_EEFF
```

### Cómo lo reproduce un tercero

1. Abrir `eeff_html/d96fd259-c5ce-431f-8e14-17af592b99f9.html`.
2. `sha256sum` → `460d1672…b6b191`.
3. Buscar `UnidadMedida` → `Millones de $` → factor 10⁶.
4. Buscar el código `3000100` → el número que le sigue es `1217305.00`.
5. `1.217.305,00 × 10⁶ = 1.217.305.000.000`.
6. Buscar `PeriodoBalance` → `1` (anual) y `FechaCierre` → `2025-12-31`.
7. El inicio del ejercicio sale de los documentos anuales del propio emisor:
   los 16 con `PeriodoBalance=1` cierran todos el **12-31**, luego el ejercicio
   empieza el **01-01**.

Ninguno de esos siete pasos requiere el código de Catalaxia.

---

## 2 · Ficha de un ratio — margen neto FY2025 CONSOLIDADO

```
METR · período 2025-01-01 → 2025-12-31 · CONSOLIDADO

ratio      net_margin
valor      0,10883304          (10,88 %)
unidad     xbrli:pure          adimensional: no lleva moneda
fórmula    NetIncome / Revenue

┌─ numerador ──────────────────────────────────────────────────────────
│  concepto    cnv:NetIncome · código CNV 3049999
│  valor       132.483.000.000
│  unidad      iso4217:ARS · unit_ref ars@1e6
│  período     DURATION 2025-01-01 → 2025-12-31
│  fact_key    2f7d72b238de410b7aaf1ba5481999e6e1101af2c727cbc225b6621526fd7a4f
│  econ_key    66d469d1afa31447a424d8a7bed7f24c41f89af8dd376cbdc8d6aa308ecbc330
│  accn        d96fd259-c5ce-431f-8e14-17af592b99f9
│  SHA-256     460d167241febbe3a3be8142c44be60c6c5eebfd4dc76c53a71b3dfca9b6b191
│  en el RAW   132.483,00 × 10⁶
└──────────────────────────────────────────────────────────────────────

┌─ denominador ────────────────────────────────────────────────────────
│  concepto    cnv:Revenue · código CNV 3000100
│  valor       1.217.305.000.000
│  unidad      iso4217:ARS · unit_ref ars@1e6
│  período     DURATION 2025-01-01 → 2025-12-31
│  fact_key    e270dfb8681a133b088b38a677bdc3bb0e828d1072f208a50c6df247160a57f3
│  econ_key    9b0c12ce7825100d46e6c61bd80a26cd40f563064472e3ba56eb67be18e1a7c6
│  accn        d96fd259-c5ce-431f-8e14-17af592b99f9
│  SHA-256     460d167241febbe3a3be8142c44be60c6c5eebfd4dc76c53a71b3dfca9b6b191
│  en el RAW   1.217.305,00 × 10⁶
└──────────────────────────────────────────────────────────────────────

132.483.000.000 / 1.217.305.000.000 = 0,10883304
```

**Los dos insumos comparten `start_date`, `end_date`, `period_kind`,
`measurement_date` y perímetro.** Es la condición que el auditor verifica antes
de dividir: sin ella el ratio sale `NOT_CALCULABLE`.

La escala se cancela en el cociente, pero eso **no** es lo que lo hace
correcto: lo que lo hace correcto es que los dos valores estén normalizados a
la misma unidad antes de dividir.

---

## 3 · Reconciliación manual contra el RAW

Ocho conceptos del documento FY2025 CONSOLIDADO, comparados uno por uno:

| concepto | impreso en el RAW | × factor | esperado | persistido | estado |
|---|--:|--:|--:|--:|---|
| Assets | 1.390.076,00 | 10⁶ | 1.390.076.000.000 | 1.390.076.000.000 | **MATCH** |
| Cash | 116.132,00 | 10⁶ | 116.132.000.000 | 116.132.000.000 | **MATCH** |
| **EPS_basico** | **229,62** | **1** | **229,62** | **229,62** | **MATCH** |
| Equity | 960.345,00 | 10⁶ | 960.345.000.000 | 960.345.000.000 | **MATCH** |
| Liabilities | 429.731,00 | 10⁶ | 429.731.000.000 | 429.731.000.000 | **MATCH** |
| NetIncome | 132.483,00 | 10⁶ | 132.483.000.000 | 132.483.000.000 | **MATCH** |
| OperatingIncome | 196.311,00 | 10⁶ | 196.311.000.000 | 196.311.000.000 | **MATCH** |
| Revenue | 1.217.305,00 | 10⁶ | 1.217.305.000.000 | 1.217.305.000.000 | **MATCH** |

```
8 MATCH · 0 MISMATCH · 0 UNKNOWN
```

**La única transformación es la multiplicación por la escala declarada por el
propio documento**, y `EPS_basico` no la lleva —factor 1— porque la CNV lo
publica ya en pesos por acción. Es la regla `NO_FACTOR` del contrato W-1.2, y
se verifica en el dato: 229,62 impreso, 229,62 persistido.

---

## 4 · Revenue 2025 — el período económico

| período económico | valor persistido | trimestre derivado |
|---|--:|--:|
| 2025-01-01 → 2025-03-31 | 205.186.000.000 | 205.186.000.000 |
| 2025-01-01 → 2025-06-30 | 504.193.000.000 | 299.007.000.000 |
| 2025-01-01 → 2025-09-30 | 898.642.000.000 | 394.449.000.000 |
| 2025-01-01 → 2025-12-31 | 1.217.305.000.000 | 318.663.000.000 |

**Los cuatro empiezan el 2025-01-01.** El valor persistido es el **acumulado
del ejercicio**, que es lo que el documento publica.

La columna de la derecha es `YTD(n) − YTD(n−1)` y **no se persiste**.

> **CORRECCIÓN (ciclo TIKR).** Al publicar esta tabla presenté esa derivación
> como si sólo faltara persistirla. **No es válida como está.** Los cuatro
> documentos tienen `measurement_date` distintas —2025-03-31, 06-30, 09-30 y
> 12-31—, que es exactamente lo que `econ_key` distingue: bajo IAS 29 cada
> estado expresa sus cifras en el poder adquisitivo de su propio cierre.
> Restar `YTD(Q4)` en moneda de diciembre menos `YTD(Q3)` en moneda de
> septiembre **mezcla dos unidades de medición**.
>
> La columna queda como ilustración de que el acumulado está bien
> representado, no como una derivación correcta del trimestre. Derivar el
> trimestre aislado exige primero llevar los dos acumulados a la misma
> `measurement_date`, y eso requiere un índice de re-expresión que Catalaxia
> no tiene.

### Por qué el inicio es el 01-01 y no está hardcodeado

```
16 documentos de METR con PeriodoBalance = 1 (anuales)
     ↓
todos declaran FechaCierre con mes-día 12-31
     ↓
cierre de ejercicio = 12-31
     ↓
inicio del ejercicio = día siguiente al cierre anterior = 01-01
```

Si un emisor no tuviera documentos anuales, o declarara más de un cierre, la
derivación devuelve `None` y sus flujos quedan fuera. No se les inventa una
duración.
