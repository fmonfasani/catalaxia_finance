# Pipeline CNV-IR — EEFF oficiales de los BYMA-only

Sistema completo para bajar los **estados contables oficiales** (formato CNV/FACPCE)
de los papeles **BYMA-only** (que NO están en EDGAR) desde el **sitio de Relación
con Inversores** de cada empresa, parsearlos y reconstruir ratios — con
**auto-validación por identidades contables**.

> **Por qué IR y no la CNV:** el portal de la CNV (aif.cnv.gov.ar) está
> geo-bloqueado fuera de Argentina. Pero las empresas publican los **mismos EEFF**
> en su web de inversores. Probado: Aluar → identidad **0.00%**, ratios completos.

---

## Componentes

| Módulo | Qué hace |
|--------|----------|
| `catalogo_ir.py` | **lista curada** ticker → URLs de IR + tipo de empresa (no se adivinan URLs) |
| `discovery.py` | baja la página de IR, encuentra el **EEFF más reciente** (sigue subpáginas, fallback bolsar) |
| `parser_eeff.py` | **librería de etiquetas** (variantes español por tipo) + números argentinos + validación + fallback OCR |
| `ocr.py` | OCR de EEFF escaneados (pytesseract/easyocr), con degradación elegante |
| `pipeline.py` | orquestador: discover → download → parse → **validar** → cargar a `cnv_estados` |

## La auto-validación (el checksum)

Cada EEFF se valida con las **identidades contables**:
```
Activo = Pasivo + Patrimonio Neto      (Aluar: 0.00% → extracción correcta)
Resultado Bruto = Ventas − Costo       (Aluar: 0.00%)
```
**El pipeline solo carga lo que cierra (~0%).** Si la identidad no cuadra, se marca
`PARCIAL` y NO se carga (no se confía en data mal extraída).

## Uso

```bash
cd scripts/tickets/cnv_ir
python pipeline.py                  # reporte de todo el catálogo (no carga)
python pipeline.py --cargar         # carga las que validan a cnv_estados
python pipeline.py ALUA CECO2       # puntual
python discovery.py                 # solo descubrir EEFF (qué IR responde)
python ocr.py archivo.pdf           # probar OCR de un escaneado
```

## Estado y cobertura (medido)

Probado end-to-end. Resultado por empresa (depende del entorno):

| Caso | Empresa ejemplo | Estado |
|------|-----------------|--------|
| ✅ texto + labels estándar | **ALUA** | OK — identidad 0%, 11 items, cargado |
| 🟡 texto, labels propios | CECO2 | PARCIAL — generalizar etiquetas |
| 🖼️ escaneado | SAMI | ESCANEADO — requiere OCR |
| 🔒 IR geo-bloqueado | LEDE, TRAN, CAPX… | SIN EEFF (desde IP no-AR) |

## ⚠️ Dos límites del entorno (no de la solución)

1. **OCR**: requiere `tesseract` (con idioma `spa`) o `easyocr` instalado. Sin eso,
   los escaneados quedan `ESCANEADO` (el módulo degrada elegante).
   ```bash
   pip install pytesseract     # + instalar Tesseract-OCR con paquete de español
   # o
   pip install easyocr
   ```
2. **IP argentina**: varios IR están geo-bloqueados fuera de AR. **Correr el
   pipeline desde una IP argentina** destraba la mayoría (`SIN EEFF` → encontrados).

→ Con OCR instalado + corrido desde AR, la cobertura sube fuerte. La parte difícil
(parseo + validación) ya funciona; el resto es entorno.

## Salida → tabla `cnv_estados`

```
ticker, cik, concepto, period_end, tipo, valor, fecha_reexpresion,
form='EEFF-IR', fuente='cnv-ir'
```
Cada dato con su **fecha de re-expresión** (NIC 29) → base para re-normalizar por
IPC. Ver `docs/screener/PIPELINE_CNV.md` para el diseño robusto general.

## Para extender la cobertura

1. **Completar `catalogo_ir.py`** con las URLs de IR que falten (las marcadas `[]`).
2. **Agregar variantes** a `parser_eeff.LIB` para los `PARCIAL` (mirar las etiquetas
   reales del PDF, ej. CECO2 usa "Ingresos de actividades ordinarias").
3. **Instalar OCR** para los escaneados.
4. **Correr desde AR** para los geo-bloqueados.
La identidad contable dice, empresa por empresa, si quedó bien (0%) o hay que revisar.
