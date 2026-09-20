# ANEXO B · DIAGRAMAS DE REFERENCIA DEL PROYECTO

Los diagramas oficiales del proyecto viven en `docs/diagramas/`. Este anexo cataloga
los que aplican a los temas que explica el manual (arquitectura, pipelines, procesos
y flujos), dice **dónde se usa cada uno dentro de las Partes** y reproduce los que no
se insertaron en línea para no repetir figuras.

> **Regla:** si hay que actualizar un diagrama, se edita el archivo fuente en
> `docs/diagramas/` y se recopia sobre `docs/manual/images/` — nunca se edita la
> copia del manual.

## Catálogo de diagramas

| Archivo fuente | Figura en el manual | Qué cubre |
|---|---|---|
| `pipeline_diagrama1.png` | Figura 3 · Parte I §3 | Vista esquemática del E2E del pipeline |
| `Arquitectura_diagramas.png` | Figura 1 · Parte I §1 | Arquitectura general del sistema |
| `Diagramas + Arquitectura.png` | Figura 6 · este anexo | Conjunto amplio de diagramas con vista de arquitectura |
| `diagramas.png` | Figura 4 · Parte I §6 | Vista general de diagramas del proyecto |
| `estilos_pipeline, arquitecura_flujos.png` | Figura 2 · Parte I §2 | Estilos de pipeline y flujos (la partición del alcance en dos) |
| `Plataforma.png` | Figura 7 · este anexo | La plataforma como sistema completo |
| `Procedimientos operativos.png` | Figura 8 · este anexo | Procedimientos operativos del proyecto |
| `procedimientos.png` | Figura 9 · este anexo | Procedimientos — vista de referencia |
| `Tapa e indice.png` | Figura 10 · este anexo | Tapa e índice originales — base de la estética del manual |

Las figuras 1 a 4 están insertadas en la **Parte I** en el punto donde se explica el
tema correspondiente (ver el mapa de la Parte I §6). Las figuras 5 a 10 están abajo.

## Figura 5 — Estética de portada (referencia)

![Figura 5 · Tapa e índice — base de la estética del manual](images/tapa_indice.png)

La portada de este manual usa la misma estética: **navy oscuro (#0B2039) sobre
blanco**, títulos en negro/navy, cuerpo gris y acentos azul/naranja. Paleta
dominante extraída de la tapa:

| Rol | Color |
|---|---|
| Tapa / fondo oscuro | `#0B2039` / `#112842` |
| Fondo claro | blanco / `#F2F4F6` |
| Acento texto secundario | `#7B899A` |

## Figura 6 — Conjunto de diagramas y arquitectura

![Figura 6 · Diagramas y arquitectura — vista amplia](images/diagramas_arquitectura.png)

## Figura 7 — La plataforma como sistema

![Figura 7 · Plataforma](images/plataforma.png)

## Figura 8 — Procedimientos operativos

![Figura 8 · Procedimientos operativos](images/procedimientos_operativos.png)

## Figura 9 — Procedimientos (vista de referencia)

![Figura 9 · Procedimientos — vista de referencia](images/procedimientos_v2.png)

## Cómo se lee este anexo

Cada figura del manual se cita con su número (Figura N). Cuando un capítulo vuelve a
tratar el mismo tema sin repetir la imagen, referencia la figura con su número en
lugar de duplicarla:

> **Ejemplo:** la Parte IX (CNV) explica los tres tramos con la Figura 2 de contexto
> de pipelines y no reinserta la imagen.

> **Nota:** en `docs/diagramas/` hay más materiales de referencia (biblioteca de
> diagramas, diseño general, capturas de pantalla). Se agregan al manual cuando su
> tema tenga capítulo/solución — no antes.