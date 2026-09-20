# Diagnóstico del repositorio — previo a FACTORY-SPEC.md

**Fecha**: 2026-09-09. **Método**: inspección directa del filesystem (`find`/`ls`/
`grep`/lectura de archivos), sin asumir nada por nombre de archivo o carpeta. Ningún
archivo existente fue eliminado, movido, fusionado ni reemplazado.

## Estructura de primer nivel (VERIFICADO POR CÓDIGO — listado directo)

```
api/            backend/         data/            docs/
engine/         migrations/      nginx/           outputs/
public/         scripts/         sql/             tests/
software-factory/ (nuevo, esta sesión)
.claude/        .github/         .opencode/       .vscode/
```

## Componentes del ETL / Harness financiero (VERIFICADO POR CÓDIGO)

- **`engine/`**: motor del pipeline financiero — `identity.py`/`identity_v1.py`,
  `db.py`, `config.py`, `hashout.py`, `manifest.yaml` (define stages S00–S04+), lógica
  de checkpoints propia del programa financiero.
- **`scripts/engine/`**: scripts de etapa (`s00_smoke.py`...`s04_normalize.py`,
  `c3_cnv_fetch.py`, `f049_bench.py`, `identity_v1_pilot.py` y variantes).
- **`scripts/market/`**: workstream Market Data (M0–M23), con su propio harness de
  checkpoint/resume (`m6_scale.py`, `market_db.py`) y contrato de identidad
  (`f014_venue_ticker.py`) — construido en sesiones previas de este mismo hilo de
  trabajo, documentado en `outputs/docs/fase_market/`.
- **`scripts/pipeline/`**, **`scripts/tickets/cnv/`**, **`scripts/dolares/`**: pipeline
  legado del screener, jobs de extracción CNV, fetchers de dólar.
- **`api/`**, **`backend/`**: servicio FastAPI y calculadoras/fetchers del producto.
- **`docs/architecture/`**: 27 documentos, todos contratos/gates del dominio
  financiero (F024/F037/F038/F039/F040/F041/F044/F045/F050/F051, IDENTITY_*,
  HASH_OUT_CONTRACT, MIGRATIONS_CONTRACT, S04_CONTRACT, SYSTEM_HOMOLOGATION_*). Cero
  documentos genéricos de agentes/SDD/orquestación.
- **`docs/review/FINDINGS.md`**: bitácora de un auditor independiente ("CIAA") sobre
  el programa financiero — findings con `severity`/`workstream`/`status`/
  `acceptance_test`, cerrados solo contra evidencia, nunca por declaración del owner.
  Patrón de gobierno real, ya en uso, exclusivo del ETL.
- **`.claude/state/`, `.claude/context/`**: archivos de continuidad por workstream
  (SEC/CNV/MARKET/Identity/Auditor) — mecanismo de estado ad-hoc basado en Markdown,
  no una State Machine ni un Shared State estructurado.

## El Harness arquitectónico — hallazgo central de esta inspección

**`.github/ARCHITECTURE_HARNESS.md.txt`** (VERIFICADO POR CÓDIGO, leído completo) es
un documento normativo — "ARCHITECTURE HARNESS — BYMAStocks" — que define:

- 12 CAPAS financieras (FUENTES→IDENTIDAD→RAW→PARSED→NORMALIZED→ECONOMIC FACTS→
  FINANCIAL MODEL→RATIOS→PROVENANCE→VALIDACIÓN→CERTIFICACIÓN→PUBLICACIÓN), cada una
  con `Responsabilidad`/`Puede`/`No puede` explícitos.
- 4 PLANOS de análisis (DATOS/CONTROL/EJECUCIÓN/INFRAESTRUCTURA).
- Un CICLO DE GARANTÍA (DEFINIR→IMPLEMENTAR→VERIFICAR→CERTIFICAR).
- Categorías de EVIDENCIA: `VERIFICADO POR CÓDIGO` / `VERIFICADO POR TEST` /
  `VERIFICADO POR EJECUCIÓN` / `NO DETERMINABLE` — **exactamente el vocabulario que el
  pedido de esta tarea exige usar**, confirmando que no es una convención nueva sino
  una ya establecida en este repositorio.
- 15 invariantes globales (I-001..I-015: RAW inmutable, SHA verificado, identidad
  obligatoria, determinismo, idempotencia, no mezclar períodos/unidades,
  NOT_CALCULABLE explícito, trazabilidad hasta RAW, nunca modificar producción sin
  autorización).
- Reglas de falla (`PASS`/`WARNING`/`BLOCK`/`NOT_CALCULABLE`/`NO DETERMINABLE`) y
  reglas de conflicto (nunca resolver una contradicción en silencio).

**Existen dos copias adicionales, idénticas y truncadas**, del *gate* de invocación de
este Harness: `.claude/CLAUDE.md.txt` y `.claude/INRTUCTIONS.md.txt` (ambas con
extensión `.txt`, por lo tanto **no activas** como instrucción automática — verificado
por ausencia real en el system prompt de esta sesión). Clasificación: **VERIFICADO POR
CÓDIGO que el archivo existe; VERIFICADO POR EJECUCIÓN que NO está activo hoy** (esta
misma sesión no lo recibió como instrucción del sistema).

**Implicancia para la Factory**: el Harness es normativo *para el dominio financiero*,
no para software en general. Su patrón de gobierno (capas con responsabilidad
exclusiva, planos, evidencia obligatoria, invariantes) es genuinamente reutilizable
como *inspiración de diseño* para la disciplina interna de la Factory — y así se usó
en `FACTORY-SPEC.md` §0, §12 — pero la Factory no debe importarlo como dependencia ni
asumir sus 12 capas financieras como propias.

## Componentes de tipo "agente"/"skill" (VERIFICADO POR CÓDIGO — dos ecosistemas duplicados)

- **`.claude/agents/`**: `data-gatherer.md`, `hat-black.md`, `hat-green.md`,
  `hat-red.md`, `hat-white.md`, `hat-yellow.md` — definiciones de subagente para
  Claude Code.
- **`.opencode/skills/`**: mismo conjunto conceptual (`catalaxia-filosofia`,
  `data-gatherer`, `hat-black/green/red/white/yellow`, `plan`, `six-hats-plan`) para
  la herramienta OpenCode (tiene su propio `node_modules`, es una instalación de CLI
  separada, no parte del código del proyecto).
- **`.claude/skills/six-hats-plan/`**: la misma técnica ("seis sombreros de Bono")
  como skill de Claude Code.

**Qué son realmente** (verificado leyendo su descripción): generan preguntas de un
ángulo fijo (riesgo/intuición/hechos/beneficio/alternativas) sobre datos crudos de un
proyecto, para asistir una sesión de planificación humana. **No son** un Classifier,
Generator, Validator, Reviewer ni Coordinator — no producen código, no validan nada,
no tienen noción de Contract ni de Pipeline SDD. Son una ayuda de ideación, anterior y
ortogonal a la Factory descripta en esta especificación.

## Búsquedas específicas, con resultado negativo (VERIFICADO POR CÓDIGO — ausencia confirmada)

| Concepto buscado | Resultado |
|---|---|
| Motor SDD (Requirement→Spec→...→Delivery) | No existe |
| Coordinator / Agent Registry genérico | No existe |
| Contracts-as-code (motor genérico, no docs de dominio) | No existe — los "contratos" existentes son documentos Markdown específicos del ETL |
| State Machine genérica | No existe — el "estado" actual son archivos Markdown de continuidad por workstream |
| Reuse Engine / Blueprint / Component Catalog | No existe |
| Configuración MCP a nivel de repositorio (`.mcp.json`) | No existe — los servidores MCP disponibles en esta sesión están configurados del lado del cliente, no del proyecto |
| `CLAUDE.md` activo en la raíz | No existe (solo las copias `.txt` inactivas mencionadas arriba) |

## Clasificación final de la inspección

| Afirmación | Clasificación |
|---|---|
| El repositorio tiene un Harness financiero de 12 capas, documentado y normativo | VERIFICADO POR CÓDIGO |
| Ese Harness está activo como instrucción automática hoy | NO — verificado por ejecución (ausente del system prompt de esta sesión) |
| Existen dos ecosistemas de skills de planificación (hats) | VERIFICADO POR CÓDIGO |
| Esos skills equivalen a un sistema SDD/agentes de generación de código | FALSO — verificado por lectura de su contenido |
| Existe algún componente reutilizable *como código* para el Kernel/Coordinator/Agents de la Factory | NO DETERMINABLE — no se encontró ninguno, pero tampoco se puede probar una ausencia total sin exhaustividad imposible en un repo de este tamaño |
| La ubicación `software-factory/` en la raíz es viable sin colisión | VERIFICADO POR CÓDIGO (no existía el nombre antes de esta sesión; no colisiona con ningún directorio de primer nivel) |

## Ubicación propuesta — justificación

`software-factory/` como directorio de primer nivel, hermano de `engine/`, `scripts/`,
`docs/`, `api/`. Razones:

1. Es exactamente la ubicación que se pidió, y la inspección no encontró ningún motivo
   para proponer otra dentro del mismo repositorio.
2. Separación física inmediata y visible del ETL — nadie que navegue el repo confunde
   `software-factory/` con parte del pipeline financiero.
3. No colisiona con ninguna convención existente (`scripts/` ya tiene sub-namespaces
   por workstream — `engine/`, `market/`, `pipeline/`, `tickets/`, `dolares/` — meter
   la Factory ahí la habría hecho ver como "un workstream más" del ETL, exactamente lo
   que el pedido prohíbe).
4. Alternativa descartada: un repositorio separado. Es arquitectónicamente más
   limpia a largo plazo (independencia total, versionado propio, sin riesgo de que un
   cambio del Kernel toque accidentalmente algo del ETL por estar en el mismo working
   tree) — pero el pedido fue explícito ("dentro del mismo repositorio"), así que no
   se propone como alternativa activa, solo se deja registrada por si se reconsidera
   más adelante.

## Qué NO se modificó

Ningún archivo fuera de `software-factory/` fue creado, editado, movido ni eliminado
en esta sesión. No se tocó `engine/`, `scripts/`, `api/`, `backend/`, `docs/`,
`migrations/`, `.claude/`, `.github/`, `.opencode/`, ni ningún dato.
