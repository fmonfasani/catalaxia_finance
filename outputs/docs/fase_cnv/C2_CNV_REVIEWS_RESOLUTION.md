# C2 — REVIEWS RESOLUTION REPORT — Golden Case CEPU

Generado: 2026-08-24 21:44 UTC
Objetivo: resolver (o dejar con evidencia) las 5 reviews de identidad abiertas por C1,
usando sondas EN VIVO contra CNV. Sin crear entidades. Sin mutar DB derivada.

## Metodo discriminante descubierto

`GET Empresa/{cuit}` devuelve **HTTP 200 siempre**. Pagina real vs inexistente se distingue por:

| senal | pagina real (CEPU) | pagina inexistente |
|---|---|---|
| bytes | ~2.260.000 | **40.720 identicos** |
| CUIT en el cuerpo | SI | **NO** |
| guids publicview | 1.927 | 0 |

## Resultados por review

| review | estado | evidencia clave |
|---|---|---|
| R-001 PROENER dual-CUIT | OPEN | Ambos CUITS -> shell generica. Dual existe solo en metadata CEPU. Requiere AFIP para cerrar. |
| R-002 Vuelta de Obligado triple-CUIT | OPEN | 3 shells genericas. Grupo display unico con 3 CUITS observados. |
| R-003 CP Renovables / Genoveva II | RESOLVED | Probe del visor de la presentacion mal etiquetada: ["12-2020 - Estados Contables GENO II Legalizados.pdf"] |
| R-004 57+45 filas legacy sin CUIT | PARTIAL | 102 filas BALANCE SUBSIDIARIA mapeadas por sigla via adjuntos del visor (CPR/CVO/TMB/PROENER). CUIT queda NULL, confianza MEDIA. |
| R-005 TGS compartida | OPEN | dim_entity ya tiene TGS (cuit=30657863056); CNV no da perfil propio para 30695541860. Nunca duplicar. |

## Hallazgos estructurales nuevos (H)

1. **H-C2-01**: Las controladas NO tienen perfiles propios en CNV — su identidad es metadata
   embebida en presentaciones de la controlante. Unica fuente: parseo RELAC. del HTML.
2. **H-C2-02**: Existe tercer tipo de relacion `RELAC.: VINCULADA` ademas de CONTROLADA
   (80 filas: DGCE, Gas Cuyana, TMB). El inventario C0 las agrupo juntas;
   C3-prep debe separarlas (impacta grafo de grupo y scope de ratios).
3. **H-C2-03**: `PERIODO BAL.` aparece en titulos RELAC. modernos (ademas de FECH. CIERRE BAL.)
   — input directo para C8.
4. **H-C2-04**: Los visores legacy (formTypeId 1001) exponen el contenido SOLO via nombre de
   adjunto (.doc); ni societyName ni CUIT estan presentes.

## Artefactos

* `C2_CNV_IDENTITY_REVIEWS_V2.csv` — cola con estados previos/nuevos, evidencia y decision.
* `C2_CNV_VALIDATION.json` — checks C2-CNV-001..005.
* Evidencia cruda: `scratchpad/tmp/c2_evidencia.json`, `c2_evidencia2.json`, `c2_visores_siglas.json`.

## Veredicto

**C2 PASS -> READY_FOR_C3_FETCHER**
Condiciones: (a) cerrar R-001/R-002/R-005 necesita fuente externa a CNV; (b) regenerar
inventario separando VINCULADA antes del primer fetch masivo.
