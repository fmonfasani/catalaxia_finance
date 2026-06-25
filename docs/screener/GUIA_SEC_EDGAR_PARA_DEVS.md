# Guía de SEC EDGAR para Desarrolladores (sin saber nada de finanzas)

> **Para quién es esta guía:** desarrolladores que van a trabajar con datos financieros
> pero **nunca estudiaron finanzas**. Empieza desde cero absoluto. No asume que sabés
> qué es una acción, un balance, ni qué significa "ROE". Si ya sabés finanzas, saltá
> directo a la sección 6 (la parte técnica de la API).

**Última actualización:** 24 de junio de 2026

---

## Índice

1. [El problema que estamos resolviendo](#1-el-problema-que-estamos-resolviendo)
2. [Conceptos de bolsa desde cero](#2-conceptos-de-bolsa-desde-cero)
3. [Qué es SEC EDGAR](#3-qué-es-sec-edgar)
4. [Los 3 estados financieros (el corazón de todo)](#4-los-3-estados-financieros)
5. [Los ratios financieros explicados como si tuvieras 5 años](#5-los-ratios-financieros)
6. [La API de SEC EDGAR (parte técnica)](#6-la-api-de-sec-edgar-parte-técnica)
7. [XBRL: cómo vienen los datos](#7-xbrl-cómo-vienen-los-datos)
8. [Empresas USA vs extranjeras (us-gaap vs IFRS)](#8-empresas-usa-vs-extranjeras)
9. [Tabla: qué concepto usar para cada dato](#9-tabla-qué-concepto-usar-para-cada-dato)
10. [Código de ejemplo paso a paso](#10-código-de-ejemplo-paso-a-paso)
11. [Errores comunes y cómo evitarlos](#11-errores-comunes)
12. [Glosario](#12-glosario)
13. [Sistema para replicar el Excel de Seguimiento (dashboard)](#13-sistema-para-replicar-el-excel-de-seguimiento-dashboard)

---

## 1. El problema que estamos resolviendo

Estamos construyendo un **screener financiero**: una tabla con cientos de empresas
donde, para cada una, mostramos números que ayudan a decidir si es "buena" o "cara"
para invertir (su ganancia, su deuda, su rentabilidad, etc.).

Para llenar esa tabla necesitamos **datos financieros confiables** de cada empresa.
¿De dónde los sacamos? Hay dos caminos:

- ❌ **Scraping de webs** (Investing.com, Yahoo): frágil, se rompe, te bloquean, y los
  números a veces están mal o calculados de forma rara. **Ya lo intentamos y falló**
  (ver carpeta `failed_investing_scraping/`).
- ✅ **SEC EDGAR**: la base de datos **oficial** del gobierno de EE.UU. donde TODAS las
  empresas que cotizan en bolsa están **obligadas por ley** a publicar sus números
  reales. Gratis, con API, sin trucos. **Este es el camino correcto.**

---

## 2. Conceptos de bolsa desde cero

Antes de tocar código, necesitás entender 6 palabras. Sin esto, el resto no tiene sentido.

### 2.1 Acción (stock / share)
Una empresa se divide en pedacitos llamados **acciones**. Si comprás una acción de Apple,
sos dueño de una partecita microscópica de Apple. Si Apple tiene 15.000 millones de
acciones y vos tenés 1, sos dueño de 1/15.000.000.000 de la empresa.

### 2.2 Bolsa (stock exchange)
Es el "mercado" donde se compran y venden acciones. Las grandes son **NYSE** y **NASDAQ**
(ambas en EE.UU.). En Argentina está **BYMA**.

### 2.3 Ticker
El "nombre corto" de una empresa en la bolsa. Apple = `AAPL`, Microsoft = `MSFT`,
Coca-Cola = `KO`. Es como un username único.

### 2.4 CEDEAR
Un CEDEAR es un "certificado" que se compra en Argentina (en pesos) pero representa una
acción de una empresa extranjera (normalmente de EE.UU.). Te permite invertir en Apple
desde Argentina sin abrir cuenta en EE.UU. **Para nosotros, un CEDEAR de Apple = la acción
de Apple** a efectos de los datos financieros (los números de la empresa son los mismos).

### 2.5 ADR
Un ADR es lo inverso: una empresa **NO estadounidense** (ej. una brasilera, una taiwanesa)
que quiere cotizar en la bolsa de EE.UU. lo hace a través de un ADR. Ejemplos:
- `TSM` = Taiwan Semiconductor (Taiwán)
- `PBR` = Petrobras (Brasil)
- `MELI` = MercadoLibre (Argentina)

**Dato clave para más adelante:** como los ADRs son empresas extranjeras, reportan sus
números de forma un poco distinta a las empresas USA (ver sección 8).

### 2.6 Precio vs. datos financieros (¡no confundir!)
- **Precio** = cuánto cuesta UNA acción ahora mismo en la bolsa. Cambia cada segundo.
  Esto **NO está en EDGAR**. Lo sacamos de Yahoo Finance (yfinance).
- **Datos financieros** = cuánto vendió la empresa, cuánto ganó, cuánto debe. Cambia cada
  3 meses (cuando la empresa publica resultados). **Esto SÍ está en EDGAR.**

> 🧠 Regla mental: **EDGAR = los números de la empresa. yfinance = el precio de la acción.**

---

## 3. Qué es SEC EDGAR

### 3.1 La SEC
La **SEC** (Securities and Exchange Commission) es el organismo del gobierno de EE.UU. que
regula la bolsa. Su trabajo es proteger a los inversores. Una de sus reglas: toda empresa
que cotiza debe publicar sus números **de forma pública y honesta**, cada 3 meses.

### 3.2 EDGAR
**EDGAR** es el sistema online donde la SEC guarda y publica todos esos reportes. Es una
base de datos gigante, pública y gratuita. Cada vez que Apple publica sus resultados, ese
documento queda en EDGAR para siempre, accesible para cualquiera.

### 3.3 Los "formularios" (forms)
Las empresas publican distintos tipos de documentos. Los que nos importan:

| Form | Qué es | Cada cuánto | Quién lo usa |
|------|--------|-------------|--------------|
| **10-K** | Reporte **anual** completo | 1 vez al año | Empresas USA |
| **10-Q** | Reporte **trimestral** (cada 3 meses) | 3 veces al año* | Empresas USA |
| **20-F** | Reporte **anual** de empresa extranjera | 1 vez al año | ADRs extranjeros |
| **6-K** | Reporte interino de empresa extranjera | Variable | ADRs extranjeros |

*El 4° trimestre va dentro del 10-K anual, por eso son 3 trimestrales + 1 anual.

> 💡 Cuando veas `"form": "10-K"` en los datos, pensá "esto es el número del **año
> completo**". Cuando veas `"form": "10-Q"`, pensá "esto es de **un trimestre** (3 meses)".

---

## 4. Los 3 estados financieros

Toda empresa reporta su salud con **3 documentos**. Entenderlos es entender el 90% de las
finanzas. Usemos una analogía: **una empresa es como una persona con un sueldo.**

### 4.1 Estado de Resultados (Income Statement)
**Responde: ¿cuánto ganó o perdió la empresa en un período?**

Es como tu recibo de sueldo del mes. De arriba hacia abajo:

```
  Revenue (Ingresos / Ventas)      ← cuánta plata entró por vender
- Costos                            ← cuánto costó producir lo que vendiste
─────────────────────────────
= Operating Income (Ganancia operativa)  ← lo que ganás de tu negocio principal
- Impuestos, intereses, etc.
─────────────────────────────
= Net Income (Ganancia Neta)       ← lo que REALMENTE te queda al final
```

- **Revenue** (ingresos/ventas): toda la plata que entró por vender productos/servicios.
  También llamado "facturación" o "top line" (la línea de arriba).
- **Net Income** (ganancia neta): lo que queda **después de pagar TODO** (costos,
  impuestos, intereses). También llamado "bottom line" (la línea de abajo). Es **el número
  más importante**: si es positivo la empresa ganó plata, si es negativo perdió.

> Analogía: Revenue = tu sueldo bruto. Net Income = lo que te queda después de pagar
> alquiler, comida, impuestos y deudas.

### 4.2 Balance General (Balance Sheet)
**Responde: ¿qué tiene y qué debe la empresa en este momento exacto?**

Es una **foto** (no un período). Tiene 3 partes y siempre se cumple esta ecuación:

```
  Assets (Activos)  =  Liabilities (Pasivos)  +  Equity (Patrimonio)
  Lo que tenés      =  Lo que debés           +  Lo que es tuyo de verdad
```

- **Assets** (activos): todo lo que la empresa **posee** (efectivo, fábricas, inventario,
  máquinas).
- **Liabilities** (pasivos): todo lo que la empresa **debe** (préstamos, deudas a
  proveedores).
- **Equity** (patrimonio / stockholders equity): lo que queda para los dueños si vendés
  todo y pagás todas las deudas. **Activos − Pasivos = Patrimonio.**

> Analogía: si tenés una casa de $100.000 (activo) con una hipoteca de $70.000 (pasivo),
> tu patrimonio real es $30.000 (equity).

- **Debt** (deuda): la parte de los pasivos que son préstamos con interés. Importante para
  saber si la empresa está "endeudada".

### 4.3 Estado de Flujo de Efectivo (Cash Flow Statement)
**Responde: ¿cuánta plata REAL entró y salió?**

Existe porque la "ganancia" (Net Income) usa trucos contables y no siempre refleja la
plata que de verdad se movió. El cash flow muestra el efectivo real.

- **Operating Cash Flow** (flujo operativo): la plata real generada por el negocio.
- **CapEx** (Capital Expenditures): plata gastada en cosas grandes y duraderas (fábricas,
  máquinas, equipos).
- **Free Cash Flow (FCF)**: `Operating Cash Flow − CapEx`. Es la plata que **sobra de
  verdad** después de mantener el negocio funcionando. Muy valorada: significa que la
  empresa genera efectivo libre que puede repartir o reinvertir.

---

## 5. Los ratios financieros

Un **ratio** es simplemente una división entre dos números financieros. Sirve para
**comparar empresas de distinto tamaño**. (No podés comparar la ganancia de Apple con la
de una panadería en números absolutos, pero sí podés comparar sus *porcentajes*.)

Estos son los ratios del screener, explicados de la forma más simple posible:

### 5.1 EPS (Earnings Per Share / Ganancia por Acción)
```
EPS = Net Income / Número de acciones
```
**Qué dice:** cuánta ganancia le toca a cada acción.
**Ejemplo:** si la empresa ganó $1.000 millones y tiene 100 millones de acciones,
EPS = $10. Cada acción "generó" $10 de ganancia.

### 5.2 PER (Price/Earnings o P/E / Precio-Ganancia)
```
PER = Precio de la acción / EPS
```
**Qué dice:** cuántos años de ganancias estás pagando al comprar la acción. Es el ratio
estrella para saber si una acción está **cara o barata**.
**Ejemplo:** si la acción vale $100 y el EPS es $10, PER = 10. Significa "pagás 10 veces
la ganancia anual". Un PER bajo (ej. 8) suele ser "barato"; uno alto (ej. 40) "caro".
**Ojo:** necesita el **precio** (de yfinance) → es el único ratio que combina EDGAR + yfinance.

### 5.3 Margen Neto (Net Margin)
```
Margen Neto = Net Income / Revenue
```
**Qué dice:** de cada $100 que vendió, cuántos le quedaron de ganancia. Mide
**eficiencia/rentabilidad**.
**Ejemplo:** margen de 0,25 (25%) = de cada $100 vendidos, $25 son ganancia pura. Apple
tiene márgenes altos; un supermercado, bajos.

### 5.4 ROE (Return on Equity / Retorno sobre Patrimonio)
```
ROE = Net Income / Equity
```
**Qué dice:** qué tan bien usa la empresa la plata de los dueños para generar ganancias.
**Ejemplo:** ROE de 0,20 (20%) = por cada $100 de patrimonio, genera $20 de ganancia al
año. Cuanto más alto, mejor (la empresa "rinde" más).

### 5.5 Deuda/Equity (Debt to Equity)
```
Deuda/Equity = Deuda total / Equity
```
**Qué dice:** cuánto debe la empresa comparado con lo que es de los dueños. Mide
**riesgo**.
**Ejemplo:** ratio de 2 = debe el doble de su patrimonio (riesgoso). Ratio de 0,3 = debe
poco (conservador).

### 5.6 EBITDA y Deuda/EBITDA
**EBITDA** = ganancia antes de intereses, impuestos, depreciación y amortización. Es una
forma de medir la ganancia "operativa pura" del negocio.
```
EBITDA = Operating Income + Depreciación y Amortización
Deuda/EBITDA = Deuda total / EBITDA
```
**Qué dice Deuda/EBITDA:** cuántos años de ganancia operativa necesitaría la empresa para
pagar toda su deuda. Menos de 3 suele ser sano; más de 5, preocupante.

### 5.7 FCF (Free Cash Flow)
```
FCF = Operating Cash Flow − CapEx
```
**Qué dice:** la plata libre real que genera. (Explicado en 4.3.)

### 5.8 Payout (Dividend Payout Ratio)
```
Payout = Dividendos pagados / Net Income
```
**Qué dice:** qué porcentaje de la ganancia reparte a los accionistas como **dividendos**
(en vez de reinvertirla). Un dividendo es plata que la empresa te paga por ser accionista.
**Ejemplo:** payout de 0,40 (40%) = reparte el 40% de lo que gana, reinvierte el 60%.

### 5.9 Crecimiento de EPS a 5 años
```
Cuánto creció el EPS comparando el de hoy con el de hace 5 años.
```
**Qué dice:** si la empresa está ganando cada vez más (creciendo) o estancada.
**Nota técnica:** este es el más difícil de calcular porque necesitás datos de **5 años
atrás** (5 reportes anuales 10-K históricos), no solo el último.

---

## 6. La API de SEC EDGAR (parte técnica)

Ahora la parte de código. EDGAR ofrece **APIs REST públicas y gratis**, sin API key.
Devuelven JSON.

### 6.1 Las 4 APIs

| API | URL | Para qué sirve |
|-----|-----|----------------|
| **submissions** | `https://data.sec.gov/submissions/CIK##########.json` | Metadata: nombre, tickers, historial. **NO trae números financieros.** |
| **companyconcept** | `https://data.sec.gov/api/xbrl/companyconcept/CIK##########/us-gaap/{Concepto}.json` | UN concepto (ej. NetIncomeLoss) de UNA empresa. Liviano (~50 KB). |
| **companyfacts** | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | **TODOS** los números de UNA empresa en una sola llamada. **El que más usamos.** |
| **frames** | `https://data.sec.gov/api/xbrl/frames/us-gaap/{Concepto}/USD/CY####Q#.json` | UN concepto de TODAS las empresas para un período. Para comparar el universo. |

### 6.2 ⚠️ DOS REGLAS QUE NO PODÉS ROMPER

Estos son los dos errores que hicieron fracasar todos los intentos anteriores. **Leelos
dos veces.**

#### Regla 1: User-Agent OBLIGATORIO con tu nombre y email

La SEC **rechaza con HTTP 403** cualquier request que no declare quién sos. No alcanza con
`Mozilla/5.0` ni `python-requests`. Tenés que mandar tu nombre real y un email:

```python
headers = {
    "User-Agent": "Tu Nombre tu-email@dominio.com",
    "Accept-Encoding": "gzip, deflate",
}
```

**Evidencia real (probado el 24-jun-2026):**
```
User-Agent "Mozilla/5.0"                     → HTTP 403 (BLOQUEADO)
User-Agent "python-requests/2.31"            → HTTP 403 (BLOQUEADO)
User-Agent "Federico Monfasani fede@mail.com" → HTTP 200 (FUNCIONA ✓)
```

> Si ves un **403**, el 99% de las veces es esto. No es que "te bloquearon la IP", no es
> CloudFlare. Es el User-Agent.

#### Regla 2: usá el endpoint correcto para los números

- ❌ `/submissions/` → solo metadata. Si lo usás, el campo `facts` viene **vacío**.
- ✅ `/api/xbrl/companyfacts/` → acá están los números financieros.

> Este fue el otro error del intento anterior: el JSON descargaba bien (200 OK) pero
> estaba vacío de finanzas, porque era el endpoint equivocado.

### 6.3 Rate limit: 10 requests por segundo

La SEC permite **hasta 10 requests por segundo**. Es mucho. Para no acercarnos al límite,
metemos un `time.sleep(0.15)` entre llamadas (≈ 6 req/seg). Con eso, descargar 212
empresas tarda ~45 segundos.

> Mito a olvidar: NO hace falta esperar "5 segundos entre requests". Eso es lentísimo e
> innecesario. El problema nunca fue la velocidad, fue el User-Agent (Regla 1).

### 6.4 El CIK (cómo encontrar una empresa)

La API no busca por ticker (`AAPL`), busca por **CIK** (un número de ID que la SEC le da a
cada empresa). Apple = CIK `320193`.

Para traducir ticker → CIK, la SEC publica un archivo con las ~10.400 empresas:
```
https://www.sec.gov/files/company_tickers.json
```
Lo descargás **una sola vez**, armás un diccionario `{ticker: cik}`, y listo.

**Importante:** el CIK tiene que ir con **10 dígitos, rellenando con ceros a la izquierda**:
`320193` → `0000320193`. En Python: `str(cik).zfill(10)`.

---

## 7. XBRL: cómo vienen los datos

Los datos financieros vienen en formato **XBRL** (un estándar internacional). En la
práctica, para vos es **JSON anidado**. Cada número financiero ("fact") se ve así:

```json
{
  "start": "2024-09-29",   // inicio del período (solo en cosas que son "flujo")
  "end":   "2025-09-27",   // fin del período / fecha de la foto
  "val":   112010000000,   // EL VALOR (acá: $112 mil millones)
  "accn":  "0000320193-25-...",  // ID del reporte de donde salió
  "fy":    2025,           // año fiscal
  "fp":    "FY",           // período fiscal: FY=año, Q1/Q2/Q3=trimestre
  "form":  "10-K",         // tipo de formulario (10-K=anual)
  "filed": "2025-10-31",   // cuándo se publicó
  "frame": "CY2025"        // a qué período calendario lo asigna la SEC
}
```

### 7.1 "Flujo" vs "Foto" (clave para no equivocarse)

- **Flujo** (revenue, ganancia, cash flow): tiene `start` Y `end`. Mide algo que pasó
  *durante* un período. Ej: "vendió $X **entre** enero y marzo".
- **Foto / instantáneo** (assets, equity, deuda): tiene **solo `end`**. Es el valor *en un
  momento exacto*. Ej: "tenía $X de deuda **al** 31 de diciembre".

### 7.2 Cómo distinguir el dato ANUAL del TRIMESTRAL

Un mismo concepto (ej. `NetIncomeLoss`) trae **muchos** registros: anuales y trimestrales,
de varios años. Para quedarte con el **anual más reciente**:

```python
anuales = [r for r in registros if r["form"] == "10-K"]   # solo anuales
mas_reciente = max(anuales, key=lambda r: r["end"])        # el de fecha más nueva
```

> ⚠️ Error típico: tomar `registros[0]` o `registros[-1]` asumiendo que están ordenados.
> **No confíes en el orden.** Filtrá por `form` y elegí por fecha con `max(...)`.

### 7.3 El "TTM" (Trailing Twelve Months)

Muchos sitios muestran datos "TTM" = los últimos 12 meses móviles. EDGAR **no te lo da
masticado**. Para el screener, lo más simple es usar **el último año fiscal (10-K)**. Es
suficiente y es lo que muestran la mayoría de los agregadores. (El TTM exacto sumando 4
trimestres es más preciso pero más complejo; dejalo para una v2.)

---

## 8. Empresas USA vs extranjeras

**Esto es crítico y casi nadie lo sabe la primera vez.** No todas las empresas usan el
mismo "idioma" de datos.

| | Empresas USA (CEDEARs) | Empresas extranjeras (ADRs) |
|---|---|---|
| **Taxonomía** | `us-gaap` | `ifrs-full` |
| **Form anual** | `10-K` | `20-F` |
| **Ejemplos** | AAPL, MSFT, KO, JNJ, WMT | TSM, PBR, VALE, BBVA, SAP, BABA |

- **us-gaap** = las normas contables de EE.UU.
- **IFRS** = las normas contables internacionales (las usan empresas de fuera de EE.UU.).

**Por qué te importa:** los conceptos tienen **nombres distintos** en cada taxonomía. Si
buscás `NetIncomeLoss` (nombre us-gaap) en una empresa que usa IFRS, **no lo vas a
encontrar** → vas a creer que "no hay datos", cuando en realidad están bajo otro nombre
(`ProfitLoss`).

**Evidencia real (TSM, Taiwan Semiconductor):**
```
Taxonomías: dei, ifrs-full, srt   ← NO tiene us-gaap
Forms usados: 20-F, 6-K           ← NO tiene 10-K/10-Q
```

> 🧠 Regla: tu código tiene que **buscar en us-gaap Y en ifrs-full**. Si no encuentra el
> concepto en una, prueba la otra. (Ver el código de la sección 10.)

---

## 9. Tabla: qué concepto usar para cada dato

Para cada dato del screener, qué "tag" buscar en el JSON. Probá los conceptos en orden
hasta encontrar uno que exista (los nombres cambiaron con los años).

### Empresas USA (`us-gaap`)

| Dato | Concepto(s) us-gaap (en orden de prioridad) |
|------|---------------------------------------------|
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet` |
| Net Income | `NetIncomeLoss`, `ProfitLoss` |
| Operating Income | `OperatingIncomeLoss` |
| Total Assets | `Assets` |
| Total Liabilities | `Liabilities` |
| Equity | `StockholdersEquity` |
| Deuda largo plazo | `LongTermDebtNoncurrent`, `LongTermDebt` |
| Deuda corto plazo | `LongTermDebtCurrent`, `DebtCurrent` |
| Cash Flow Operativo | `NetCashProvidedByUsedInOperatingActivities` |
| CapEx | `PaymentsToAcquirePropertyPlantAndEquipment` |
| Depreciación & Amort. | `DepreciationDepletionAndAmortization`, `DepreciationAndAmortization` |
| EPS diluido | `EarningsPerShareDiluted` |
| Acciones diluidas | `WeightedAverageNumberOfDilutedSharesOutstanding` |
| Dividendos | `PaymentsOfDividendsCommonStock`, `PaymentsOfDividends` |

### Empresas extranjeras (`ifrs-full`) — equivalencias

| us-gaap | ifrs-full |
|---------|-----------|
| `Revenues` | `Revenue` |
| `NetIncomeLoss` | `ProfitLoss` |
| `OperatingIncomeLoss` | `ProfitLossFromOperatingActivities` |
| `Assets` | `Assets` |
| `Liabilities` | `Liabilities` |
| `StockholdersEquity` | `Equity` |
| `NetCashProvidedByUsedInOperatingActivities` | `CashFlowsFromUsedInOperatingActivities` |
| `EarningsPerShareDiluted` | `DilutedEarningsLossPerShare` |

### Unidad de medida (`units`)
Casi todo está en `USD`. Dos excepciones:
- Acciones (`shares`): unidad `shares`.
- EPS: unidad `USD-per-shares`.

---

## 10. Código de ejemplo paso a paso

```python
import requests
import time

# ── REGLA 1: User-Agent con tu nombre y email (sin esto → 403) ──
HEADERS = {
    "User-Agent": "Federico Monfasani fmonfasani@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}
DELAY = 0.15  # segundos entre requests (límite SEC = 10/seg)


def cargar_mapping_ticker_cik():
    """Descarga UNA vez el diccionario {ticker: CIK de 10 dígitos}."""
    url = "https://www.sec.gov/files/company_tickers.json"
    data = requests.get(url, headers=HEADERS, timeout=15).json()
    return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in data.values()}


def descargar_facts(cik):
    """REGLA 2: companyfacts (no submissions) para traer los números."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    return r.json() if r.status_code == 200 else None


def buscar_dato(facts, conceptos, unidad="USD", forms=("10-K", "20-F")):
    """Busca el valor ANUAL más reciente de un dato.

    - Recorre us-gaap Y ifrs-full (para empresas USA y extranjeras).
    - Prueba cada concepto de la lista hasta encontrar uno que exista.
    - Filtra por formularios anuales y devuelve el de fecha más nueva.
    """
    for taxonomia in ("us-gaap", "ifrs-full"):
        tax = facts.get("facts", {}).get(taxonomia, {})
        for concepto in conceptos:
            if concepto not in tax:
                continue
            registros = tax[concepto].get("units", {}).get(unidad, [])
            anuales = [r for r in registros if r.get("form") in forms]
            if anuales:
                return max(anuales, key=lambda r: r["end"])  # el más reciente
    return None


# ── USO ──
mapping = cargar_mapping_ticker_cik()

cik = mapping["AAPL"]                 # "0000320193"
facts = descargar_facts(cik)
time.sleep(DELAY)                     # respetar rate limit

revenue = buscar_dato(facts, [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues", "SalesRevenueNet",
    "Revenue",   # ← nombre IFRS, para ADRs extranjeros
])
net_income = buscar_dato(facts, ["NetIncomeLoss", "ProfitLoss"])
equity = buscar_dato(facts, ["StockholdersEquity", "Equity"])

# Calcular un ratio
margen_neto = net_income["val"] / revenue["val"]
roe = net_income["val"] / equity["val"]

print(f"Revenue:     ${revenue['val']:,}  ({revenue['form']}, {revenue['end']})")
print(f"Net Income:  ${net_income['val']:,}")
print(f"Margen Neto: {margen_neto:.1%}")
print(f"ROE:         {roe:.1%}")
```

Salida real para Apple:
```
Revenue:     $416,161,000,000  (10-K, 2025-09-27)
Net Income:  $112,010,000,000
Margen Neto: 26.9%
ROE:         ...
```

---

## 11. Errores comunes

| Síntoma | Causa | Solución |
|---------|-------|----------|
| **HTTP 403** | User-Agent genérico o ausente | Mandar `User-Agent: Nombre email@dominio` (Regla 1) |
| **`facts` vacío** | Usaste `/submissions/` | Usar `/api/xbrl/companyfacts/` (Regla 2) |
| **"No hay datos" en una empresa** | Es extranjera (IFRS) | Buscar también en `facts['ifrs-full']` (sección 8) |
| **Revenue da `None`** en empresa USA | El tag cambió en 2018 | Empezar la lista de fallback por `RevenueFromContractWithCustomerExcludingAssessedTax` |
| **Número parece viejo/raro** | Tomaste `registros[0]` | Filtrar por `form` y usar `max(..., key=lambda r: r["end"])` |
| **CIK no encontrado** | Empresa delisted o muy chica | Marcar para revisión manual (ej. TWTR, RDSB ya no cotizan) |
| **Mezclaste anual y trimestral** | No filtraste por `form` | Anual = `10-K`/`20-F`; trimestral = `10-Q`/`6-K` |
| **Llamás desde el frontend y falla** | EDGAR no soporta CORS | Llamar siempre desde el backend |

---

## 12. Glosario

| Término | En una frase |
|---------|--------------|
| **Acción** | Un pedacito de propiedad de una empresa. |
| **Ticker** | El nombre corto de una empresa en bolsa (AAPL, MSFT). |
| **CEDEAR** | Certificado argentino que representa una acción extranjera. |
| **ADR** | Forma en que una empresa extranjera cotiza en EE.UU. |
| **SEC** | El regulador de la bolsa de EE.UU. |
| **EDGAR** | La base de datos pública de la SEC con los reportes de las empresas. |
| **CIK** | El número de ID que la SEC le da a cada empresa. |
| **10-K** | Reporte anual de una empresa USA. |
| **10-Q** | Reporte trimestral de una empresa USA. |
| **20-F** | Reporte anual de una empresa extranjera (ADR). |
| **XBRL** | El formato estándar de los datos financieros (para nosotros: JSON). |
| **us-gaap** | Normas contables de EE.UU. (taxonomía). |
| **IFRS** | Normas contables internacionales (taxonomía). |
| **Revenue** | Ventas / facturación (la plata que entró). |
| **Net Income** | Ganancia neta (lo que quedó después de todo). |
| **Assets** | Activos (lo que la empresa tiene). |
| **Liabilities** | Pasivos (lo que la empresa debe). |
| **Equity** | Patrimonio (activos − pasivos = lo de los dueños). |
| **EBITDA** | Ganancia operativa antes de intereses, impuestos y amortizaciones. |
| **EPS** | Ganancia por acción. |
| **PER / P/E** | Precio dividido la ganancia por acción (¿cara o barata?). |
| **ROE** | Rentabilidad sobre el patrimonio. |
| **FCF** | Flujo de caja libre (plata que sobra de verdad). |
| **Payout** | Porcentaje de la ganancia repartido como dividendos. |
| **Dividendo** | Plata que la empresa le paga al accionista. |

---

## 13. Sistema para replicar el Excel de Seguimiento (dashboard)

> Esta sección documenta, de punta a punta, cómo construir un dashboard que
> replique `Seguimiento_original.xlsx` para **todos los papeles que cotizan en
> EE.UU.**, usando solo SEC EDGAR (financials) + yfinance (precios). Es el
> resultado de validar el pipeline contra Investing.com y corregir 10 problemas
> reales. Ver `docs/screener/DIAGNOSTICO_INVESTING_vs_EDGAR.md` para el detalle
> del análisis y `scripts/tickets/` para el código.

### 13.1 Objetivo y resultado

El Excel de seguimiento tiene 15 columnas por papel. Reproducirlas con datos
GAAP de EDGAR converge con Investing.com así (mediana de divergencia, set US):

| Métrica | mediana \|dif\| | dentro del 10% |
|---------|----------------|----------------|
| PER | 1,3% | 95% |
| EPS (TTM) | 1,3% | 95% |
| EPS (anual reportado) | 0,0% | 82% |
| Margen Neto | 0,0% | 91% |
| ROE | 0,4% | 85% |
| Payout | 0,0% | 87% |
| Crec. EPS 5Y | 1,5% | 58% |

Conclusión: **EDGAR-GAAP reproduce Investing**; las divergencias que quedan se
explican por causas conocidas y flagueadas (ver §13.5).

### 13.2 Las 15 columnas: fórmula y fuente exacta

| # | Columna (Excel) | Fórmula | Fuente / tag XBRL |
|---|-----------------|---------|-------------------|
| 1 | Especie | ticker | input |
| 2 | Dónde se encuentra | exchange | `yfinance.fast_info.exchange` |
| 3 | **Precio en u$s** | precio actual | `yfinance.fast_info.last_price` |
| 4 | **PER** | `precio / EPS_TTM` | calculado (ver fila EPS) |
| 5 | Precio Máximo 52s | máximo 52 semanas | `yfinance.fast_info.year_high` |
| 6 | Dif. contra Máx 52s | `precio / year_high − 1` | calculado |
| 7 | Precio Mínimo 52s | mínimo 52 semanas | `yfinance.fast_info.year_low` |
| 8 | Dif. contra Mín 52s | `precio / year_low − 1` | calculado |
| 9 | **Deuda/EBITDA** | `deuda / EBITDA_TTM` | deuda = `LongTermDebt` (+`LongTermDebtCurrent` +`ShortTermBorrowings`/`DebtCurrent`); EBITDA = `OperatingIncomeLoss` + D&A (ver §13.5.6) |
| 10 | **EPS (Anual)** | `NetIncome_TTM / DilutedShares` | `NetIncomeLoss`(→`ProfitLoss`) TTM / `WeightedAverageNumberOfDilutedSharesOutstanding`. ⚠️ pese al rótulo "Anual", la fórmula histórica es **TTM** (así cuadra con el PER) |
| 11 | **Crec. EPS 5 años** | CAGR de `EarningsPerShareDiluted` anual | serie anual limpia, 6 años (ver §13.5.1 y §13.5.8) |
| 12 | **Margen Neto** | `NetIncome_TTM / Revenue_TTM` | `Revenues`→`RevenueFromContractWithCustomerExcludingAssessedTax`→`SalesRevenueNet` |
| 13 | **ROE (5 años)** | CAGR del ROE anual | `NetIncomeLoss`/`StockholdersEquity` por año, luego CAGR. ⚠️ es **CAGR a 5 años**, NO el ROE TTM |
| 14 | **FCFonCE** | `FCF_TTM / Capital_empleado` | FCF = `NetCashProvidedByUsedInOperatingActivities` − `PaymentsToAcquirePropertyPlantAndEquipment`; CapEmpleado = `StockholdersEquity` + deuda LP (variante A) o + deuda − caja (variante B) |
| 15 | **Payout** | `Dividendos_TTM / NetIncome_TTM` | `PaymentsOfDividendsCommonStock`→`PaymentsOfDividends` |

> **Dos columnas que confunden por el rótulo**: la "EPS (Anual)" se calcula TTM
> (para que `PER × EPS = precio`); el "ROE (5 años)" es un CAGR, no un nivel.
> Si además querés comparar contra la columna "Diluted EPS ANN" de Investing,
> usá el **EPS anual reportado** (`EarningsPerShareDiluted` del último 10-K),
> que es un dato distinto del EPS TTM (ver §13.5.2).

### 13.3 Arquitectura del pipeline (5 pasos)

Implementado en `scripts/tickets/` (aislado, no toca `backend/`):

1. **`01_mapear_cik.py`** — ticker → CIK vía `company_tickers.json`. Excluye
   tickers reciclados por la SEC (GOLD, CHA) y manda a revisión manual lo que
   no matchea, en vez de adivinar.
2. **`02_descargar_datos.py`** — baja `companyfacts` (SEC) y precios (yfinance),
   cacheado en `datos/`. Resume-safe (no re-baja lo que ya está).
3. **`03_calcular_ratios.py`** — el corazón: TTM, CAGR, EBITDA, ROE, etc. Acá
   viven los 10 fixes de §13.5.
4. **`04_generar_reporte.py`** — Excel con tabs Ratios / Calidad / Sin CIK.
5. **`05_comparar_investing.py`** — cruza por ticker (nunca por fila) contra el
   archivo de seguimiento y calcula divergencias.

### 13.4 El cálculo del TTM (lo más importante)

**Clave 1: `companyfacts` ya trae TODO.** No se bajan filings individuales: el
endpoint `companyfacts` devuelve el dataset XBRL agregado completo (100+
datapoints por empresa), con trimestres de 10-Q **y** anuales de 10-K. No hace
falta "bajar los últimos 6 10-Q" — ya están.

**Clave 2: tres estrategias para armar el TTM de un flujo** (revenue, net income,
etc.), en orden de preferencia:

- **A** — 4 trimestres standalone (~90d) consecutivos → sumar.
- **B (generalizada)** — `Anual + parcial_FY_nuevo − mismo_parcial_año_anterior`.
  El "parcial del FY nuevo" puede ser 1 trimestre (Q1, ~90d), un semestre o 9
  meses. Ej. a junio 2026: `FY2025 + Q1'2026 − Q1'2025`.
- **C** — último anual solo. ⚠️ **NO es un TTM rodante**: es el último año fiscal
  cerrado. Si un trimestre reciente tuvo un ítem no recurrente, diverge.

**Por qué importa:** el "Q4 standalone" no existe (no hay 10-Q de Q4; el Q4 es
anual − 9 meses YTD), así que la estrategia A casi nunca aplica. La B es la
canónica. Antes de generalizarla, cuando el último filing era el Q1 del año nuevo
caía a C y el TTM divergía (MRK/JNJ/LLY). Con la B generalizada, 39 de 53
empresas usan TTM rodante real.

### 13.5 Las 10 trampas que hay que evitar (con su fix)

Cada una rompía silenciosamente algún ratio. Están todas resueltas en
`03_calcular_ratios.py` y expuestas como flags en el campo `_flags`.

**1. Dedup por `fy` (el peor bug).** El campo XBRL `fy` es el año del *filing*,
no del período: un 10-K reporta 2-3 años comparativos **con el mismo `fy`**.
Deduplicar la serie anual por `fy` los colapsa y se pisan (ej. MRK 2023/2024/2025
comparten fy=2025; el 2023 tenía EPS 0,14 por un cargo y contaminaba todo).
**Fix:** deduplicar por el **`end` del período**, no por `fy`. Esto solo arregló
`eps_annual`, `cagr_eps` y `roe_cagr` a la vez (Crec. EPS pasó de mediana 104% a
1,5%).

**2. EPS TTM ≠ EPS anual.** Investing tiene dos columnas con earnings distintos:
"P/E Ratio TTM" usa TTM rodante, "Diluted EPS ANN" usa el anual reportado. No se
reconstruye uno desde el otro. **Fix:** calcular ambos —`eps_ttm_diluted`
(NetIncome_TTM/shares, alimenta el PER) y `eps_annual` (`EarningsPerShareDiluted`
del último 10-K)— y comparar cada uno contra su par.

**3. Ventana TTM = FY (estrategia C).** Ver §13.4. **Fix:** estrategia B
generalizada + flag `ni_es_fy_no_ttm` cuando igual cae a C.

**4. Datos stale.** Foreign private issuers (TM/Toyota, VALE, NMR) dejaron de
filear us-gaap detallado; su último income statement es de 2012 pero se tomaba
como "TTM" actual. **Fix:** si el net income usado tiene >2 años → anular los
ratios (flag `stale_<fecha>`).

**5. Escala de shares.** NMR tagea el weighted-avg de acciones con la unidad
equivocada (3,04×10¹⁵, ~10⁶ de más) → EPS/PER absurdos. **Fix:** descartar
`diluted_shares` si difiere >100× del `CommonStockSharesOutstanding` (flag
`shares_descartadas_escala`).

**6. EBITDA e intangibles.** Elegir el tag de D&A "más reciente" tomaba el
estrecho `Depreciation` (sin amortización de intangibles) y subestimaba el EBITDA
de empresas adquisitivas (ORCL/Cerner, GE, IBM). **Fix:** usar
`DepreciationDepletionAndAmortization` si existe; si no, el tag de **mayor** TTM
(evita el mis-tag de INTC); y si solo hay `Depreciation`, sumarle
`AmortizationOfIntangibleAssets` (flag `ebitda_da_mas_intangibles`).

**7. ROE con equity puntual.** Daba ruido en empresas con recompras. **Fix:**
usar **equity promedio** (último balance + el de ~1 año antes) / 2, como
Investing. Mediana de divergencia de ROE: 10,4% → 0,4%. Flag
`roe_no_significativo` si equity < 5% de los activos (ej. CL, equity casi cero
por treasury stock → ROE no interpretable).

**8. Crec. EPS con base corrupta.** El CAGR explota si el año base es chico o
está contaminado (CSCO base 0,02 → +173% falso). **Fix:** serie anual limpia
(solo años fiscales completos) + descartar el cálculo si el año base es < 10% de
la mediana de la serie.

**9. PER con EPS ≤ 0.** Un PER negativo no tiene sentido económico. **Fix:** PER
= NULL si EPS ≤ 0 (Investing a veces muestra el negativo; EDGAR no).

**10. Empresas IFRS (pendiente).** El fetcher cae a `ifrs-full` pero
`METRICAS_GAAP` lista nombres us-gaap → 0 métricas para INFY, TSM, RIO, BHP,
KGC, NVS, etc. **Pendiente:** mapear los tags IFRS (`Revenue`, `ProfitLoss`,
`EquityAttributableToOwnersOfParent`…). Por ahora el sistema cubre solo US-GAAP.

### 13.6 Cómo llevarlo a un dashboard

1. **Universo:** lista de tickers US (los que mapean a un CIK en
   `company_tickers.json`). Los IFRS y stale quedan marcados, no rotos.
2. **Refresh:** precios (yfinance) son intradiarios; financials (EDGAR) cambian
   solo cuando hay un nuevo 10-Q/10-K (trimestral). Cachear `companyfacts` y
   re-bajar solo ante un filing nuevo.
3. **Persistencia:** guardar los ratios calculados + el campo `_flags` por
   ticker. El dashboard muestra el ratio y, si hay flag, un ícono de advertencia
   con el motivo (stale / FY-no-TTM / ROE no significativo / etc.).
4. **Regla de oro:** **nunca estimar.** Si falta un componente, el ratio es NULL.
   Un NULL honesto vale más que un número inventado.
5. **Validación continua:** correr `05_comparar_investing.py` contra una muestra
   cargada a mano cada tanto; si la mediana de divergencia de PER/EPS/Margen/ROE
   se va por encima de ~5%, algo se rompió.

---

## Fuentes oficiales

- [EDGAR APIs (documentación oficial)](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC Developer Resources](https://www.sec.gov/about/developer-resources)
- [SEC Webmaster FAQ (rate limit y User-Agent)](https://www.sec.gov/os/webmaster-faq)
- `https://www.sec.gov/files/company_tickers.json` (mapping ticker→CIK)

> Documento verificado empíricamente el 24-jun-2026: pruebas de User-Agent (403 vs 200) y
> descarga real de datos de Apple (us-gaap) y Taiwan Semiconductor (ifrs-full).
