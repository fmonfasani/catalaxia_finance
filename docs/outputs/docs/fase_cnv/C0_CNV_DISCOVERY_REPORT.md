# C0 — CNV DISCOVERY REPORT — Golden Case CEPU

Generado: 2026-08-24 01:31 UTC
Alcance: SOLO discovery. No se implemento C1+. Se descargaron: 1 pagina empresa,
25 visores de muestra y 1 adjunto de prueba. Nada mas.

---

## 1. ¿Como descubrimos las presentaciones?

UNA sola request publica: `GET https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/33650305499`
(HTML server-side 2.26 MB). Contiene TODAS las presentaciones del perfil con fecha, titulo,
presentationId y GUID. Sin auth, sin API oculta necesaria.

## 2. ¿Como obtenemos su metadata?

Tres niveles, en orden de costo creciente:
1. **Titulo estructurado en la pagina empresa** (0 requests extra): para EEFF trae
   NORMA CONTABLE / TIPO BALANCE / PERIODICIDAD / FECHA CIERRE. Resuelve scope y periodo
   SIN abrir el visor.
2. **Visor AIF2** (~53 KB por presentacion): `formTypeId`, `formTypeName`, `presentationIdGlobal`,
   XML `modeloDatos` con `claveinformativa` (codigos C####), `UnidadMedida`, `FechaCierre`,
   y bloques JSON de adjuntos con nombre/tamaño/guid/hash.
3. **Adjuntos** (flujo ValetKey): documento legalizado completo.

## 3. ¿Como identificamos un EEFF?

`formTypeId==147` ("Estados Contables - NIIF") o titulo que empieza con `NORMA CONTABLE:`.
Legacy: `formTypeId==1001` "Balance Consolidado - Migracion" o titulos `BALANCE CONSOLIDADO - CPSA ...`.

## 4. ¿Consolidado vs individual?

Campo explicito `TIPO BALANCE: CONSOLIDADO|INDIVIDUAL` en el titulo (pagina empresa) y en el
XML del visor. Nunca inferir por el adjunto. CEPU: 132 consolidados / 17 individuales.

## 5. ¿Anual vs trimestral?

`PERIODICIDAD: ANUAL|SEMESTRAL|TRIMESTRAL` (o digito 1/3 en formato nuevo) + `FECHA CIERRE`
exacta. Los legacy no declaran periodicidad: se deduce de la fecha de cierre y se marca UNKNOWN.

## 6. ¿Como obtenemos un attachment?

VERIFICADO END-TO-END:
```
GET  aif2.cnv.gov.ar/api/ValetKeyProvider/GetPublicValetKey/{guid}?operation=DownloadBlob  -> valetKeyData
POST blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/{guid}  (form ValetKey=..., header X-CSRF-TOKEN)
```
Test: EEFF Final Legalizado 06-2026 -> 22.347.603 bytes, PDF valido.

## 7. ¿Que formatos existen?

Dos generaciones (detalle en C0_CNV_FORMATS.md): moderna 147 con datos inline estructurados
(~90 codigos por presentacion, unidad, fecha) y legacy 1001 con todo dentro del adjunto.
Hechos relevantes, actas, ON: adjuntos/informativos.

## 8. ¿Que historial tiene CEPU?

* Presentaciones totales: **1860 GUIDs unicos** (1927 filas; 64 repetidas por seccion "Ultima Informacion Recibida").
* **EEFF propios: 149** — 132 CONSOLIDADO + 17 INDIVIDUAL, todos NIIF salvo legacy.
* Rango de cierres EEFF propio: **2004 .. ?** (anios: 2004, 2005, 2008, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, ?).
* Anuales declarados: 30 · Trimestrales declarados: 83 · Semestrales: 4 · Sin declarar (legacy): 35.
* Consolidados desde 2020H2 (ventana 6 anios): **72** · ventana 10 anios: **100**.
* EEFF de CONTROLADAS publicados bajo CEPU: 135 (23 entidades: Vuelta de Obligado, Proener, TMB, Genoveva, DGCE...).
* Hechos relevantes: 541. Actas aprobando EECC: 57. Informes trimestrales ON: 19. Otros: 1.026.

## 9. ¿Que necesitamos para 5/6 anos?

Minimo para los 13 ratios: los **72 EEFF consolidados NIIF (147)** de la ventana
+ sus adjuntos de auditor (informe auditor) como evidencia. Los individuales se fetcherian solo
si S04 decide scope INDIVIDUAL para alguna metrica. Legacy 1001 NO aporta a ratios (pre-NIIF,
sin inline) y queda para fase historica opcional.

## 10. Potencial para los 13 ratios

| ratio | input CNV candidato | disponible? |
|---|---|---|
| PER / EPS anual / CAGR EPS | EPS_basico 8000000 / EPS_diluido 8000001 (inline 147) | SI (4 presentaciones 147 verificadas con ~90 codigos inline) |
| Deuda/EBITDA | DebtCurrent 2322200 + DebtNonCurrent 2312300 + EBITDA 8000004 directo | SI (inline) |
| Margen neto | NetIncome 3049999 / Revenue 3000100 | SI |
| ROE 5y | NetIncome + Equity 2299999 (+ PN ejercicio anterior 8000002 no mapeado aun) | SI con mapeo extendido |
| FCF/Cap | CF_Operativo 3241100 - CF_Inversion 3241200 (scope: flujo total inversion, NO CapEx puro) | PARCIAL — semantica distinta a EDGAR CapEx |
| Payout | cnv_dividendos form 339 / hechos relevantes de pago | PARCIAL (fuera de EEFF) |
| Precio USD, Max/Min 52w, dif | NO EXISTE EN CNV | NO — requiere fuente externa (precios/FX) |

## 11. Gaps y riesgos

1. **Hash CNV ≠ hash del archivo servido** (C0-CNV-006): definir en C3 doble-hash + no usar hash CNV para idempotencia.
2. Legacy 1001 (0+ presentaciones migradas) sin inline: requiere descarga documental; FECHAS ausentes en visor (estan en el documento).
3. `UriArchivo` del JSON apunta a host interno desa-iis: ignorar siempre; usar blob.cnv.gov.ar publico.
4. Duplicados benignos por seccion: deduplicar por GUID conservando ambas ubicaciones como provenance.
5. Periodicidad textual vs digito (TRIMESTRAL vs 3): normalizar en C8.
6. EEFF de controladas mezclados en el perfil: filtrar SIEMPRE por `RELAC.:` antes de considerar EEFF propio.
7. Rate: visores tardan 2-5 s; fetch masivo de ~150 visores EEFF ~ 5-10 min con delay 0.5 s. Adjuntos grandes (20 MB): presupuesto de ancho de banda y backoff.
8. Sin API JSON de listado: cualquier cambio del HTML de la pagina empresa rompe el parser de discovery -> check de estructura en cada run.

## 12. ¿Que se generaliza al universo CNV?

TODO el mecanismo es por-CUIT y sin excepciones CEPU: pagina empresa -> inventario -> visor ->
ValetKey/blob. La unica variabilidad esperada entre empresas: mix de formTypeIds (bancos usaran
otros formularios), presencia de legacy, y periodicidad irregular (CELU/LEDE mayo, CAPX abril).
La arquitectura ya contempla fiscal-year no calendario (principio Catalaxia #6).

---

## Arquitectura descubierta (resumen)

```
www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{CUIT}          -> INVENTARIO + METADATA basica (1 request)
        └── aif2.cnv.gov.ar/presentations/publicview/{GUID}  -> METADATA fina + DATOS INLINE (147)
                ├── modeloDatos XML: claveinformativa, UnidadMedida, FechaCierre
                ├── Adjuntos JSON: nombre, tamano, guid, hash CNV
                └── /api/ValetKeyProvider/GetPublicValetKey/{blobGuid}?operation=DownloadBlob
                        └── POST blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/{blobGuid}  -> RAW binario
```

## Estrategia FETCH recomendada (para C3)

1. Pagina empresa: 1 request por run; diff de GUIDs contra inventario previo (nuevos/muertos).
2. Visores: SOLO clases financieras (EEFF propio/controlada + informes ON), delay 0.5-1 s, retries x3 backoff, SHA256 por HTML, idempotencia por (guid, sha256).
3. Adjuntos: primero los de EEFF ventana 6 anos; ValetKey fresca por descarga (expiran), POST con CSRF del visor correspondiente; guardar ambos hashes.
4. Estados: DOWNLOADED / SIN_CAMBIOS / FAILED / NOT_FOUND / BLOCKED / SKIPPED.

## VEREDICTO

**C0 PASS -> READY_FOR_C1**

Condicion registrada: C0-CNV-006 (hash mismatch) pasa como WARN con accion definida para C3.
