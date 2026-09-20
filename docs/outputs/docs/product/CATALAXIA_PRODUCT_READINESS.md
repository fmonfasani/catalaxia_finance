# CATALAXIA — PRODUCT READINESS AUDIT

**2026-09-01** · auditoría de superficie comercial · sin commits
Sin cambios en SEC, CNV, Identity ni Market. Una sola adición de código, en §4.

---

# CATALAXIA_PRODUCT_READINESS = **READY_FOR_DEMO**

Lista para mostrarse a un cliente **conducida por nosotros**, sobre la
superficie canónica. **No** lista para que un cliente consulte por su cuenta:
hoy no existe ninguna vía por la que un cliente acceda a la superficie canónica
sin nosotros — y sí existen varias por las que llegaría a datos legacy.

---

## 1. Superficie canónica — y las fugas hacia legacy

### Lo que un cliente puede consumir hoy

| componente | estado | vía |
|---|---|---|
| `derived.ratio` (32 celdas) | **canónico** | CLI `ratio_api.py` |
| `derived.fact` (88.789) | **canónico** | CLI, vía `--fundamental` |
| provenance → `parsed.facts` → RAW | **canónico** | CLI, vía `--provenance` |
| Identity V1 | **canónico** | resolución interna de `--ticker`/`--cik` |
| Market (`market_price_daily`) | **canónico** | insumo de P/B, P/E, EV/Sales |

### LAS FUGAS — medidas, no supuestas

Hay **dos bases de datos distintas**, y la que sirve al cliente no tiene nada
canónico:

```
catalaxia-engine-dev   127.0.0.1:5433   derived.fact · derived.ratio · identity_v1
catalaxia-db           127.0.0.1:5432   ← la que sirve la API
```

```sql
-- sobre catalaxia-db (5432), el que consume la API
derived.ratio       NO EXISTE
derived.fact        NO EXISTE
identity_v1.entity  NO EXISTE
public.screener     screener        ← legacy
```

**La API apunta por defecto a 5432** (`DB_PORT`, default `"5432"`). La
superficie canónica nunca se desplegó ahí.

Y **cero de los endpoints leen algo canónico**:

```
grep -cE "derived\.|identity_v1|parsed\." api/main.py  →  0
```

| vía por la que un cliente recibiría datos legacy | sirve | procedencia |
|---|---|---|
| `GET /v2/screener` · `/v2/screener/{ticker}` | tabla `screener` (S4) | **ninguna** |
| `GET /v2/screener/hist/{ticker}` | `screener_hist` | ninguna |
| `GET /v2/grupos` · `/v2/stats` | `screener` | ninguna |
| `GET /v1/ratios` | `silver_norm` — que **no son ratios** sino hechos normalizados de un solo emisor | ninguna |
| `GET /v1/validaciones` · `/v1/certificacion` | tablas legacy | ninguna |
| `docs/producto/screener.html` (595 KB, publicado) | `screener_gold` (S3) | ninguna |
| 10 dashboards HTML en la raíz del repo | legacy | ninguna |
| `nginx` en `:9200`, API en `:8100` | todo lo anterior | ninguna |
| `scripts/deploy/sincronizar_a_produccion.py` | empuja SQLite → PostgreSQL de producción | — |

**Conclusión: toda superficie hoy consumible por un cliente sirve datos legacy
sin procedencia.** Ver §9 B1.

### Contención propuesta para la demo

No se modifica nada —el encargo lo prohíbe—; se **acota el alcance de la
demo**, y queda escrito en el guion:

1. la demo corre **exclusivamente** contra 5433 vía CLI;
2. no se abre el screener publicado, ni `:8100`, ni `:9200`;
3. el guion incluye la respuesta preparada para *«vi otro screener suyo con más
   empresas»* — decirlo antes de que lo descubran.

---

## 2. Dataset demo

Ocho emisores. **Ningún dato fabricado**: lo que falta está persistido como
`NOT_CALCULABLE` con motivo.

| emisor | identity | fundamentals | market | EPS | P/B | P/E | EV/Sales |
|---|---|---|---|:-:|:-:|:-:|:-:|
| Apple Inc. | CIK `VERIFIED` · 2 instr. | 2.085 facts · 2 filings | 23.038 precios | ✓ | ✓ | ✓ | ✓ |
| Microsoft Corp. | `VERIFIED` · 2 | 3.460 · 2 | 20.386 | ✓ | ✓ | ✓ | ✓ |
| NVIDIA Corp. | `VERIFIED` · 2 | 2.505 · 2 | 13.884 | ✓ | ✓ | ✓ | ✓ |
| Transportadora de Gas del Sur | `VERIFIED` · 4 | 7.301 · 2 | 29.266 | ✓ | ✓ | ✓ | ✓ |
| YPF S.A. | `VERIFIED` · 2 | 47.930 · **9** | 14.985 | ✓ | ✓ | — | ✓ |
| Central Puerto S.A. | `VERIFIED` · 2 | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Grupo Financiero Galicia | `VERIFIED` · 2 | ✓ | ✓ | ✓ | — | ✓ | — |
| Macro Bank Inc. | `VERIFIED` · **sin instrumento** | ✓ | sin enlace | ✓ | — | — | — |

```
32 celdas · 25 CALCULADO · 7 NOT_CALCULABLE
provenance: 27 COMPLETA · 5 AUSENTE (todas NOT_CALCULABLE)
CALCULADO con provenance != COMPLETA: 0
```

**El invariante que sostiene la demo: `CALCULADO ⇒ COMPLETA`, sin excepción.**

Los dos bancos se dejan a propósito. Un conjunto que sólo mostrara Apple y
NVIDIA sería una demo; con Galicia y Macro adentro es una prueba de que el
sistema declara sus límites en vez de rellenarlos.

---

## 3. Demo vertical

`CATALAXIA_CUSTOMER_DEMO.md` — siete tramos, 5:00 exactos, todo en vivo.

| | | cubre |
|---|---|---|
| 00:00 | problema | las tres preguntas sin respuesta |
| 00:45 | **empresa** | identidad opaca, no ticker |
| 01:30 | **fundamentals** | concepto vs tag, cadena de fallback |
| 02:15 | **ratio** + **fórmula** | `window: FY`, versión de fórmula |
| 03:00 | **inputs** + **provenance** + **filing** + **fuente** | cadena entera, cuenta a mano, verificador independiente |
| 04:00 | **`NOT_CALCULABLE`** | las dos familias |
| 04:30 | piloto | alcance y límites |

Los ocho elementos pedidos están. `NOT_CALCULABLE ≠ 0 ≠ error` se demuestra con
**dos casos contrastados**, no con una explicación: uno donde falta el dato y
otro donde la procedencia está completa y aun así no hay número.

---

## 4. API / query surface

**Existe y es suficiente para demo y para entrega de piloto.**
`scripts/engine/ratio_api.py` — CLI, JSON, sólo lectura.

| dimensión pedida | cómo se consulta | en la respuesta |
|---|---|---|
| company | `--ticker` / `--cik` | `entity_key`, `nombre`, `cik` |
| metric | `--ratio` / `--fundamental` | `canonical_id` |
| period | `--period` | `period_end` |
| window | `--window` | `window` |
| currency | `--currency` | `currency` |
| value | — | `value` |
| status | `--status` | `status` + `motivo` |
| provenance | `--provenance` | `provenance_status` + cadena |

### La única adición de código de este ciclo

Faltaban los filtros `--period` y `--currency`, que estaban en la lista de
dimensiones exigidas aunque los campos ya se devolvían. Se agregaron: un
predicado SQL más y una clase `Filtros` de cinco atributos. **Nada más se tocó.**

### Formato de entrega para el piloto

`--universo --provenance` produce el conjunto completo en un JSON autocontenido
—**132.028 bytes, 8 empresas, 32 celdas con procedencia**— regenerable con un
comando: `outputs/docs/product/CATALAXIA_SLICE_EXPORT.json`.

### Lo que no existe

Endpoint HTTP e interfaz web sobre la superficie canónica. **Especificados en la
propuesta de piloto, no construidos** — construirlos habría sido funcionalidad
nueva, y no es necesaria para que el cliente ejecute el vertical slice en una
demo conducida ni para recibir el archivo de entrega.

---

## 5. Documentos creados

| | |
|---|---|
| `CATALAXIA_PRODUCT_CONTRACT.md` | qué ofrece, fuentes, métricas, períodos, procedencia, `NOT_CALCULABLE`, límites, cobertura, y **qué NO promete** |
| `CATALAXIA_ONE_PAGER.md` | problema · solución · cómo funciona · ejemplo · diferencial · piloto · limitaciones · próximo paso |
| `CATALAXIA_PILOT_OFFER.md` | alcance, 8 empresas, 4 métricas, fuentes, período, entrega, procedencia, 4 semanas, 7 criterios de aceptación, pricing a discutir |
| `CATALAXIA_CUSTOMER_DEMO.md` | guion de 5:00 con las preguntas difíciles preparadas |
| `CATALAXIA_SLICE_EXPORT.json` | el conjunto entregable |

### Sobre el lenguaje comercial

Ninguno de los cuatro documentos usa «reemplazo de TIKR», «reemplazo de
Bloomberg», «100 % de cobertura», «todos los ratios», «tiempo real» ni «grado
institucional». Los tres claims que sí se hacen tienen evidencia numérica
detrás:

| claim | evidencia |
|---|---|
| «procedencia hasta el documento» | 25/25 celdas calculadas con cadena completa hasta archivo + SHA-256 |
| «verificación independiente» | 25/25 reproducidas, desvío máximo 1,59e-7, tolerancia 1e-6 |
| «aislamiento entre emisores» | 0 violaciones en 135.077 punteros + prueba de mutación |

---

## 6. Blockers comerciales

**Los que impedirían mostrar Catalaxia a un cliente: ninguno.**

La demo corre sobre la superficie canónica, con datos reales, y cada afirmación
del guion es verificable en vivo.

### B1 · Un blocker de PILOTO, no de demo

**No existe ninguna vía por la que un cliente consulte la superficie canónica
sin nosotros, y sí existen nueve por las que llegaría a datos legacy** (§1).

- **Para la demo:** contenido por alcance. La demo la conducimos nosotros y no
  se abre ninguna superficie legacy.
- **Para el piloto:** contenido por formato. La entrega es un archivo, no un
  acceso a un sistema.
- **Para producto:** es un blocker real. Un cliente con acceso a `:8100`
  recibiría números sin procedencia que pueden discrepar de los que le
  mostramos.

**Riesgo residual de la demo:** que el prospecto encuentre por su cuenta el
screener publicado o la API. Mitigación: el guion lo declara antes, en la
pregunta preparada.

---

## 7. Technical warnings — no bloquean

Conocidos, medidos y declarados en el contrato de producto. **No se convierte
ninguno en blocker.**

| | |
|---|---|
| W1 | No hay TTM; todas las métricas de flujo son `FY`, y la celda lo dice |
| W2 | 4 métricas de las 17 prioritarias del contrato técnico |
| W3 | Ninguna métrica con EBITDA hasta resolver la cadena de amortización (12 candidatos) |
| W4 | 8 emisores; el límite es la ingesta, no el cálculo |
| W5 | Los bancos con cobertura pobre — del modelo contable del sector |
| W6 | 3 fallos históricos de F-038 en la suite: preexistentes, de Market, ajenos |
| W7 | 11 decisiones de producto abiertas |
| W8 | Sin series históricas; el modelo las soporta, falta reprocesar |

---

## 8. Product gaps — faltan para vender, no para mostrar

| | |
|---|---|
| G1 | Endpoint HTTP e interfaz web sobre la superficie canónica |
| G2 | Actualización programada: hoy el motor se corre a mano |
| G3 | Series históricas |
| G4 | Cobertura más allá de 8 emisores |
| G5 | Un mecanismo de contención sobre las superficies legacy (marcarlas, versionarlas o retirarlas) |
| G6 | Sin evidencia de mercado para fijar precio |

---

## 9. Roadmap — orden de dependencia

| # | | desbloquea |
|---|---|---|
| 1 | **TTM** | comparabilidad de toda métrica de flujo contra cualquier fuente externa |
| 2 | **Ingesta a escala** | cobertura; hoy 8 de 513 entidades identificadas |
| 3 | **Decisión sobre EBITDA** | EV/EBITDA, deuda/EBITDA, margen EBITDA |
| 4 | **HTTP + interfaz** | consumo directo por el cliente — y cierra B1 |
| 5 | **Series históricas** | evolución temporal |
| 6 | Resto de decisiones de producto | ROE, ROIC, D/E, FCF, dividendos |

---

## 10. Dictamen

# CATALAXIA_PRODUCT_READINESS = **READY_FOR_DEMO**

### La evidencia que lo sostiene

| | |
|---|---|
| **Datos reales, superficie canónica** | 32 celdas persistidas en `derived.ratio` sobre 8 emisores con identidad verificada |
| **Procedencia completa donde importa** | 25/25 celdas calculadas con cadena hasta archivo + SHA-256. `CALCULADO ⇒ COMPLETA`, sin excepción |
| **Verificable sin confiar en nosotros** | un proceso sin código compartido reproduce 25/25 con desvío máximo 1,59e-7 |
| **Aislamiento entre emisores demostrado** | 0 violaciones en 135.077 punteros, más una prueba de mutación que confirma que la protección es la que decimos |
| **Los huecos declarados** | 7 `NOT_CALCULABLE`, cada uno con concepto faltante y cadena consultada; imposible por diseño que exista uno sin motivo |
| **Superficie de consulta completa** | las 8 dimensiones exigidas, en una CLI reproducible |
| **Documentación comercial sin claims falsos** | 4 documentos; ninguno usa el vocabulario prohibido; los 3 claims que hace tienen número detrás |
| **Guion de 5:00 verificado en vivo** | cada comando del guion se ejecutó |

### Por qué NO es READY_FOR_PILOT todavía

El ciclo anterior emitió `CATALAXIA_COMMERCIAL_READINESS = READY_FOR_PILOT`
mirando la **capacidad técnica** del slice. Esta auditoría mira la **superficie
comercial**, y encuentra algo que aquel gate no había medido: **la única vía de
acceso que un cliente tiene hoy sirve datos legacy** (§1, B1).

Eso no invalida el piloto: con la entrega en archivo, B1 queda contenido y el
piloto de `CATALAXIA_PILOT_OFFER.md` es ejecutable tal como está escrito. Lo
que cambia es el orden: **primero la demo, y el piloto sólo con entrega en
archivo y el alcance declarado por escrito** — nunca dando acceso a los sistemas
que corren hoy.

`READY_FOR_PILOT` sin reservas requiere cerrar B1: una vía canónica de consulta,
o una contención explícita de las superficies legacy.

### Lo que no se debe decir delante de un cliente

- que hay paridad con TIKR o Bloomberg
- que el P/E es TTM
- que la cobertura de ratios está completa
- que el screener publicado y la API v2 tienen el mismo respaldo que esto

Las cuatro están escritas en `CATALAXIA_PRODUCT_CONTRACT.md` §9 y en el guion
para que nadie las afirme por omisión.

---

### Anexo · verificación

```bash
python scripts/engine/ratio_api.py --ticker AAPL --ratio ev_sales --provenance
python scripts/engine/ratio_api.py --ticker YPFD --ratio pe        # regla EPS<=0
python scripts/engine/ratio_api.py --ticker CEPU --ratio ev_sales  # dato faltante
python scripts/engine/ratio_api.py --ticker AAPL --period 2025-09-27 --currency USD \
                                   --window FY --status CALCULADO  # 6 filtros
python scripts/engine/ratio_api.py --universo --provenance > CATALAXIA_SLICE_EXPORT.json
python scripts/engine/homologacion_slice.py                        # 13/13 · 25/25

docker exec catalaxia-db psql -U catalaxia -d catalaxia -c \
  "SELECT to_regclass('derived.ratio')"                            # NO EXISTE
grep -cE "derived\.|identity_v1|parsed\." api/main.py              # 0
```
