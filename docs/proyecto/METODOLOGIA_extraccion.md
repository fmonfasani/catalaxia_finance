# Metodología de Extracción de Datos Financieros
### (la "E" del ETL — de la fuente pública a datos crudos inmutables y trazables)

> **Nota de honestidad (misma regla que predicamos).** La **E es en su mayoría infraestructura
> pre-existente** del repo (jobs de CNV, módulo SEC, run_update), no algo que construimos y
> testeamos juntos como la T. Este documento se basa en **leer los scripts reales** + lo que
> **verifiqué directamente** hoy (el mecanismo de la CNV, con test de control). Donde no verifiqué,
> lo digo. No hay endpoint ni mecanismo inventado.

---

## 1. Qué es la E (y por qué es tan importante como la T)

La E es **traer el dato crudo de la fuente pública de forma responsable, completa y trazable** —
sin transformarlo todavía. Es la capa **BRONZE** (inmutable). Si la E es frágil o poco trazable,
toda la validación de la T pierde valor: no podés certificar lo que no podés reconstruir desde el
origen.

**El principio que la ordena:** *descubrimiento barato, descarga respetuosa, crudo inmutable,
todo trazable.*

---

## 2. Las fuentes (verificadas)

| Fuente | Qué trae | Endpoint real (verificado) |
|---|---|---|
| **CNV — AIF2** | Estados contables argentinos (AIF, ARS, normas CNV/NIIF) | `cnv.gov.ar/SitioWeb/Empresas/AutoComplete` (universo) · `aif2.cnv.gov.ar/presentations/publicview/{guid}` (XBRL) |
| **SEC EDGAR** | Estados US + ADR (20-F, en ARS o USD, XBRL) | `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` (facts) · `data.sec.gov/submissions/CIK{cik}.json` (historial) |
| **Precios** | Cotizaciones (BYMA, ADR, US) | yfinance + IAMC + BYMA |
| **Referencia** | Ratios ADR (del 20-F), CEDEAR (Comafi) | archivos + `adr_ratios`, `cedear_ratios` |

**Verificado directamente hoy:** el mecanismo CNV `publicview/{guid}` → devuelve el XBRL completo
(estructura `<propiedad id="Nro/Rubro/Monto">` + `TipoBalance`, `FechaCierre`, `UnidadMedida`). Lo
probé con un test de control: bajé un estado que ya teníamos y vino idéntico (150 KB de XBRL).

---

## 3. El pipeline CNV — paso a paso, con fundamento

Es un flujo **discovery → download → clasificación offline → extracción**, diseñado para pegarle
lo mínimo posible a la fuente.

### D1 — Descubrimiento del universo  · `job1_universo`
Un endpoint `AutoComplete` devuelve **TODAS** las empresas registradas en la CNV en **1 sola
request** → `empresas_556.csv`.
**Fundamento:** discovery barato. No hay que adivinar el universo; la fuente lo lista.

### D2 — Descarga de páginas de empresa  · `job2_download`
Por cada empresa, **1 request** baja su página pública, que contiene —en un acordeón— **todos los
GUIDs** de esa empresa agrupados por tipo de formulario. Resume-safe (saltea lo ya bajado),
rate-limited (sleep configurable).
**Fundamento (API etiquette + eficiencia):** 1 request por empresa trae todo su universo de
presentaciones. Guardar el HTML permite clasificar **sin red**.

### D3 — Clasificación offline  · `job3_formtype`
Parsea los HTML ya bajados **sin red**: cada GUID hereda el último encabezado (nombre de
formulario) del acordeón → `guid_formtype.csv`.
**Fundamento (eficiencia demostrada):** reemplazó un approach de fuerza bruta que abría **79.772
publicview (~9 h)** por un parseo local de **segundos**. Menos requests = más respetuoso y más
rápido.

### D4 — Whitelists  · `job4_clasificar`
Clasifica los GUIDs por palabras clave del formulario → `whitelist_eeff.csv` (estados contables),
`whitelist_div.csv` (dividendos). **0 requests.**
**Fundamento:** separar QUÉ bajar (offline) de bajarlo. Solo se piden los documentos que importan.

### E — Extracción de estados  · `job5_v2_extract_eeff`
Por cada GUID de la whitelist EEFF, pide el `publicview` → obtiene el XBRL, **guarda el HTML crudo
en `eeff_html/{guid}.html` (nunca re-bajar)**, y persiste los datos.
**Fundamento (bronze inmutable):** el crudo se guarda tal cual, con su GUID. Cualquier dato
derivado se puede rastrear y re-procesar sin volver a la red. **Verificado:** con `fetch_dgce.py`
recuperé DGCE hoy — de 418 docids, 13 eran estados contables (405 no), confirmando que la
clasificación (D3/D4) es necesaria y que el mecanismo anda.

### D6/D7 — Dividendos y validación  · `job6`, `job7`
Extracción de dividendos (whitelist_div) y chequeos de consistencia.

---

## 4. El pipeline SEC EDGAR — paso a paso, con fundamento

Usa las **APIs oficiales** de la SEC (no scraping).

### Mapeo ticker → CIK  · `01_mapear_cik`
Mapea cada ticker a su CIK usando el archivo oficial `company_tickers.json` (cacheado). Los que no
matchean van a un CSV de **revisión manual** — **"NUNCA inventar CIK".**
**Fundamento (identidad + ética):** el CIK es la clave canónica en SEC. Y acá aparece el **mismo
principio que la T**: ante la duda, se marca para revisión, no se fabrica.

### Descarga de facts + precios  · `02_descargar_datos`
Baja `companyfacts/CIK{cik}.json` (todos los facts XBRL de la empresa, GAAP + fallback IFRS) y los
precios (yfinance). Resume-safe (1 JSON por CIK), errores logueados aparte.
**Fundamento (API etiquette):** la SEC **exige User-Agent** y pide no abusar de requests → se
cachea, se paginan, se respeta. El fallback `ifrs-full` es clave: **los ADR argentinos reportan en
IFRS/ARS** (lo verificamos: 11 de 13 en ARS).

### Detección de frescura  · `submissions` API + `run_update --quarterly`
`data.sec.gov/submissions/CIK{cik}.json` da el historial; se detecta si hay un `lastFiled` nuevo y
**solo se re-baja lo que cambió**.
**Fundamento:** actualización incremental — no se re-descarga todo, solo lo nuevo. Idempotente.

---

## 5. Precios y CCL

- **Diario** (`run_update --daily`): yfinance para ~571 tickers (precio, máx/mín 52s, market cap).
- **IAMC / BYMA**: cierres locales en ARS.
- **CCL** (contado con liqui): del bono **AL30 / AL30C** (definido en el contrato de datos; su
  implementación/verificación quedó pendiente — **lo marco honesto, no lo doy por hecho**).

---

## 6. Los fundamentos transversales de la E (por qué está bien diseñada)

| Principio | Cómo se aplica | Por qué importa (fundamento) |
|---|---|---|
| **Discovery barato** | AutoComplete (1 req) · company_tickers (1 archivo) · acordeón (1 req/empresa) | Minimiza requests → respetuoso con la fuente y rápido |
| **Clasificación offline** | job3/job4 parsean HTML local, 0 red | Testeable, reproducible, sin castigar la fuente |
| **Crudo inmutable** | HTML/JSON guardado por GUID/CIK, "nunca re-bajar" | Capa bronze → todo derivado es reconstruible y trazable |
| **Resume-safe / idempotente** | saltea lo ya bajado; 1 archivo por doc | Se puede cortar y retomar; determinista |
| **API etiquette** | User-Agent, rate-limit, cache | Cumplimiento de ToS + no te bloquean |
| **Nunca inventar** | CIK sin match → revisión manual; errores logueados | Misma ética que la T: marcar > fabricar |
| **Provenance / log** | `ingest_log` (url, http_status, sha256, bytes, ts) | Auditoría: quién, qué, cuándo, con qué hash |

---

## 7. Qué verifiqué vs qué es infraestructura existente (lo honesto)

| Componente | Estado de mi verificación |
|---|---|
| CNV `publicview → XBRL` | ✅ **Verificado hoy** (test de control + `fetch_dgce` funcionó) |
| CNV jobs 1–7 (flujo) | 📖 Leído en los scripts reales (docstrings claros); no re-ejecuté 1–4 |
| SEC endpoints (companyfacts/submissions) | ✅ Verificados en el código; los facts están en la base (4,6M filas) |
| SEC fetcher interno (User-Agent, ifrs fallback) | 📖 Leído en docstrings; no leí `backend/fetchers/sec_edgar.py` línea por línea |
| Precios yfinance/IAMC | 📖 Referenciados; `run_update --daily` documentado |
| CCL AL30/AL30C | ⚠️ **Diseñado, no verificado** que esté implementado — lo digo honesto |

---

## 8. Cómo suma la E al proceso vendible

La T vende **confianza en el dato**. La E vende **confianza en el ORIGEN del dato** — y juntas
cierran el círculo "crudo → certificado":

1. **Trazabilidad de punta a punta.** Cada número certificado se rastrea a un documento crudo
   (GUID/CIK) con hash y timestamp. Para un regulador o un due diligence, esto es oro.
2. **Ingesta respetuosa y legal.** APIs oficiales, User-Agent, rate-limit, sin scraping frágil.
   Vendible como *compliance-friendly*.
3. **Reproducibilidad desde el origen.** No solo la T es determinista; la E guarda el crudo
   inmutable, así que se puede reconstruir TODO desde la fuente.
4. **Multi-fuente desde la ingesta.** Traer SEC **y** CNV para la misma empresa es lo que después
   habilita la triangulación (la validación más fuerte). La E ya siembra la doble fuente.

---

## 9. Perspectivas que quizás no ves (el "pensá vos")

1. **La E es tu foso defensivo.** Cualquiera compra un feed; pocos arman un discovery barato +
   clasificación offline + crudo inmutable para dos fuentes distintas (una con inflación). El costo
   de replicar tu ingesta es tu barrera de entrada.
2. **El crudo inmutable = re-procesamiento gratis.** Cuando mejorás la T (como hicimos hoy 20
   veces), **no volvés a la red** — re-procesás el crudo guardado. Eso es velocidad de iteración y
   respeto por la fuente al mismo tiempo.
3. **La detección de frescura (submissions/lastFiled) es un producto SaaS.** "Te avisamos y
   actualizamos cuando una empresa presenta algo nuevo, y solo eso." Es un *feed incremental
   certificado*.
4. **El log de ingesta con hash es evidencia forense.** Si un cliente cuestiona un dato, mostrás
   la URL, el hash y el timestamp de cuándo lo bajaste. Eso es defendible legalmente.
5. **La misma ética en E y en T ("nunca inventar") es una marca.** Un CIK sin match va a revisión,
   no a un valor adivinado. Consistencia entre capas = confianza del cliente.
6. **La E es agnóstica de mercado.** El patrón (discovery → download → classify → extract, con
   crudo inmutable y log) sirve para SEC, CNV, ESMA, B3. Documentado así, es una **plantilla de
   ingesta replicable** que se vende como servicio.

---

## 10. El cuadro completo: E + T

```
   FUENTE PÚBLICA
   (CNV AIF2 · SEC EDGAR · yfinance)
        │
        ▼  E — ingesta responsable, crudo inmutable, trazable  ← este documento
   BRONZE (crudo, con GUID/CIK + hash + timestamp)
        │
        ▼  T — normalización + validación multi-fuente          ← METODOLOGIA_validacion.md
   SILVER + GOLD (fundamentals CERTIFICADOS, puntaje por dato)
        │
        ▼
   PRODUCTO (screener, feed, API, sello de calidad)
```

> **La frase que cierra las dos:** "Traemos el dato de la fuente oficial de forma trazable, y lo
> validamos hasta poder probar que es correcto — o marcarte honestamente que no. Del documento
> crudo al número certificado, con el recibo de cada paso."
