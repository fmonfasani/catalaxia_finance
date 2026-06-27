# Pipeline CNV — estados contables argentinos (trimestral)

> Extracción automática de **estados contables argentinos** (formato CNV/FACPCE,
> NIC 29) para tener el **dato trimestral** que el XBRL de EDGAR no provee, con
> cada dato anclado a su **fecha de re-expresión** (la pieza clave para resolver
> la inflación contable).

**Estado:** piloto funcionando. **9/16 ADR** cargadas con trimestral en la tabla
`cnv_estados`. Junio 2026.

---

## 1. El problema que resuelve

Las argentinas reportan bajo **NIC 29** (hiperinflación): cada estado re-expresa
los importes a **moneda constante de la fecha de reporte**. Consecuencias medidas
(ver `BITACORA_Y_DECISIONES.md` / análisis de la sesión):

- El XBRL de EDGAR **solo tiene el anual** para los ADR argentinos clásicos
  (filean 6-K interino **sin XBRL**) → no hay trimestral estructurado.
- Yahoo `.BA` tiene trimestral pero **mezcla vintages** de re-expresión → el
  **penúltimo año** diverge ~32% (el último año sí es confiable, ~1%).
- La CNV (fuente oficial, todos los períodos) está **geo-bloqueada** fuera de AR.

**La vía:** los 6-K de EDGAR **adjuntan los estados contables** (formato CNV, en
inglés) como exhibit **HTML parseable** (no imágenes — los números están en
texto). EDGAR es accesible. Eso da el trimestral oficial, NIC 29 coherente por
filing, sin destrabar la CNV.

## 2. El principio de diseño (lo importante)

```
Dato argentino = (concepto, period_end, valor, FECHA_DE_RE-EXPRESION)
                  nunca un escalar suelto
```

Cada line item se guarda con su `fecha_reexpresion` (= `filed` del 6-K). El mismo
`period_end` desde filings distintos = **filas distintas** (se preserva el
"blanco móvil" de NIC 29). Eso permite, después, re-normalizar toda la serie a una
base común con el índice de inflación.

## 3. Arquitectura (`scripts/tickets/cnv_auto.py`)

```
descubrir(cik)        índice de 6-K/20-F (submissions) -> exhibit de estados (top-3 por tamaño)
fetch_texto(url)      HTML->texto o PDF->texto (pdfplumber), cache en data/raw/cnv/
detectar_escala(txt)  miles / millones -> multiplicador
detectar_periodo(txt) fecha de cierre (la mas reciente valida) + tipo Q/A
parsear(txt)          line items canonicos (variantes de etiqueta por concepto)
validar(d)            IDENTIDADES CONTABLES: Gross=Rev+COGS ; Activo=Pasivo+PN
cargar_a_base(...)    -> tabla cnv_estados (con fecha_reexpresion)
```

**Auto-validación:** las identidades contables confirman que se extrajeron los
números correctos sin conocer la respuesta de antemano (LOMA: Gross 0.00%,
Activo=Pas+PN 0.07%). Cross-check contra Yahoo Q1-2026: Revenue 0.0%, NetIncome
0.0% (Yahoo usa NI total; el 6-K, atribuible — difieren por el minoritario).

### Uso
```bash
python scripts/tickets/cnv_auto.py LOMA PAM CEPU      # prueba puntual (solo imprime)
python scripts/tickets/cnv_auto.py --todos            # las 16 ADR + carga a cnv_estados
```

### Tabla `cnv_estados`
```
ticker, cik, concepto, period_end, tipo (Q/A), valor, valor_comparativo,
fecha_reexpresion, form, escala, accn, fuente='cnv-6k'
PK (cik, concepto, period_end, fecha_reexpresion)
```

## 4. Estado de cobertura (16 ADR)

| Estado | Empresas | Nota |
|--------|----------|------|
| ✅ Cargadas | LOMA, PAM, CEPU, CRESY, TEO, EDN, GGAL, BMA, SUPV (9) | formato estándar; bancos con menos conceptos (sin Rev/COGS) |
| 🔧 Sin estados en 6-K HTML | YPF, BBAR, IRS | interinos solo press-release / van en 20-F → parser de 20-F o CNV directa |
| 🔧 Formato propio | TGS, BIOX | balance sin línea "Total assets" / USD distinto → handler específico |
| ➖ No aplica | MELI | filea 10-Q (us-gaap) → ya está en el XBRL |

## 5. Pendiente

1. **Handlers de los 7 holdouts** (parser de 20-F para YPF; etiquetas TGS/BIOX;
   fecha de cierre de bancos GGAL/BMA).
2. **Historia**: subir `max_filings` → varios trimestres por empresa → la serie
   con sus re-expresiones.
3. **Capa de normalización IPC** (INDEC/FACPCE) → re-expresar todo a base común.
4. **BYMA-only (~56)**: mismo parser sobre PDFs de CNV (desde IP argentina).

## 6. Scripts relacionados

- `extraer_estados_6k.py` — piloto (1 empresa, proof of concept con validación).
- `cnv_auto.py` — el pipeline automático (este doc).
- `cargar_argentina_cnv.py` — loader manual (los ~20 números a mano → motor de ratios).
- `cargar_byma_yfinance.py` — fundamentales BYMA vía yfinance (precio + último año confiable).
