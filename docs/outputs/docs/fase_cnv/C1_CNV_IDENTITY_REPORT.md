# C1 — IDENTITY REPORT — Golden Case CEPU (CNV)

Generado: 2026-08-24 12:10 UTC
Alcance: formalizar la identidad de CEPU para el pipeline CNV y dejar en cola de revision
todo lo ambiguo (controladas). Principio aplicado: *el ticker NO es la identidad* —
puente CIK (SEC) <-> CUIT (CNV) <-> tickers vigentes.

## 1. Identidad canonica resuelta

| campo | valor | fuente de registro |
|---|---|---|
| entity_key | `CIK:0001717161` | convencion engine identity.* |
| entity_id (screener.db) | 70 | dim_entity |
| Razon social legal | **CENTRAL PUERTO S.A.** | SEC (empresas) |
| CUIT | 33650305499 | CNV (pagina empresa) |
| CIK | 0001717161 | SEC |
| Tickery instrumentos | CEPU/BYMA ordinaria ARS (ratio NULL) · CEPU/NYSE ADR USD (**ratio 10**) | dim_instrument 80/81 |
| Grupo / moneda / FY | adr · ARS · cierre dic-12 (SEC 1231) | dim_entity |

Coherencia verificada: la pagina CNV (`Empresa/33650305499`) titula "Central Puerto | 33650305499";
SEC lista a `CENTRAL PUERTO S.A.` con ticker CEPU/NYSE; dim_instrument tiene ambos mercados.
Sin colisiones: ni el CUIT ni el CIK aparecen en otra entidad.

Aliases aceptados (no identidades): "Central Puerto" (display), "Central Puerto S.A."
(adjuntos CNV), "CENTRAL PUERTO S.A." (legal). Placeholder legacy `mapa_entidades.ticker='_ADR_5499'`
marcado RETIRED en el seed (patron pre-puente, nunca usarlo como clave).

## 2. Controladas publicadas bajo el perfil CEPU

135 filas EEFF_CONTROLADA en el inventario live -> **20 CUITS distintos** tras
normalizar sufijos societarios (S.A./S.A.U.). Regla aplicada: mismo CUIT + grafias distintas =
UNA entidad con alias multiples; CUITS distintos = entidades separadas HASTA revisar.

| CUIT | pres. | nombres observados (grafias) |
|---|---|---|
| `30711900582` | 13 | CENTRAL VUELTA DE OBLIGADO S.A. (x13) |
| `30709504904` | 8 | TERMOELÉCTRICA MANUEL BELGRANO S.A. (x4); TERMOELÉCTRICA MANUEL BELGRANO (x3); TERMOLEÉCTRICA MANUEL BELGRANO S.A. (x1) |
| `30715255975` | 7 | VIENTOS LA GENOVEVA S.A.U. (x5); VIENTOS LA GENOVEVA SAU (x2) |
| `30715163760` | 7 | CP RENOVABLES S.A. (x6); VIENTOS LA GENOVEVA II SAU (x1) |
| `30709508772` | 7 | TERMOELÉCTRICA JOSE DE SAN MARTÍN (x3); TERMOELÉCTRICA JOSÉ DE SAN MARTÍN S.A. (x3); TERMOELÉCTRICA JOSE DE SAN MARTÍN S.A. (x1) |
| `33677297579` | 6 | PROENER S.A.U. (x3); PROENER SAU (x3) |
| `30715562819` | 5 | VIENTOS LA GENOVEVA II S.A.U. (x4); VIENTOS LA GENOVEVA II SAU (x1) |
| `33657865279` | 5 | DISTRIBUIDORA DE GAS DEL CENTRO S.A. (x5) |
| `33657865589` | 5 | DISTRIBUIDORA DE GAS CUYANA S.A. (x4); DISTRIBUIDORA DE GAS GUYANA S.A. (x1) |
| `30715345435` | 2 | CP LA CASTELLANA S.A.U. (x2) |
| `30715328042` | 2 | CP ACHIRAS S.A.U. (x2) |
| `30715678841` | 2 | LOMA ALTA FORESTAL S.A. (x2) |
| `30711928576` | 2 | CENTRAL VUELTA DE OBLIGADO S.A. (x2) |
| `30715641840` | 1 | CP CORDILLERA SOLAR S.A. (x1) |
| `30687143619` | 1 | FORESTAL ARGENTINA S.A. (x1) |
| `30677297579` | 1 | PROENER S.A.U. (x1) |
| `30716342804` | 1 | CP MANQUE S.A.U. (x1) |
| `30715345451` | 1 | PUERTO ENERGIA S.A.U. (x1) |
| `30717065065` | 1 | VUELTA DE OGLIGADO S.A. (x1) |
| `30695541860` | 1 | TRANSPORTADORA DE GAS DEL MERCOSUR S.A. (x1) |

Casos resueltos por convencion (alias del mismo CUIT): Termoelectrica Manuel Belgrano
(x8, 3 grafias incl. typo "TERMOLEcTRICA"), Termoelectrica Jose de San Martin (x7, 2 grafias),
Distribuidora de Gas Cuyana/GUYANA (x5, typo en fuente), Vientos La Genoveva I/II.

## 3. Cola de revision (IDENTITY_REVIEWS)

| review | ids | estado | motivo |
|---|---|---|---|
| C1-R-001 | `33677297579 | 30677297579` | OPEN | Mismo nombre 'PROENER S |
| C1-R-002 | `30711900582 | 30711928576 | 30717065065` | OPEN | Nombre casi identico 'VUELTA DE OBLIGADO S |
| C1-R-003 | `30715163760` | OPEN | CUIT mayormente asociado a 'CP RENOVABLES S |
| C1-R-004 | `(vacio)` | OPEN | 57 presentaciones de controladas sin CUIT parseable en el titulo (formato RELAC |
| C1-R-005 | `30695541860` | OPEN | TGS (controlada publicada bajo perfil CEPU) YA EXISTE como entidad independiente (entity_id=53, ticker=TGNO4) |

Politica: **no se crean entidades nuevas** para controladas hasta resolver R-001 (PROENER
dual-CUIT), R-002 (Vuelta de Obligado triple-CUIT) y R-005 (TGS ya existe como entidad
independiente del universo — vincular por CUIT, jamas duplicar). R-004 (parser de RELAC.)
se ataca en C2/C3 y no afecta la identidad de CEPU.

## 4. Modelo y artefactos

* Seed declarativo: `data/catalogo/cnv_identity_seed_cepu.csv` (schema engine `identity.entities`
  + `identifiers`, listo para migrar a PostgreSQL cuando corresponda).
* Cola: `outputs/docs/fase_cnv/C1_CNV_IDENTITY_REVIEWS.csv` (formato estandar reviews).
* DB screener.db NO fue mutada (es derivada; cambios estructurales van por migrations/engine).

## 5. Hallazgos

1. `mapa_entidades` usa placeholders `_ADR_<ultimos5>` como ticker para ADRs: deuda tecnica
   del puente viejo; el seed lo declara RETIRED.
2. Las fuentes cargan nombres mal tipiados o truncados (GUYANA, OGLIGADO, TERMOLEcTRICA,
   PROENER sin S.A.): toda igualdad de entidades debe pasar por CUIT, nunca por nombre.
3. `cnv_filings` solo cubre NIIF 2018+ (107 filas) frente a 149 EEFF live desde 2004: gap
   historico del parser viejo, se regenera en C3.
4. Periodicidad codificada T/A/S en `cnv_filings` vs textual en titulos CNV: normalizar en C8.

## 6. Veredicto

**C1 PASS -> READY_FOR_C2** (condiciones en C1_CNV_IDENTITY_VALIDATION.json).
