# C0 — Formatos de informacion CNV (2026-08-24 01:31 UTC)

CNV expone DOS generaciones tecnicas conviviendo. Un parser unico no alcanza: hace falta
una cadena de parsers seleccionada por formato detectado.

## Generacion MODERNA — formTypeId 147 "Estados Contables - NIIF"

* Visor con **datos financieros inline** (sin descargar nada): ~90 codigos contables distintos
  por presentacion (rango [1-8]xxxxxx), valores `-12345.67`, unidad `Miles de $`,
  `FechaCierre`, `TipoBalance`.
* Es la MISMA estructura que ya parsea `job5_v2_extract_eeff.py` en el resto del universo
  (mapa CODIGOS de 50 conceptos + RATIOS_CNV).
* Adjuntos tipicos por presentacion (5): EEFF legalizado (20 MB), informe auditor independiente,
  acta organo de fiscalizacion, memoria/"No corresponde", resena informatica.
* Provenance maximo posible: codigo+rubro+valor -> tabla/celda del visor -> GUID presentacion
  -> presentationId -> CUIT -> URL -> SHA256 del HTML -> run_id.

## Generacion LEGACY — formTypeId 1001 "Balance Consolidado - Migracion" (pre-2018 aprox.)

* Sin inline codes (solo 1 falso positivo por timestamps). Todo el contenido esta en el ADJUNTO
  (.doc/.pdf legalizado). `FechaCierre`/`UnidadMedida` ausentes en el visor: viven en el documento.
* Requiere pipeline documental (descarga blob -> parser doc/pdf). OCR solo como fallback si el
  .doc/.pdf no tiene capa de texto.

## Otros formatos presentes en el perfil CEPU

| tipo | formato | utilidad financiera |
|---|---|---|
| Hechos relevantes (1007 y modernos) | texto + adjunto PDF | eventos (ON, pagos, fusiones) |
| Informes trimestrales ON | adjunto | deuda financiera detalle |
| Actas que aprueban EECC | adjunto | cross-check fechas de aprobacion |
| EEFF de controladas (135) | mismo esquema EEFF | analisis de grupo (bonus, no ratio directo) |

## Regla de seleccion de parser (para C6)

```
formTypeId==147  -> parser inline del visor (estructurado, prioridad 1) + adjuntos como RAW complementario
formTypeId==1001 u otros legacy -> descarga adjunto -> parser doc/pdf (fallback OCR solo si no hay capa texto)
otros formTypes  -> inventario + RAW, sin parsing financiero
```

## Codigos inline observados (muestra CEPU 2026-06-30 consolidado)

~90 codigos distintos incluyendo el mapa conocido (1999999 Assets, 3000100 Revenue,
3049999 NetIncome, 8000004 EBITDA...) mas rubros no mapeados (intereses minoritarios 2211300,
PN ejercicio anterior 8000002, etc.) — inventario completo se hara en C7 sobre todos los 147.
