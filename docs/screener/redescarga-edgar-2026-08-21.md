# Re-descarga de EDGAR — 2026-08-21

Qué se corrió, qué cambió y por qué el atraso de los ADR argentinos **no se
arregla re-descargando**.

## Resultado en una línea

De las 35 empresas re-descargadas, **avanzaron 3, todas de EE.UU.**. Las 31 ADR
—las que motivaron el trabajo— no avanzaron ni un día, y no por un error del
pipeline: **la API de la SEC de la que se leen los datos no tiene sus balances
2025**.

## Lo que se corrió

    python scripts/tickets/sec_edgar/scripts/construir_base.py adr      # 34 -> 31 rebajadas
    python scripts/tickets/sec_edgar/scripts/construir_base.py sp500    # 500 -> 4 rebajadas + 1 nueva

`sp500`, no `us`: **`us` no es un modo válido**. `universo_objetivo()` sólo
reconoce `sp500` y `latam`, y cualquier otra cosa cae en el default, que es el
universo ADR. Correr `us` habría vuelto a bajar las ADR creyendo que bajaba el
S&P 500.

La decisión de qué rebajar reprodujo exactamente lo documentado: sobre las 8.077
filas de `empresas`, **554 se saltean y 55 se rebajan**. `adr` y `sp500` cubren
35 de esas 55; las 20 restantes caen fuera de los dos universos (`latam`).

## Medición contra el estado previo

Base: `data/redescarga/baseline_facts_20260821-2138.csv` (609 CIK, 4.605.617
filas) y respaldo completo en la tabla `facts_pre_redescarga`.

| | |
|---|---|
| CIK que **avanzaron** su `period_end` | **3** — TAP `2025-12-31 → 2026-06-30`, CAH `2025-12-31 → 2026-06-30`, FISV `2026-03-31 → 2026-06-30` |
| CIK que **retrocedieron** | **0** |
| CIK desaparecidos | **0** |
| filas | 4.605.617 → 4.604.484 (**−1.133**) |

**Las 1.133 filas de menos no son pérdida.** Por período: −2.491 en
`2020-06-30`, +463 en `2025-06-30`, +128 en `2025-12-31`, +113 en `2024-06-30`.
`CUTOFF` es una ventana móvil de 6 años (`hoy − 6 años` = 2020-08-23), así que
el trimestre más viejo se cae por diseño mientras entran los nuevos. El saldo es
negativo sólo porque lo que se cae es más que lo que entra.

## Por qué las ADR no avanzan

El pipeline lee los hechos de un solo lugar:
`data.sec.gov/api/xbrl/companyfacts/CIK*.json`. Para estos emisores extranjeros,
ese endpoint **se quedó en el 20-F del ejercicio 2024, presentado en abril de
2025**:

| | último `filed` en companyfacts | 20-F del ejercicio 2025 que SÍ está en EDGAR |
|---|---|---|
| BBAR | 2025-04-04 | **2026-04-09** (`reportDate` 2025-12-31) |
| SUPV | 2025-04-21 | **2026-04-08** |
| TGS  | 2025-04-24 | **2026-04-22** |
| LOMA | 2025-04-29 | **2026-04-28** |
| YPF  | — | **2026-03-26** |

El dato existe y es legible por máquina: la presentación de BBAR
(`0001628280-26-024441`) trae su XBRL completo —`bbar-20251231_htm.xml` más las
linkbases— entre sus 238 archivos. Lo que falla es que **companyfacts no lo
ingirió**, y ese es el único sitio del que el pipeline lee.

Verificado hoy contra la red, no contra el caché.

## Dos cosas que se arreglaron en el camino

**1. Había un segundo caché, en disco.** `_caducidad` decidía bien qué empresa
estaba atrasada, pero `descargar_empresa()` seguía leyendo
`data/raw/companyfacts/*.json` —556 archivos del 25-jun y 09-jul— y
`get_json_cache()` no tiene vencimiento. La corrida habría re-insertado el mismo
dato viejo y **habría parecido exitosa sin traer una sola fila nueva**. Eran dos
cachés en serie y el arreglo anterior destapó sólo el primero. Corregido en
`05588eb`: la empresa marcada `rebajada` se baja con `forzar=True`, que ignora el
JSON del disco y lo reescribe; si la red falla se cae al caché en vez de
devolver `None`, porque el re-insert hace `DELETE FROM facts WHERE cik=?` antes.

**2. `hay_que_rebajar()` sobre-dispara con los 6-K.** Toma cualquier 6-K como
prueba de que hay estados contables nuevos, y para estos emisores la mayoría de
los 6-K son comunicados sin XBRL: BBAR presentó 23 en lo que va de 2026 y
ninguno aportó un hecho. Por eso marcó 31 ADR para rebajar y ninguna tenía nada
que traer. La regla es barata y conservadora —ante la duda baja— pero mientras
la fuente sea companyfacts va a seguir pidiendo 31 descargas inútiles por
corrida.

## Lo que hay que decidir

Para que estos papeles tengan su ejercicio 2025 hay que **leer el XBRL de la
presentación**, no el resumen de companyfacts: bajar el instance document desde
`https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/` y parsearlo. Es un
extractor nuevo, no un ajuste del que hay.

Alternativa más barata si sólo interesan los papeles argentinos: para BBAR,
SUPV, TGS, LOMA y compañía, la CNV ya publica los mismos estados y el pipeline
**ya sabe leer la CNV**. El 20-F sirve para la serie en dólares; la CNV, para la
frescura.

## Cómo deshacerlo

    -- vuelve `facts` al estado del 2026-08-21 21:38
    DELETE FROM facts;
    INSERT INTO facts SELECT * FROM facts_pre_redescarga;

`facts_pre_redescarga` ocupa 573 MB (la base pasó de 904 MB a 1.477 MB). Se
puede borrar con `DROP TABLE` cuando ya no haga falta, seguido de `VACUUM` para
recuperar el espacio.
