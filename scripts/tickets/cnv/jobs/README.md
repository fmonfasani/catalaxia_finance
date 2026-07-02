# CNV · Jobs de ETL segmentado (la "mina 556")

Pipeline para descubrir y extraer los estados contables y dividendos de **TODAS**
las entidades registradas en la CNV (~556: cotizantes + ADR + emisoras de ON que
no cotizan equity). Diseñado en **jobs chicos, secuenciales y resume-safe**, con
separación clara entre *Discovery* (barato, cacheable, offline) y *Extract*
(rate-limited contra CNV).

> **Para el agente que ejecuta:** corré los jobs **en orden**. Los jobs 1–4 son
> baratos/offline. Los jobs 5 y 6 le pegan a la CNV: usá `--rango` para partirlos
> en varias corridas y **no corras dos instancias en paralelo contra el mismo
> host** (aif2.cnv.gov.ar). Ninguno de estos scripts fue ejecutado todavía.

## Principio de diseño

| | Discovery | Extract |
|---|---|---|
| Qué | Descubre qué presentaciones existen | Baja el contenido de cada una |
| Costo | 1 request por empresa (o 0, offline) | 1 request por presentación |
| Cacheable | Sí (se guarda el HTML / CSV) | Parcial (resume-safe por log) |
| Paralelizable | Entre fuentes, no dentro | Segmentable por `--rango` |

La clave de eficiencia: la **company page** de cada empresa (1 request) ya trae
**todos** sus GUIDs agrupados por tipo de formulario en un acordeón. Parsear eso
**offline** (JOB 3) reemplaza abrir 79.772 `publicview` uno por uno (~9 h) por
segundos de parseo local.

## Orden de ejecución

```
JOB 1 · D1  job1_universo.py      AutoComplete → datos/empresas_556.csv          1 req
JOB 2 · D2  job2_download.py      GET x CUIT  → datos/html_descargados/*.html    ~556 req (rate-limited, --rango)
JOB 3 · D3  job3_formtype.py      OFFLINE: HTMLs → datos/guid_formtype.csv        0 req   ← el atajo
JOB 4 · D4  job4_clasificar.py    OFFLINE: cruce → whitelist_eeff/div + maestra   0 req
JOB 5 · E   job5_extract_eeff.py  whitelist_eeff → publicview → cnv_estados       rate-limited, --rango
JOB 6 · E   job6_extract_div.py   whitelist_div  → publicview → cnv_dividendos    rate-limited, --rango
```

### Comandos

```bash
cd scripts/tickets/cnv/jobs

python job1_universo.py
python job2_download.py                      # o por tramos: --rango 0 150
python job3_formtype.py --debug
python job4_clasificar.py

# Extract segmentado (ejemplo en tramos de 500):
python job5_extract_eeff.py --rango 0 500
python job5_extract_eeff.py --rango 500 1000
python job6_extract_div.py  --solo dividendo --rango 0 300
```

## Diagnóstico obligatorio antes de escalar (pedido del dueño)

Antes de lanzar el barrido completo, **validar el pipeline con UNA empresa que NO
cotice en bolsa** (solo emite ON), para confirmar que el acordeón se parsea bien y
la extracción cierra la identidad contable. Sugerido: **360 Energy Solar SA**
(cuit `30711204055`), ya verificada manualmente (276 GUIDs, 34 secciones, tiene
"Estados Contables", no tiene "Pago de Dividendos"). Flujo de diagnóstico:

```bash
python job1_universo.py
python job2_download.py --rango 0 5           # baja unas pocas company pages
python job3_formtype.py --debug               # ver acordeón parseado
python job4_clasificar.py                     # ver whitelists
python job5_extract_eeff.py --rango 0 20      # validar identidad (identidad>5% debe ser ~0)
```

Si la identidad contable cierra (`identidad>5% ≈ 0`) y los ratios de la CNV
aparecen, recién ahí escalar D2/D3/D4 al universo completo y correr E-EEFF/E-DIV
por tramos.

## Salidas

| Archivo / tabla | Job | Qué es |
|---|---|---|
| `datos/empresas_556.csv` | 1 | universo (ticker, empresa, cuit, url) |
| `datos/html_descargados/*.html` | 2 | company pages crudas (gitignore) |
| `datos/guid_formtype.csv` | 3 | GUID → formulario (offline) |
| `datos/whitelist_eeff.csv` | 4 | GUIDs de estados contables |
| `datos/whitelist_div.csv` | 4 | GUIDs de dividendos/HR/actas |
| `datos/tabla_maestra.csv` | 4 | 1 fila por empresa (conteos + cotiza?) |
| `data/screener.db :: cnv_estados` | 5 | conceptos + ratios CNV por período |
| `data/screener.db :: cnv_dividendos` | 6 | dividendos/HR/actas (candidatos + HTML crudo) |

## Contratos entre jobs (para no romper nada)

- **Fuentes verificadas**: AutoComplete `…/SitioWeb/Empresas/AutoComplete`;
  company page `…/SitioWeb/Empresas/Empresa/{CUIT}`; presentación
  `https://aif2.cnv.gov.ar/presentations/publicview/{GUID}` (aif2 **no** está
  geo-bloqueado; `aif.cnv.gov.ar` sí).
- **Clasificación por nombre** (JOB 4): la company page muestra el *nombre* del
  formulario, no el `formTypeId`. Se clasifica por palabras clave. Referencia de
  IDs conocidos: EEFF `{147,349,487,142,488,1001,1002}`; dividendos/HR/actas
  `{339,244,1007,198,334,1006}`.
- **Parser de EEFF** (JOB 5): idéntico al validado en
  `../scripts/extract_aif2_masivo.py` (identidad 0.000 % en Ledesma). Códigos de
  7 dígitos (`1999999`=Activo, `3049999`=NetIncome, `3021800`=RECPAM…) + ratios
  pre-calculados (`8000009`=ROE…).
- **Resume-safe**: JOB 2 saltea HTML ya bajados; JOB 5/6 registran GUIDs hechos en
  `data/log_job5_done.txt` / `log_job6_done.txt`. Borrá el log para reprocesar.
- **Idempotencia DB**: `cnv_estados` usa `INSERT OR IGNORE` (PK cik+concepto+
  period_end+reexpresión); `cnv_dividendos` usa `INSERT OR REPLACE` por GUID.

## Notas de rate limit / paralelismo

- CNV responde 2–5 s por request. El `--sleep` default (0.3 s extract, 1 s
  download) es conservador; ajustar con cuidado.
- **Tope por corrida (`--max N`)** en los jobs 2, 5 y 6: corta tras `N` requests
  reales (no cuenta los que saltea por resume). Como son resume-safe, volvés a
  correr y sigue donde quedó. Sirve para acotar cada sesión sin pasarte de rosca.
- **Límites recomendados** (a ~4 s efectivos por request):

  | Job | tramo `--rango` | `--max` | duración aprox |
  |---|---|---|---|
  | 2 · download | 150 | 200 | ~10–13 min |
  | 5 · EEFF | 500 | 800 | ~35–55 min |
  | 6 · DIV | 300 | 800 | ~35–55 min |

  Regla práctica: no más de ~800 requests por corrida y una sola corrida a la vez
  contra aif2. Entre corridas, dejá un respiro (1–2 min).
- Para paralelizar de verdad: partí por `--rango` **disjuntos** y corré cada
  tramo en una corrida distinta. No abras varias instancias simultáneas contra
  aif2 (misma IP → riesgo de bloqueo).
- `data/html_descargados/` y `eeff/div_html/` son crudos → deben quedar en
  `.gitignore` (solo se sube lo procesado: CSVs de datos y la DB).
```
