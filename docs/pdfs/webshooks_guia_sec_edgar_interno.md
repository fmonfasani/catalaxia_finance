webshooks
Documento interno
Guía técnica SEC EDGAR
Integración de datos financieros para el screener
Última actualización: 24 de junio de 2026
Clasificación: interno · webshooks.com
Resumen ejecutivo
Documento de referencia para la integración del backend de screener financiero con la API pública de
SEC EDGAR. Cubre el modelo conceptual mínimo de los datos, las reglas de consumo de la API, las
diferencias entre emisores estadounidenses (us-gaap) y extranjeros (IFRS), el mapeo concepto a
concepto necesario para poblar la tabla del screener, código de referencia y los errores recurrentes
observados en iteraciones previas.
Audiencia: equipo de ingeniería de webshooks asignado al pipeline Catalaxia Finance y proyectos derivados. Pre-requisitos:
Python, HTTP, JSON; no se asume formación contable previa.


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 2
Índice
1. Problema a resolver
2. Conceptos de mercado
3. Qué es SEC EDGAR
4. Los tres estados financieros
5. Ratios financieros del screener
6. La API de SEC EDGAR (parte técnica)
7. XBRL: estructura de los datos
8. Emisores USA vs. extranjeros (us-gaap vs. IFRS)
9. Tabla de mapeo concepto → dato
10. Código de referencia
11. Errores comunes y diagnóstico
12. Glosario
13. Fuentes oficiales


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 3
1. Problema a resolver
El producto es un screener financiero: una matriz de empresas en la que, para cada emisor, se exponen
métricas que permiten al usuario evaluar su atractivo relativo (rentabilidad, apalancamiento, eficiencia
operativa, valuación). Para alimentar esa matriz se requieren datos financieros confiables y trazables por
empresa. Existen dos caminos posibles:
Scraping de portales financieros (Investing.com, Yahoo Finance). Frágil ante cambios de DOM,
sujeto a bloqueos por IP y a inconsistencias en los números expuestos (criterios de cálculo opacos,
normalizaciones propias del agregador). Esta vía fue intentada y descartada; la evidencia queda
documentada en la carpeta failed_investing_scraping/.
SEC EDGAR. Repositorio oficial del gobierno de los Estados Unidos donde toda empresa cotizante está
obligada por ley a publicar sus estados financieros. API pública, gratuita, sin clave y con esquema estable.
Es el camino correcto y la base de este documento.
2. Conceptos de mercado
Antes de la parte técnica, conviene fijar seis términos sin los cuales el resto del documento pierde
precisión.
2.1 Acción (stock / share)
Unidad mínima de propiedad de una sociedad anónima. Quien posee una acción posee una fracción
proporcional del capital social. Si una empresa tiene N acciones en circulación, cada acción representa
1/N del capital.
2.2 Bolsa (stock exchange)
Mercado organizado donde se compran y venden acciones. Las dos principales son NYSE y NASDAQ
(ambas en EE.UU.); en Argentina opera BYMA.
2.3 Ticker
Identificador alfabético corto y único de un emisor dentro de una bolsa: AAPL (Apple), MSFT (Microsoft),
KO (Coca-Cola).
2.4 CEDEAR
Certificado de Depósito Argentino: instrumento local, en pesos, que representa una acción extranjera
(típicamente estadounidense) y permite exposición a ese subyacente sin operar una cuenta offshore. A
los efectos de los datos financieros, un CEDEAR de Apple es equivalente a la acción de Apple: los
fundamentals del emisor son los mismos.
2.5 ADR
American Depositary Receipt: instrumento inverso al CEDEAR. Permite a una empresa no
estadounidense cotizar en bolsas de EE.UU. Ejemplos: TSM (Taiwan Semiconductor), PBR (Petrobras),
MELI (MercadoLibre).
Implicancia técnica: por tratarse de emisores extranjeros, los ADRs reportan bajo un esquema contable
distinto al de las empresas USA (ver sección 8).


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 4
2.6 Precio vs. datos financieros
Dos magnitudes que se confunden con frecuencia y conviene separar explícitamente:
• Precio: cotización instantánea de una acción en mercado. Variable en tiempo real. No está en
EDGAR; se obtiene de yfinance u otro proveedor de cotizaciones.
• Datos financieros: revenue, ganancia, deuda, etc. Frecuencia trimestral. Sí están en EDGAR.
Regla mental: EDGAR = fundamentals del emisor. yfinance = precio de la acción.
3. Qué es SEC EDGAR
3.1 La SEC
La Securities and Exchange Commission es el organismo regulador del mercado de capitales
estadounidense. Entre sus competencias está la obligación de transparencia: todo emisor cotizante debe
publicar de manera pública, periódica y verificable sus estados financieros.
3.2 EDGAR
EDGAR (Electronic Data Gathering, Analysis and Retrieval) es el sistema donde la SEC concentra y
publica esos reportes. Actúa como repositorio histórico: cada presentación queda accesible de forma
permanente y puede consultarse vía web o API.
3.3 Formularios relevantes
Los emisores presentan distintos tipos de documentos. Para el screener interesan estos cuatro:
Form
Descripción
Frecuencia
Aplica a
10-K
Reporte anual completo
1 vez al año
Emisores USA
10-Q
Reporte trimestral
3 veces al año*
Emisores USA
20-F
Reporte anual de emisor extranjero
1 vez al año
ADRs extranjeros
6-K
Reporte interino de emisor extranjero
Variable
ADRs extranjeros
*El cuarto trimestre del año fiscal se consolida dentro del 10-K anual; de allí que solo existan tres 10-Q por año.
Al inspeccionar el JSON, "form": "10-K" corresponde a información del año fiscal completo y
"form": "10-Q" a un trimestre individual (3 meses).


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 5
4. Los tres estados financieros
Toda empresa reporta su situación a través de tres documentos. Comprenderlos cubre el 90% del
razonamiento financiero necesario para el screener.
4.1 Estado de Resultados (Income Statement)
Responde a la pregunta: ¿cuánto ganó o perdió la empresa en un período determinado? Estructura de
arriba hacia abajo:
Revenue (Ingresos / Ventas)          <- entradas por venta
- Costos                              <- costo de producir lo vendido
------------------------------------------------------------
= Operating Income (Ganancia operativa) <- resultado del negocio core
- Impuestos, intereses, etc.
------------------------------------------------------------
= Net Income (Ganancia Neta)          <- resultado final del período
Revenue (ingresos / ventas): total facturado por venta de productos o servicios. También denominado
top line.
Net Income (ganancia neta): resultado después de costos, impuestos e intereses. También denominado
bottom line. Es la métrica de cierre del estado: un valor positivo indica utilidad y uno negativo, pérdida del
período.
En términos comparativos, Revenue equivale al ingreso bruto y Net Income al ingreso disponible una vez
deducidos todos los conceptos pasivos (costos operativos, financieros e impositivos).
4.2 Balance General (Balance Sheet)
Responde a la pregunta: ¿qué posee y qué adeuda la empresa en un instante de corte? Es una fotografía
puntual (no un flujo) y siempre se cumple la identidad contable:
Assets (Activos) = Liabilities (Pasivos) + Equity (Patrimonio)
Lo que la empresa tiene = Lo que debe + Lo que pertenece a los socios
Assets (activos): conjunto de bienes y derechos del emisor (efectivo, inventario, propiedad, planta y
equipo, intangibles).
Liabilities (pasivos): obligaciones del emisor frente a terceros (deuda financiera, cuentas por pagar,
provisiones).
Equity (patrimonio / stockholders equity): valor residual perteneciente a los accionistas una vez
liquidados los pasivos. Algebraicamente, Activos − Pasivos = Patrimonio. A modo de ilustración, una
propiedad de USD 100.000 con una hipoteca de USD 70.000 implica un equity efectivo de USD 30.000.
Debt (deuda): subconjunto de los pasivos correspondientes a préstamos con costo financiero. Es el
numerador estándar de los indicadores de apalancamiento.
4.3 Estado de Flujo de Efectivo (Cash Flow Statement)
Responde a la pregunta: ¿cuánto efectivo real entró y salió en el período? Existe porque la ganancia
contable (Net Income) incorpora criterios de devengado, depreciaciones y ajustes que no necesariamente
se traducen en flujos de caja. El cash flow refleja el movimiento efectivo de dinero.
• Operating Cash Flow: efectivo generado por la operación principal del negocio.
• CapEx (Capital Expenditures): erogaciones destinadas a la adquisición o mejora de activos fijos de
uso prolongado (infraestructura, maquinaria, equipamiento).


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 6
• Free Cash Flow (FCF): Operating Cash Flow − CapEx. Representa el efectivo libre disponible
una vez garantizado el mantenimiento del activo productivo. Es una métrica altamente valorada porque
cuantifica la caja que el emisor puede distribuir o reinvertir.


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 7
5. Ratios financieros del screener
Un ratio es el cociente entre dos magnitudes financieras. Su utilidad principal es normalizar
comparaciones entre emisores de tamaño dispar: los valores absolutos de una multinacional no son
comparables con los de una empresa local, pero sí lo son los porcentajes y proporciones derivados. A
continuación, los ratios contemplados en el screener.
5.1 EPS (Earnings Per Share)
EPS = Net Income / Número de acciones
Indica la utilidad asignable a cada acción en circulación. Ejemplo: una empresa con utilidad de USD 1.000
millones y 100 millones de acciones presenta un EPS de 10 USD por acción.
5.2 PER (Price/Earnings)
PER = Precio de la acción / EPS
Expresa cuántos años de ganancias actuales paga el inversor al adquirir la acción. Es el indicador de
valuación de referencia. Ejemplo: una acción a USD 100 con EPS de 10 USD implica un PER de 10x.
Valores bajos (p. ej. 8x) suelen interpretarse como acción barata; valores altos (p. ej. 40x) como cara,
sujeto al contexto del sector.
Particularidad: requiere el precio (de yfinance). Es el único ratio del screener que combina datos de
EDGAR y de un feed de cotizaciones.
5.3 Margen Neto (Net Margin)
Margen Neto = Net Income / Revenue
Mide la proporción de cada unidad facturada que se convierte en utilidad neta. Indicador de eficiencia
operativa y rentabilidad. Ejemplo: un margen de 0,25 (25%) significa que de cada USD 100 facturados,
USD 25 son utilidad. Sectores intensivos en marca y tecnología (Apple) tienden a presentar márgenes
altos; el retail de alta rotación, márgenes bajos.
5.4 ROE (Return on Equity)
ROE = Net Income / Equity
Mide la rentabilidad del capital aportado por los accionistas. Un ROE de 0,20 (20%) indica que por cada
USD 100 de patrimonio, el emisor genera USD 20 anuales de utilidad neta. A mayor valor, mayor
rendimiento del capital propio.
5.5 Debt/Equity
Deuda/Equity = Deuda total / Equity
Indicador de apalancamiento estructural. Compara el endeudamiento financiero contra el capital propio.
Un ratio de 2 implica deuda igual al doble del patrimonio (perfil riesgoso); un ratio de 0,3 indica estructura
conservadora.
5.6 EBITDA y Deuda/EBITDA
EBITDA: utilidad antes de intereses, impuestos, depreciación y amortización. Es una aproximación a la
rentabilidad operativa pura del negocio, depurada de efectos financieros, fiscales y contables no


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 8
monetarios.
EBITDA = Operating Income + Depreciación y Amortización
Deuda/EBITDA = Deuda total / EBITDA
Deuda/EBITDA representa la cantidad de años de generación operativa necesarios para cancelar el stock
de deuda. Valores por debajo de 3x suelen considerarse saludables; por encima de 5x, indicio de estrés
financiero.
5.7 FCF (Free Cash Flow)
FCF = Operating Cash Flow - CapEx
Efectivo libre real generado por la operación tras cubrir las inversiones de capital necesarias para
sostener el negocio. Detalle conceptual desarrollado en 4.3.
5.8 Payout (Dividend Payout Ratio)
Payout = Dividendos pagados / Net Income
Proporción de la utilidad neta que el emisor distribuye como dividendos a sus accionistas, en oposición a
la fracción reinvertida en el negocio. Un dividendo es la retribución periódica en efectivo (u otros
instrumentos) que la empresa paga a quienes poseen sus acciones. Ejemplo: un payout de 0,40 (40%)
implica que se reparte el 40% de la utilidad y se retiene el 60%.
5.9 Crecimiento de EPS a 5 años
Variación del EPS comparando el reporte anual más reciente con el de cinco años previos. Permite
identificar si el emisor está en expansión, estabilidad o contracción de su utilidad por acción.
Nota técnica: es el ratio de implementación más costosa, ya que requiere recuperar y consolidar cinco
reportes anuales históricos (10-K) y no solo el último.


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 9
6. La API de SEC EDGAR (parte técnica)
EDGAR expone APIs REST públicas, gratuitas y sin necesidad de API key. Todas las respuestas son
JSON.
6.1 Las cuatro APIs
Endpoint
URL
Función
submissions
https://data.sec.gov/submissions/CIK#####
#####.json
Metadata del emisor: nombre, tickers,
historial. No incluye valores financieros.
companyconcept
https://data.sec.gov/api/xbrl/companyconc
ept/CIK##########/us-gaap/{Concepto}.json
Un único concepto (ej. NetIncomeLoss)
para un único emisor. Payload liviano
(~50 KB).
companyfacts
https://data.sec.gov/api/xbrl/companyfact
s/CIK##########.json
Todos los conceptos financieros del
emisor en una sola llamada. Endpoint de
uso principal en el pipeline.
frames
https://data.sec.gov/api/xbrl/frames/us-g
aap/{Concepto}/USD/CY####Q#.json
Un concepto para todos los emisores en
un período dado. Útil para comparativas
de universo.
6.2 Dos reglas innegociables
Las dos causas raíz de fallas reiteradas en intentos previos. Su incumplimiento explica el 100% de los
bloqueos y JSONs vacíos observados en producción.
Regla 1 — User-Agent obligatorio con nombre real y email
La SEC rechaza con HTTP 403 toda solicitud que no identifique al consumidor. Headers genéricos del
tipo Mozilla/5.0 o python-requests son insuficientes. La identificación debe incluir nombre real y
dirección de correo de contacto:
headers = {
    "User-Agent": "Tu Nombre tu-email@dominio.com",
    "Accept-Encoding": "gzip, deflate",
}
Evidencia empírica (verificada el 24-jun-2026):
• User-Agent "Mozilla/5.0" → HTTP 403 (bloqueado)
• User-Agent "python-requests/2.31" → HTTP 403 (bloqueado)
• User-Agent "Federico Monfasani fede@mail.com" → HTTP 200 (operativo)
Si se observa un 403, en el 99% de los casos la causa es el User-Agent. No es un bloqueo de IP ni un
filtro de CloudFlare.
Regla 2 — Endpoint correcto para los valores financieros
 /submissions/ devuelve únicamente metadata. Si se utiliza, el campo facts viene vacío.
 /api/xbrl/companyfacts/ es el endpoint que expone los valores financieros estructurados.
Este fue el segundo error detectado en el intento previo: la respuesta HTTP era 200 OK pero el JSON no
contenía datos financieros, porque la URL apuntaba al endpoint equivocado.


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 10
6.3 Rate limit: 10 requests por segundo
El límite oficial de la SEC es de hasta 10 requests por segundo, lo cual es holgado para el caso de uso.
Para mantenerse cómodamente por debajo del techo, el pipeline introduce un time.sleep(0.15) entre
llamadas (aproximadamente 6 req/s). Con esa cadencia, la descarga de 212 emisores se completa en
unos 45 segundos.
Mito a descartar: no es necesario esperar 5 segundos entre requests. Esa creencia, propagada en hilos
antiguos, es injustificada y vuelve el pipeline impracticable. El problema histórico nunca fue la velocidad
sino el User-Agent (Regla 1).
6.4 El CIK (resolución de emisores)
La API no acepta el ticker (AAPL) como identificador. Cada emisor está indexado por su CIK (Central
Index Key), un identificador numérico asignado por la SEC. Apple = CIK 320193.
Para traducir ticker → CIK, la SEC publica un archivo con aproximadamente 10.400 emisores:
https://www.sec.gov/files/company_tickers.json
Se descarga una sola vez, se construye un diccionario {ticker: cik} en memoria y queda disponible
para todo el batch.
Importante: el CIK debe expresarse con 10 dígitos, completando con ceros a la izquierda: 320193 →
0000320193. En Python: str(cik).zfill(10).


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 11
7. XBRL: estructura de los datos
Los datos financieros se entregan en formato XBRL (eXtensible Business Reporting Language), un
estándar internacional. En la práctica, para el cliente del API es JSON anidado. Cada valor financiero
(fact) presenta la siguiente estructura:
{
  "start": "2024-09-29",          // inicio del período (solo magnitudes de flujo)
  "end":   "2025-09-27",          // fin del período / fecha de la foto
  "val":   112010000000,          // valor reportado (USD 112 mil millones)
  "accn":  "0000320193-25-...",   // identificador del reporte de origen
  "fy":    2025,                  // año fiscal
  "fp":    "FY",                  // período fiscal: FY=anual, Q1/Q2/Q3=trim.
  "form":  "10-K",                // tipo de formulario
  "filed": "2025-10-31",          // fecha de publicación
  "frame": "CY2025"               // período calendario asignado
}
7.1 Magnitudes de "flujo" vs. "foto"
Distinción crítica para no mezclar conceptos al consumir el JSON:
• Flujo (revenue, ganancia neta, cash flow): los registros traen start y end. Cuantifican algo ocurrido
durante un intervalo (p. ej., facturación de enero a marzo).
• Foto / instantáneo (assets, equity, deuda): los registros traen solo end. Cuantifican el valor en una
fecha puntual (p. ej., deuda al 31 de diciembre).
7.2 Discriminar dato anual vs. trimestral
Para un mismo concepto (p. ej. NetIncomeLoss), la API devuelve múltiples registros: anuales y
trimestrales, de varios años fiscales. Para quedarse con el dato anual más reciente:
anuales = [r for r in registros if r["form"] == "10-K"]   # solo anuales
mas_reciente = max(anuales, key=lambda r: r["end"])       # el de fecha más nueva
Error típico: tomar registros[0] o registros[-1] asumiendo orden. El orden no está garantizado.
Filtrar siempre por form y seleccionar por fecha con max(...).
7.3 TTM (Trailing Twelve Months)
Muchos agregadores exponen métricas en formato TTM, es decir, los últimos doce meses móviles.
EDGAR no entrega este agregado pre-calculado. La aproximación más simple para el screener es utilizar
el último año fiscal disponible (10-K): es suficiente para el caso de uso y coincide con lo que muestran la
mayoría de los agregadores públicos. El cálculo exacto de TTM —sumando los cuatro trimestres más
recientes— ofrece mayor precisión pero implica mayor complejidad de implementación; queda diferido a
una v2.


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 12
8. Emisores USA vs. extranjeros
Un punto crítico, frecuentemente subestimado: no todos los emisores reportan bajo el mismo esquema
contable.
Emisores USA (CEDEARs)
Emisores extranjeros (ADRs)
Taxonomía
us-gaap
ifrs-full
Form anual
10-K
20-F
Ejemplos
AAPL, MSFT, KO, JNJ, WMT
TSM, PBR, VALE, BBVA, SAP, BABA
us-gaap agrupa las normas contables estadounidenses. IFRS agrupa las normas contables
internacionales utilizadas por emisores fuera de EE.UU.
Implicancia operativa: los conceptos llevan nombres distintos en cada taxonomía. Si el código busca
NetIncomeLoss (nombre us-gaap) en un emisor que reporta bajo IFRS, no lo encontrará y reportará
erróneamente ausencia de datos, cuando en realidad la información existe bajo otro nombre
(ProfitLoss).
Evidencia (TSM, Taiwan Semiconductor):
Taxonomias presentes: dei, ifrs-full, srt   <- NO contiene us-gaap
Forms utilizados:     20-F, 6-K              <- NO contiene 10-K / 10-Q
Regla: el código debe consultar us-gaap y ifrs-full. Si el concepto no aparece en la primera
taxonomía, debe intentarse en la segunda (ver código de referencia en la sección 10).


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 13
9. Tabla de mapeo concepto → dato
Para cada métrica del screener, los tags a buscar en el JSON. La convención es probar los conceptos en
orden de prioridad hasta encontrar uno presente en los datos; los nombres han mutado a lo largo de las
distintas versiones de la taxonomía.
Emisores USA (us-gaap)
Dato
Concepto(s) us-gaap (orden de prioridad)
Revenue
RevenueFromContractWithCustomerExcludingAssessedTax, Revenues,
SalesRevenueNet
Net Income
NetIncomeLoss, ProfitLoss
Operating Income
OperatingIncomeLoss
Total Assets
Assets
Total Liabilities
Liabilities
Equity
StockholdersEquity
Deuda largo plazo
LongTermDebtNoncurrent, LongTermDebt
Deuda corto plazo
LongTermDebtCurrent, DebtCurrent
Cash Flow Operativo
NetCashProvidedByUsedInOperatingActivities
CapEx
PaymentsToAcquirePropertyPlantAndEquipment
Depreciación & Amort.
DepreciationDepletionAndAmortization, DepreciationAndAmortization
EPS diluido
EarningsPerShareDiluted
Acciones diluidas
WeightedAverageNumberOfDilutedSharesOutstanding
Dividendos
PaymentsOfDividendsCommonStock, PaymentsOfDividends
Emisores extranjeros (ifrs-full): equivalencias
us-gaap
ifrs-full
Revenues
Revenue
NetIncomeLoss
ProfitLoss
OperatingIncomeLoss
ProfitLossFromOperatingActivities
Assets
Assets
Liabilities
Liabilities
StockholdersEquity
Equity
NetCashProvidedByUsedInOperatingActivities
CashFlowsFromUsedInOperatingActivities


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 14
us-gaap
ifrs-full
EarningsPerShareDiluted
DilutedEarningsLossPerShare
Unidad de medida (units)
La práctica totalidad de los conceptos se expresa en USD. Dos excepciones:
• Acciones (shares): unidad shares.
• EPS: unidad USD-per-shares.


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 15
10. Código de referencia
Implementación mínima que aplica las dos reglas y resuelve la búsqueda cross-taxonomía (us-gaap +
ifrs-full).
import requests
import time
# -- REGLA 1: User-Agent con nombre y email (sin esto -> 403) --
HEADERS = {
    "User-Agent": "Federico Monfasani fmonfasani@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}
DELAY = 0.15   # segundos entre requests (limite SEC = 10/seg)
def cargar_mapping_ticker_cik():
    """Descarga UNA vez el diccionario {ticker: CIK de 10 digitos}."""
    url = "https://www.sec.gov/files/company_tickers.json"
    data = requests.get(url, headers=HEADERS, timeout=15).json()
    return {v["ticker"]: str(v["cik_str"]).zfill(10)
            for v in data.values()}
def descargar_facts(cik):
    """REGLA 2: companyfacts (no submissions) para traer los numeros."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    return r.json() if r.status_code == 200 else None
def buscar_dato(facts, conceptos, unidad="USD", forms=("10-K", "20-F")):
    """Busca el valor ANUAL mas reciente de un dato.
    - Recorre us-gaap Y ifrs-full (emisores USA y extranjeros).
    - Prueba cada concepto de la lista hasta encontrar uno existente.
    - Filtra por formularios anuales y devuelve el de fecha mas nueva.
    """
    for taxonomia in ("us-gaap", "ifrs-full"):
        tax = facts.get("facts", {}).get(taxonomia, {})
        for concepto in conceptos:
            if concepto not in tax:
                continue
            registros = tax[concepto].get("units", {}).get(unidad, [])
            anuales = [r for r in registros if r.get("form") in forms]
            if anuales:
                return max(anuales, key=lambda r: r["end"])
    return None
# -- USO --
mapping = cargar_mapping_ticker_cik()
cik = mapping["AAPL"]                # "0000320193"
facts = descargar_facts(cik)
time.sleep(DELAY)                    # respetar rate limit
revenue = buscar_dato(facts, [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues", "SalesRevenueNet",
    "Revenue",                       # <- nombre IFRS, para ADRs extranjeros
])
net_income = buscar_dato(facts, ["NetIncomeLoss", "ProfitLoss"])
equity     = buscar_dato(facts, ["StockholdersEquity", "Equity"])
# Calculo de ratios
margen_neto = net_income["val"] / revenue["val"]
roe         = net_income["val"] / equity["val"]


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 16
print(f"Revenue:    ${revenue['val']:,} ({revenue['form']}, {revenue['end']})")
print(f"Net Income: ${net_income['val']:,}")
print(f"Margen Neto: {margen_neto:.1%}")
print(f"ROE:         {roe:.1%}")
Salida real para Apple:
Revenue:     $416,161,000,000  (10-K, 2025-09-27)
Net Income:  $112,010,000,000
Margen Neto: 26.9%
ROE:         ...


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 17
11. Errores comunes y diagnóstico
Síntoma
Causa
Solución
HTTP 403
User-Agent genérico o
ausente
Enviar User-Agent: Nombre email@dominio
(Regla 1)
facts vacío
Uso de /submissions/
Cambiar a /api/xbrl/companyfacts/ (Regla 2)
"No hay datos" en una
empresa
Emisor extranjero (IFRS)
Consultar también facts['ifrs-full'] (sección 8)
Revenue devuelve
None en emisor USA
El tag cambió en 2018
Iniciar la lista de fallback por RevenueFromC
ontractWithCustomerExcludingAssessedTax
Número parece viejo o
anómalo
Se tomó registros[0]
Filtrar por form y usar max(..., key=lambda r:
r['end'])
CIK no encontrado
Empresa delisted o de
bajísima capitalización
Marcar para revisión manual (p. ej. TWTR,
RDSB ya no cotizan)
Mezcla de datos
anuales y trimestrales
No se filtró por form
Anual = 10-K / 20-F; trimestral = 10-Q / 6-K
Llamada desde el
frontend falla
EDGAR no soporta CORS
Invocar siempre desde el backend


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 18
12. Glosario
Término
Definición
Acción
Unidad de propiedad sobre el capital de una empresa.
Ticker
Identificador corto del emisor en la bolsa (AAPL, MSFT).
CEDEAR
Certificado argentino que representa una acción extranjera.
ADR
Instrumento mediante el cual una empresa extranjera cotiza en EE.UU.
SEC
Regulador del mercado de capitales de los Estados Unidos.
EDGAR
Base de datos pública de la SEC con los reportes de los emisores.
CIK
Identificador numérico que la SEC asigna a cada emisor.
10-K
Reporte anual de un emisor estadounidense.
10-Q
Reporte trimestral de un emisor estadounidense.
20-F
Reporte anual de un emisor extranjero (ADR).
XBRL
Formato estándar de los datos financieros (en este caso, JSON).
us-gaap
Taxonomía contable estadounidense.
IFRS
Taxonomía contable internacional.
Revenue
Ventas / facturación (ingresos del período).
Net Income
Ganancia neta (resultado después de todos los cargos).
Assets
Activos (bienes y derechos del emisor).
Liabilities
Pasivos (obligaciones del emisor).
Equity
Patrimonio (Activos − Pasivos: residual de los accionistas).
EBITDA
Ganancia operativa antes de intereses, impuestos y amortizaciones.
EPS
Ganancia por acción.
PER / P/E
Precio sobre ganancia por acción (indicador de valuación).
ROE
Rentabilidad sobre el patrimonio.
FCF
Flujo de caja libre.
Payout
Porcentaje de la ganancia distribuido como dividendos.
Dividendo
Retribución periódica que el emisor paga a sus accionistas.
13. Fuentes oficiales


webshooks · documento interno
Guía técnica · SEC EDGAR
Confidencial · uso interno · webshooks.com
Página 19
• EDGAR APIs — documentación oficial.
• SEC Developer Resources.
• SEC Webmaster FAQ (rate limit y User-Agent).
• https://www.sec.gov/files/company_tickers.json (mapping ticker → CIK).
Documento verificado empíricamente el 24 de junio de 2026: pruebas de User-Agent (403 vs. 200) y descarga real de datos
de Apple (us-gaap) y Taiwan Semiconductor (ifrs-full).
