# Pipeline CNV-IR — EEFF oficiales de los BYMA-only (por pasos)

Baja los **estados contables oficiales** (formato CNV/FACPCE) de los **56 papeles
BYMA-only** desde el sitio de **Relación con Inversores** de cada empresa, los
parsea y carga a la base — con **menú interactivo** y **auto-validación contable**.

> **Importante:** corré esto **desde Argentina**. Varios IR geo-bloquean IPs de
> afuera. Desde Buenos Aires responden normalmente.

---

## Instalación (una vez)

```bash
# 1. Python 3.10+  (python.org)
# 2. librerías:
pip install requests pdfplumber pymupdf pandas yfinance

# 3. OCR (opcional, para los EEFF escaneados):
pip install pytesseract
#   + instalar Tesseract-OCR con idioma español:
#   Windows: https://github.com/UB-Mannheim/tesseract/wiki  (marcar "Spanish")
#   o, alternativa sin binario:  pip install easyocr
```

## Cómo correrlo

```bash
cd scripts/tickets/cnv_ir
python run.py            # menú interactivo: te pregunta TODO antes de bajar
```

El menú pregunta, **antes de descargar**:
1. **Qué empresas**: todas / un sector / un papel
2. **Tipo de presentación**: anual / trimestral / ambos
3. **Períodos**: solo el último / rango de años (desde-hasta)
4. **Tipo de PDF**: cualquiera / solo texto (rápido) / solo imagen (OCR)
5. **Cargar a la base**: sí / no

```bash
python run.py --rapido   # sin menú: todas, último, cualquier PDF, carga a BD
```

## Arquitectura por pasos (cada uno corre suelto)

```
run.py  →  orquesta los 5 pasos con la config del menú

paso1_descarga.py      descubre EEFF en el IR + descarga los que pasan el filtro → manifiesto
paso2_extraccion.py    abre cada PDF, detecta texto/imagen, extrae line items (texto u OCR)
paso3_validacion.py    identidades contables (Activo=Pasivo+PN). Marca OK / parcial
paso4_normalizacion.py rotula: ARS, NIC 29, fecha de re-expresión, period_end
paso5_publicacion.py   carga a cnv_estados (solo lo validado)
```

Correr un paso solo:
```bash
python paso1_descarga.py     # solo descarga (te pregunta config)
python paso3_validacion.py   # corre paso1+2+3
```

## Soporte (módulos base)

| Módulo | Qué hace |
|--------|----------|
| `catalogo_ir.py` | los 56 con **sector**, cierre fiscal y URLs de IR |
| `discovery.py` | encuentra el/los EEFF en el sitio de IR |
| `parser_eeff.py` | librería de etiquetas (ES, por tipo) + números argentinos + validación |
| `ocr.py` | OCR de escaneados (pytesseract/easyocr) |
| `config.py` | el menú interactivo + filtros |

## La auto-validación (clave)

Cada EEFF pasa el **checksum contable**: `Activo = Pasivo + Patrimonio`. **Solo se
carga lo que cierra (<1%).** Si no cuadra, queda `parcial` y NO se carga — nunca se
confía en data mal extraída. Así sabés, empresa por empresa, si quedó bien.

## Completar cobertura

- **URLs faltantes**: en `catalogo_ir.py`, los que tienen `[]` — agregá la URL del
  IR (la encontrás googleando "<empresa> relación con inversores estados contables").
- **PARCIAL**: si la identidad no cierra, mirá las etiquetas del PDF y agregá la
  variante en `parser_eeff.LIB` (ej. bancos: "Ingresos por intereses").
- **Escaneados**: instalá OCR.

## Salida → `cnv_estados`

```
ticker, cik, concepto, period_end, tipo (A/Q), valor, fecha_reexpresion,
fuente='cnv-ir', esquema=NIC 29
```
Cada dato con su fecha de re-expresión. Listo para reconstruir ratios oficiales
y, a futuro, re-normalizar por IPC para series largas.
