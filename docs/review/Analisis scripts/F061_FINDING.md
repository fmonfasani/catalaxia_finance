# F-061 — LA CAPA DE RATIOS NO VERIFICA EL ORIGEN NI LA INTEGRIDAD DE LOS FACTS QUE CONSUME

**Detectado:** 2026-09-01, banco adversario de la Fase F del encargo de producto
**Severidad: HIGH** · **Estado: REGISTRADO, NO CORREGIDO** (registrar y no corregir es
lo que pide el encargo salvo que sea necesario para completar una prueba autorizada)

---

## 1. El hallazgo

`scripts/engine/ratios_inventario.py`, `e2e_producto.py` y
`matriz_producto.py` calculan cada ratio leyendo `derived.fact` filtrado por
`cik` y `tag`. Ninguno de los tres verifica que el valor recuperado
efectivamente pertenezca a la empresa, ni que sea internamente consistente
con el resto de sus estados contables. Dos ataques del banco adversario lo
confirman:

### A2 — signo corrupto

Se invirtió el signo de `Equity` de GGAL 2025 (una UPDATE directa, simulando
un error de extracción o un fact corrupto). ROE pasó de `0.027388` a
`-0.027388`: **calculado, con un valor distinto, sin ninguna señal de
error.** El motor no tiene forma de distinguir "el patrimonio bajó" de "el
signo está mal".

### A7 — fact de otra empresa, más severo

Se clonaron los dos operandos de `current_ratio`
(`AssetsCurrent`/`LiabilitiesCurrent`, ambos de AAPL) bajo el CIK de GGAL,
retagueados a `CurrentAssets`/`CurrentLiabilities` (nombres `ifrs-full`,
coherentes con la taxonomía que GGAL declara) y en ARS. GGAL, banco, no
tenía originalmente NINGUNO de los dos tags — el ratio daba
`NO_CALCULABLE`.

Resultado: `current_ratio` de GGAL pasó a **`CALCULADO = 0.893293`** — el
mismo número, dígito por dígito, que el `current_ratio` real de AAPL
(`0.8933`). La fila que un cliente vería "de GGAL" es, en los hechos, el
balance de Apple con otra etiqueta. Nada en el resultado lo delata: es un
número plausible para un `current_ratio`, dentro de rango, sin ninguna
marca.

## 2. Por qué es HIGH y no un hallazgo teórico

El encargo pidió explícitamente atacar "fact perteneciente a otra empresa"
como uno de los diez vectores adversarios. No es un escenario exótico: es
exactamente el tipo de corrupción que **ya ocurrió en este sistema** —
F-054 documenta un incidente real donde un `fact_id` reciclado hizo que
`derived.fact` de YPF apuntara a filas de GGAL. F-054 se corrigió en la capa
de *parsing* (S03/S04). Este hallazgo muestra que, si una corrupción
equivalente ocurriera río abajo de esa capa — o si alguien escribiera
directamente en `derived.fact` sin pasar por el pipeline — **la capa de
ratios no tiene ningún control propio que lo atrape.**

## 3. La mitigación existe, pero no es obligatoria

`audit_provenance_ratios.py` SÍ detecta ambos ataques cuando se ejecuta:
la identidad `Activo = Pasivo + Patrimonio` se rompe con el signo invertido
(A2b, desvío 0% → una magnitud del orden de 2×Equity), y un `current_ratio`
construido con datos 100% ajenos no tiene ningún control cruzado que lo
mire en este momento — un control de identidad contable no verifica
`current_ratio` en sí, así que el ataque A7 **no tiene hoy ningún control
que lo detecte**, ni siquiera el de identidad contable (que solo cubre
Activo=Pasivo+Patrimonio, EPS y margen bruto).

**El problema no es la ausencia total de defensa — es que la defensa que
existe (a) es un script separado, (b) no cubre todos los ratios por igual, y
(c) nada obliga a correrla antes de publicar.**

## 4. Recomendación (no aplicada en este ciclo)

Formalizar que ningún ratio se publique en el screener sin que la
identidad contable del emisor+período correspondiente haya pasado su
control ese mismo día/corrida — ya sugerido en `PRODUCT_DEMO_GATE.md` #4
del ciclo del 2026-09-01, y confirmado aquí con evidencia más directa
(A7 fabrica un resultado incorrecto y plausible, no solo un signo
sospechoso). Ampliar la cobertura de `audit_provenance_ratios.py` más allá
de las tres identidades actuales (Activo=Pasivo+Patrimonio, EPS, margen
bruto) para que cada ratio publicable tenga al menos una verificación
cruzada independiente sería el siguiente paso, pero es trabajo de diseño de
contrato, no una corrección de una línea — no se implementa aquí.

## 5. Lo que esto no es

- No es una corrupción real de la base homologada: el ataque corrió sobre
  una copia descartable (`adversario_ratios_mut`), verificada destruida y
  con la homologada bit a bit idéntica antes y después (control Z).
- No invalida los 60/60 controles de `RATIO_INDEPENDENT_AUDIT.json`: esos
  verifican que el motor reproduce fielmente lo que HAY en `derived.fact`
  hoy, que es correcto. Este hallazgo es sobre qué pasaría si lo que hay en
  `derived.fact` estuviera mal — un escenario distinto, deliberadamente
  fabricado para la prueba.

## 6. Lección

Un motor de cálculo correcto sobre datos correctos no es lo mismo que un
motor robusto ante datos incorrectos. La distinción importa especialmente
acá porque el "dato correcto" de esta arquitectura pasa por varias etapas
(SEC → S02 → S03 → S04 → `derived.fact`) antes de llegar al motor de
ratios, y cada una de esas etapas ya tuvo al menos un incidente real
(F-054, F-055) que movió o mezcló datos entre empresas. La capa de ratios
fue, hasta este ciclo, la única que nunca se sometió a esa misma pregunta.
