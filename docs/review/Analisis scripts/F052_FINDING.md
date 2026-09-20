*# F-052 — LA PROVENANCE DEPENDE DE ARTEFACTOS QUE EL SISTEMA NO CUSTODIA

**Detectado:** 2026-08-31, al reconstruir el RAW mínimo tras el incidente
**Estado: REGISTRADO, NO CORREGIDO** · **Severidad: media** · **No es blocker**

---

## 1. El hallazgo

Las 6 re-afirmaciones de F-041 declaran en `assertion.source_facts` el `sha256` del
`submissions/CIK<n>.json` que las sostiene. Al re-descargar esos 6 archivos con el
fetcher oficial y comparar contra el hash registrado:

```
CIK 0000320193 Apple      f54472c17b26988e…  vs  2503475b32d84986…   DIFIERE
CIK 0000789019 Microsoft  d3e4cdd9cf0dedf6…  vs  ef3d1eed787e1d32…   DIFIERE
CIK 0000931427 TGS        854f2dd1245a8e34…  vs  15556a886f6ddc81…   DIFIERE
CIK 0001045810 NVIDIA     3f7c580a7593ef54…  vs  64a5368efdc842eb…   DIFIERE
CIK 0001114700 GGAL       7bdaf08e4387c335…  vs  f0e4311816fe9916…   DIFIERE
CIK 0001717161 CEPU       10400c2e1bae7806…  vs  32b72984aa3e8f01…   DIFIERE

0/6 byte-identicos
```

## 2. Por qué difieren — y por qué no es corrupción

`data.sec.gov/submissions/CIK<n>.json` es un **recurso vivo**: contiene la lista de
presentaciones del emisor, y **cambia cada vez que la empresa presenta algo**. Entre el
28 y el 31 de agosto los seis se actualizaron.

El hash hizo exactamente lo que debe: **detectar que el contenido cambió**.

## 3. El defecto real

El sistema **registra el hash del artefacto pero no custodia el artefacto**.

Los artefactos vivían en `data/raw/`, que:
- no está versionado (correcto: son datos, no código);
- no tiene respaldo, snapshot ni retención;
- no tiene ninguna garantía de inmutabilidad.

Combinado con una fuente mutable, el resultado es que **la provenance caduca**: la
assertion cita un `sha256` que ya no puede reproducirse desde ninguna parte.

> Un hash prueba «el archivo que leí era éste». Sin el archivo archivado y con una
> fuente que cambia, esa afirmación pasa de **verificable** a **no verificable** — y
> el momento en que ocurre no lo controla el sistema.

## 4. Alcance medido

| tipo de artefacto | ¿fuente mutable? | ¿verificable hoy? |
|---|---|---|
| `submissions/CIK<n>.json` | **sí** — cambia con cada filing | **no** (0/6) |
| `company_tickers.json` | **sí** — 10.403 filas el 23/08, **10.391** el 31/08 | no |
| filings de EDGAR (`Archives/`) | **no** — un accession es inmutable | sí, si se re-descarga |
| `history.csv` de Market | **sí** — la serie crece cada rueda | no |
| RAW de CNV | parcialmente | no |

**El caso favorable son los filings**: un accession publicado no cambia. Por eso S03
sí puede reproducirse re-descargando, y `submissions` no.

## 5. Lo que NO es

- **No invalida los datos persistidos.** `parsed.facts`, `derived.fact` e
  `identity_v1` conservan lo extraído, con su fuente, cita y autor.
- **No es corrupción ni pérdida en la base**: PostgreSQL sigue con DELTA = 0.
- **No es un defecto introducido** por F-050 ni F-051.
- **No lo causó el incidente.** El incidente lo *reveló*: aunque `data/raw` no se
  hubiera borrado, esos 6 hashes habrían dejado de coincidir igual, porque la fuente
  cambió. El borrado sólo adelantó el descubrimiento.

## 6. Lo que sí es

Una **limitación estructural del modelo de provenance**: se ancla en el hash de un
artefacto que el sistema no garantiza conservar, y para fuentes mutables eso convierte
la evidencia en no reproducible con el paso del tiempo.

## 7. Correcciones posibles (ninguna aplicada)

1. **Archivar el artefacto junto con el hash** — almacenamiento inmutable
   (content-addressed) para todo artefacto citado por una assertion `VERIFIED`. Es lo
   que el `sha256_index.jsonl` de CNV insinuaba y que nunca se generalizó.
2. **Distinguir fuentes mutables de inmutables en `source`**, y exigir archivado sólo
   para las mutables.
3. **Aceptar la caducidad y declararla**: registrar `valid_as_of` junto al hash, de modo
   que la assertion diga «esto era cierto en esta fecha» en vez de «esto se verifica
   contra este archivo».

La 1 es la única que preserva la promesa actual. La 3 es la más honesta si no se quiere
pagar el almacenamiento.

**Requiere decisión de producto.** No se corrige en este ciclo.
