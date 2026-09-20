# F-058 — EL BANCO ADVERSARIO NUEVO TENÍA UN PRODUCTO CARTESIANO SIN FILTRAR

**Detectado:** 2026-09-01, al correr `adversario_ratios.py` (el propio banco
adversario de Fase G, sobre sí mismo)
**Severidad: media** (robustez de la herramienta de auditoría, no del dato)
**Estado: CORREGIDO**

---

## 1. El hallazgo

El ataque A2 (signo de `Equity` invertido) mide el desvío de la identidad
`Activo = Pasivo + Patrimonio` antes y después de corromper el dato, con:

```sql
SELECT abs(v1.value_numeric - (v2.value_numeric+v3.value_numeric))
  FROM derived.fact v1, derived.fact v2, derived.fact v3
 WHERE v1.cik=:cik AND v1.tag='Assets' AND v1.report_period=:per
   AND v2.cik=:cik AND v2.tag='Liabilities' AND v2.report_period=:per
   AND v3.cik=:cik AND v3.tag='Equity' AND v3.report_period=:per
   AND v1.valid_to IS NULL AND v2.valid_to IS NULL AND v3.valid_to IS NULL
```

Sin `NOT is_dimensional`. GGAL desglosa `Assets`/`Liabilities`/`Equity` por
segmento de negocio además del total consolidado: el mismo tag y período
tienen múltiples filas dimensionales. La consulta es un `FROM` con tres
tablas y sin condición de join entre ellas — un producto cartesiano
explícito. Con N filas de cada lado, el resultado es N³.

## 2. Efecto medido

El proceso Python que llama a `docker exec ... psql` capturó un stdout de
**38.6 MB en una sola línea** (`p.stdout.strip()` no separa por filas en
esta función auxiliar) y la conversión posterior `float(a1)` reventó con
`ValueError`, cortando el banco adversario a mitad de camino — antes de
llegar a los ataques A3–A6.

## 3. Por qué es un hallazgo real y no solo un bug de mi propio script

Es la misma familia de error que ya casi apareció en otro lugar de este
ciclo (F-054, F-055: consultas escritas para un universo de una sola
empresa que se rompen al agregar una segunda con datos dimensionales más
ricos). GGAL, con desglose por segmento, es exactamente el tipo de emisor
que expone esta clase de bug — y es la propia auditoría adversaria la que
lo encontró, sobre sí misma, antes de terminar de auditar el sistema. Un
banco adversario que no sobrevive a sus propios datos no puede terminar de
atacar lo que se propuso atacar.

## 4. Corrección aplicada

Se extrajo la consulta a una función (`desvio_identidad()`) que agrega
`NOT is_dimensional` a las tres tablas y el filtro de período principal
(`COALESCE(instant_date,end_date) = report_period`), igual que usan
`ratios_inventario.py` y `audit_provenance_ratios.py` para el mismo
propósito. Además, la función ahora exige que el resultado sea **una sola
fila** — si no lo es, devuelve `None` en vez de asumir la primera, para que
una ambigüedad futura falle de forma visible en vez de silenciosa.

## 5. Verificación

Banco adversario completo tras el fix — ver `PRODUCT_DEMO_GATE.md` §2 y
`outputs/docs/fase_ratios/adversario_ratios.json` para el resultado
ataque por ataque de la corrida final.

## 6. Lección

Una consulta SQL con `FROM a, b, c` (join implícito) sin condición que
relacione las tablas es, por definición, un producto cartesiano. Es
inofensivo cuando cada tabla filtrada devuelve una sola fila — que es lo
que ocurría en YPF, el único emisor usado al escribir la consulta por
primera vez — y una bomba de memoria en cuanto un emisor con más
dimensiones (segmentos, monedas, escenarios) entra en el mismo código. La
regla que ya aplican otros scripts del repo (`NOT is_dimensional` +
filtro de período principal) no es opcional en ninguna consulta nueva sobre
`derived.fact`, ni siquiera en el código de auditoría.
