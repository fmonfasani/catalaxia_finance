# FACTORY-SPEC — Especificación Normativa de la Software Factory

**Estado**: OBJETIVO (diseño). Ningún componente descrito aquí tiene Kernel, Coordinator
o Agentes implementados todavía. **Versión**: 0.1.0. **No modifica** el ETL financiero
ni su Harness (`.github/ARCHITECTURE_HARNESS.md.txt`).

---

## 0 · Diagnóstico previo (resumen — detalle completo en el informe adjunto)

Antes de escribir esta especificación se inspeccionó el repositorio completo. Hallazgo
central: **ya existe un Harness arquitectónico**, pero es específico del dominio
financiero — `.github/ARCHITECTURE_HARNESS.md.txt` ("ARCHITECTURE HARNESS —
BYMAStocks"), que define 12 capas (FUENTES→...→PUBLICACIÓN), 4 planos, un ciclo de
garantía (DEFINIR→IMPLEMENTAR→VERIFICAR→CERTIFICAR), categorías de evidencia
(VERIFICADO POR CÓDIGO/TEST/EJECUCIÓN/NO DETERMINABLE) e invariantes globales
(I-001..I-015). **Ese documento es la razón por la que esta especificación usa el mismo
vocabulario de evidencia** — no porque la Factory dependa de él, sino porque es un
patrón de gobierno ya probado en este repositorio que vale la pena reutilizar
*conceptualmente* en un dominio distinto. Ver §16 (Reutilización) para el detalle de
qué se toma prestado y qué no.

No se encontró: un motor SDD, un Coordinator, un Agent Registry, un motor de Contracts,
una State Machine genérica, un Reuse Engine, un Blueprint/Component Catalog, ni
configuración de MCP a nivel de repositorio. Sí se encontraron dos ecosistemas de
skills de planificación/brainstorming ("six thinking hats") duplicados en `.claude/` y
`.opencode/` — son ayudas de ideación, no un sistema de generación de software.

---

## 1 · Propósito

La Software Factory es un sistema que transforma un **Requirement** en **software
ejecutable, validado y entregado**, atravesando obligatoriamente:

```
Requirement → Specification → Architecture → Contracts → Invariants → Evals
  → Plan → Tasks → Code → Validation → Review → Delivery
```

Ninguna etapa puede saltearse. Ninguna etapa se considera completa sin evidencia (§12).
El software que la Factory produce puede, eventualmente, ser Catalaxia mismo (su API,
su dashboard, nuevas capacidades) — pero la Factory no depende estructuralmente de
Catalaxia para existir ni para operar sobre otros proyectos.

## 2 · Principios

1. **El LLM no controla el sistema. El sistema controla al LLM.** Un modelo de lenguaje
   ejecuta responsabilidades delimitadas dentro de un Agent; nunca decide por sí mismo
   qué etapa del pipeline sigue, qué Contract aplica, ni si una entrega está aprobada.
2. **SDD define el software.** El código es una consecuencia de la especificación, no
   al revés. Si el código y la especificación difieren, es una discrepancia a resolver,
   nunca una fuente de verdad tácita.
3. **Los Agents ejecutan responsabilidades delimitadas.** Un Agent declara su
   `PRIMARY_RESPONSIBILITY`, sus `INPUTS`, sus `OUTPUTS` y sus `NON_RESPONSIBILITIES` —
   exactamente el mismo patrón de declaración de capa que ya usa el Harness financiero
   (`PRIMARY_LAYER`/`INPUT_LAYERS`/`OUTPUT_LAYER`/`RESPONSIBILITIES`/
   `NON_RESPONSIBILITIES`), aplicado a agentes en vez de a capas de datos.
4. **El Coordinator coordina, no ejecuta.** Nunca genera código, nunca valida, nunca
   revisa — orquesta la secuencia y decide transiciones de estado basado en evidencia
   que otros Agents produjeron.
5. **Los Contracts restringen.** Un Contract es la forma ejecutable/verificable de una
   Specification — define qué debe cumplirse, no cómo lograrlo.
6. **Los Guardrails limitan.** Acotan qué puede hacer un Agent en tiempo de ejecución
   (herramientas permitidas, alcance de archivos, límites de autonomía) —
   independientemente de si el Agent "quiere" hacer algo distinto.
7. **Los Invariants protegen.** Propiedades que deben sostenerse en todo momento del
   ciclo de vida del software producido (p. ej.: "un artefacto de Delivery nunca se
   publica sin Validation + Review satisfactorios" — el mismo patrón que I-012 del
   Harness financiero, generalizado).
8. **Los Validators verifican.** Producen evidencia objetiva de que un Contract se
   cumple o no. Un Validator no opina; mide.
9. **Los Reviewers revisan.** Evalúan calidad, diseño y riesgo más allá de lo que un
   Validator puede medir mecánicamente — con criterio, no con checklist únicamente.
10. **Los Evals demuestran comportamiento.** Antes de confiar en un Agent para una
    responsabilidad, debe existir un conjunto de casos que demuestre que la cumple —
    igual que el `Six-Hats` actual demuestra su propio comportamiento por convención de
    invocación explícita, no por confianza implícita.
11. **El State registra el estado.** En todo momento debe ser posible responder "en qué
    etapa está esto, con qué evidencia, y qué falta" sin inferencia ni suposición.
12. **El Audit registra evidencia.** Toda decisión de la Factory —humana o de
    agente— debe quedar rastreable: quién, cuándo, con qué input, qué output, qué
    herramienta, qué resultado.

## 3 · Alcance

Pertenece a la Software Factory:

- El Factory Kernel (motor de orquestación, no implementado todavía).
- El Coordinator y los Agents especializados (Classifier, Generator, Validator,
  Reviewer — §6).
- El Pipeline SDD y su State Machine (§7, §8).
- El Shared State de la Factory (§9) — separado de cualquier estado del ETL.
- Los Contracts, Guardrails, Invariants y Evals que la Factory define para **sí
  misma** y para el software que produce.
- El mecanismo de Audit y Traceability de la Factory.
- El Reuse Engine, Blueprints, Component Catalog y Capability Catalog (§16) — que
  pueden eventualmente catalogar componentes de Catalaxia como reutilizables, sin que
  eso implique que la Factory dependa de Catalaxia para funcionar.
- La convención de aislamiento Git/worktrees para cambios que la Factory produce
  (§14) — conceptual en esta versión, no implementada.

## 4 · No-alcance (explícito)

**El ETL financiero de Catalaxia y su Harness NO forman parte del Factory Kernel.**
Concretamente, quedan fuera y no se modifican:

- `engine/` (motor del pipeline financiero: identity, checkpoints, hashout, xbrlparse,
  manifest de stages).
- `scripts/engine/`, `scripts/market/`, `scripts/pipeline/`, `scripts/tickets/`,
  `scripts/dolares/` (stages S00–S04, Market M0–M23, screener legacy, jobs CNV,
  fetchers de dólar).
- `api/`, `backend/` (servicio y calculadoras del producto financiero).
- `.github/AGENT_HARNESS.md` / `ARCHITECTURE_HARNESS.md.txt` (el Harness de 12 capas
  financieras — normativo para el ETL, **no** para la Factory).
- `docs/architecture/*` (contratos F0XX, IDENTITY_*, HASH_OUT_CONTRACT, MIGRATIONS_
  CONTRACT, S04_CONTRACT, SYSTEM_HOMOLOGATION_* — todos artefactos de gobierno del
  dominio financiero).
- `docs/review/FINDINGS.md` (bitácora del auditor CIAA, exclusiva del programa
  financiero).
- `migrations/`, `data/`, `outputs/docs/fase_*` (datos y migraciones del ETL).
- `.claude/state/`, `.claude/context/` en su contenido actual (continuidad de los
  workstreams SEC/CNV/MARKET/Identity) — la Factory puede definir su **propio**
  mecanismo de state (§9), separado de estos archivos, no reemplazarlos.

La Factory puede eventualmente **leer** estos artefactos (por ejemplo, para catalogar
un componente financiero como reutilizable) y puede eventualmente **producir cambios**
sobre ellos si un Requirement lo pide explícitamente — pero siempre pasando por su
propio pipeline SDD, nunca modificándolos como efecto colateral de operar la Factory
misma, y nunca el ETL como *dependencia estructural* del Kernel (el Kernel debe poder
existir y operar sobre un proyecto que no tenga nada de Catalaxia).

## 5 · Arquitectura lógica

**ARQUITECTURA OBJETIVO** — nada de lo listado abajo está implementado hoy
(**ESTADO ACTUAL DEL REPOSITORIO**: ninguno de estos componentes existe como código;
ver §0 y el informe adjunto).

```
                    ┌─────────────────────────┐
                    │   Factory Specification   │  (este documento y sus sucesores)
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │       Factory Kernel       │
                    │  (motor: state machine +   │
                    │   evidence gate + registry) │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │        Coordinator         │  orquesta, no ejecuta
                    └──┬───────┬───────┬────────┘
                       │       │       │
              ┌────────▼─┐ ┌──▼────┐ ┌▼─────────┐      ┌──────────────┐
              │Classifier│ │Generator│ │Validator │ ...  │ Agent Registry│
              └──────────┘ └────────┘ └──────────┘      └──────────────┘
                       │       │       │
                    ┌──▼───────▼───────▼──┐
                    │   Shared State (§9)  │◄────────┐
                    └──────────┬───────────┘         │
                               │                       │
        ┌──────────┬──────────┼──────────┬───────────┼──────────┐
        │          │          │          │           │          │
   ┌────▼───┐ ┌────▼────┐ ┌───▼────┐ ┌───▼────┐ ┌────▼────┐ ┌───▼────┐
   │Contracts│ │Guardrails│ │Invariants│ │  Evals │ │Validation│ │ Review │
   └────────┘ └─────────┘ └────────┘ └────────┘ └─────────┘ └────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Human Gates / Risk  │  (§17)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  MCP / Tool Gateway   │  (§18)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Audit / Traceability │  (§10, §13)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Git / Worktrees     │  (§14)
                    └──────────┬──────────┘
                               │
        ┌──────────────────────▼──────────────────────┐
        │  Factory Knowledge: Reuse Engine · Blueprints  │
        │  · Component Catalog · Capability Catalog (§16)│
        └────────────────────────────────────────────────┘
```

Ningún componente de este diagrama existe hoy como código. Se documenta la relación
lógica esperada, no una implementación.

## 6 · Agentes

**ARQUITECTURA OBJETIVO.** Cinco responsabilidades mínimas, sin implementación:

### Classifier
- **Responsabilidad primaria**: recibe un Requirement (o un Change Request, §20) y
  determina su tipo, dominio, complejidad y descomposición jerárquica preliminar
  (§16.1 — Project→Domain→Capability→Feature→Requirement→Task).
- **No puede**: generar código, decidir arquitectura final, aprobar ni rechazar nada.
- **Output**: una clasificación estructurada que el Coordinator usa para decidir qué
  Agents siguen en el Pipeline.

### Generator
- **Responsabilidad primaria**: produce artefactos (Specification, Architecture, Plan,
  Tasks, Code) a partir de los artefactos previos del Pipeline y de los Contracts
  vigentes.
- **No puede**: certificar su propio output como válido, ni saltear una etapa de
  Validation, ni decidir que su output está "listo" — eso lo determina evidencia
  (§12), no una afirmación del Generator.

### Validator
- **Responsabilidad primaria**: produce evidencia objetiva (tests, chequeos
  estáticos, ejecución real) de que un artefacto cumple sus Contracts e Invariants.
- **No puede**: corregir el artefacto que está validando (separación de
  responsabilidad — el mismo principio que el Harness financiero aplica entre capas:
  "una capa no oculta errores de otra capa").
- **Output**: uno de PASS / WARNING / BLOCK / NOT_CALCULABLE / NO DETERMINABLE — nunca
  una aprobación implícita por ausencia de error.

### Reviewer
- **Responsabilidad primaria**: evalúa lo que un Validator no puede medir
  mecánicamente — diseño, mantenibilidad, alineación con la Specification, riesgo no
  cuantificable.
- **No puede**: sustituir a Validation. Un Review favorable nunca compensa una
  Validation fallida.

### Coordinator
- **Responsabilidad primaria**: orquesta la secuencia del Pipeline, invoca al Agent
  correspondiente según el estado actual (§8), decide transiciones de estado
  **basado exclusivamente en evidencia producida por otros Agents**, y escala a un
  Human Gate cuando el Risk Level (§17) lo exige.
- **No puede**: generar, validar ni revisar arbitrariamente el trabajo de otro Agent.
  Si el Coordinator necesita ese trabajo hecho, lo delega — nunca lo asume él mismo.

Cada Agent, cuando se implemente, deberá declarar explícitamente:
`PRIMARY_RESPONSIBILITY`, `INPUTS`, `OUTPUTS`, `NON_RESPONSIBILITIES`,
`TOOLS_ALLOWED` (Guardrail), `RISK_LEVEL_DEFAULT` — mismo patrón de declaración de
responsabilidad que usa `.github/ARCHITECTURE_HARNESS.md.txt` para sus 12 capas.

## 7 · Pipeline

**ARQUITECTURA OBJETIVO.** Etapas y condición de transición mínima entre cada una
(evidencia requerida, no solo "el agente terminó"):

| Etapa | Agent(s) típico(s) | Condición de transición a la siguiente |
|---|---|---|
| Requirement | Classifier | Clasificación completa + Requirement con ID asignado |
| Specification | Generator | Specification aprobada contra el Requirement (evidencia: revisión o eval) |
| Architecture | Generator + Reviewer | Architecture consistente con Specification y con Contracts existentes |
| Contracts | Generator | Contracts formalizados y verificables (no ambiguos) |
| Invariants | Generator + Reviewer | Invariants declarados y no contradictorios entre sí ni con Contracts existentes |
| Evals | Generator | Casos de eval definidos, ejecutables, con criterio de éxito explícito |
| Plan | Generator | Plan descompuesto en Tasks trazables a Requirement/Spec/Architecture |
| Tasks | Coordinator | Tasks con dependencias explícitas, sin ciclos |
| Code | Generator | Código que compila/corre y referencia su Task de origen |
| Validation | Validator | Evidencia PASS sobre Contracts + Invariants + Evals |
| Review | Reviewer | Aprobación explícita, con motivo — nunca silenciosa |
| Delivery | Coordinator | Validation=PASS + Review=APPROVED simultáneos (mismo patrón que I-012 del Harness financiero: Publicación exige Validación + Certificación) |

Ninguna etapa puede retroceder en silencio: si algo posterior invalida una etapa
anterior, eso es un Change Request (§20), no una edición directa del artefacto ya
aprobado.

### 7.1 · Alcance declarado de un Run (DEC-SF-001)

**IMPLEMENTADO.** Las 12 etapas de la tabla anterior son el **modelo conceptual
completo** del pipeline SDD. Un Run concreto se evalúa contra su **alcance
declarado** (`RunScope`): el subconjunto de esas etapas que ese Run se compromete a
ejecutar, junto con los tests y la evidencia que su contrato exige.

Lectura normativa de *"Ninguna etapa puede saltearse"* (§1): **ninguna etapa
obligatoria dentro del alcance declarado puede omitirse.** Una etapa fuera de ese
alcance no es obligatoria para ese Run, salvo que otro contrato aplicable la exija.

**Conflicto registrado y resuelto por DEC-SF-001.** La frase de §1, leída de forma
absoluta, exigiría las 12 etapas en todo Run. Esa lectura es incompatible con la
Factory tal como existe hoy: solo `Code` y `Validation` tienen Agents implementados
(§6 — Reviewer sigue siendo ARQUITECTURA OBJETIVO), de modo que ningún Run podría
alcanzar `completed` jamás. DEC-SF-001 resuelve el conflicto de forma explícita y
acotada: el alcance declarado es la unidad de evaluación. No se modifica la tabla de
12 etapas ni se declara implementado nada que no lo esté.

## 7.2 · DEC-SF-001 — Run Completion Semantics

| Campo | Valor |
|---|---|
| ID | `DEC-SF-001` |
| Estado | **APROBADA** — implementada en esta slice |
| Afecta | §1 (lectura de "ninguna etapa puede saltearse"), §7, §8, §9, §12 |
| Implementación | `kernel/run_scope.py`, `kernel/run_manager.py`, `coordinator/coordinator.py` |
| Tests | `tests/test_dec_sf_001_run_scope.py` |

**Motivo.** `Coordinator.execute_pipeline()` transicionaba a `COMPLETED` cuando se
agotaba la lista de `steps` que le pasaba el llamador, sin compararla contra ninguna
definición de completitud. Un Run de 2 etapas quedaba `COMPLETED` igual que uno de
12: el estado terminal describía al llamador, no al contrato.

**Reglas.**

1. Un Run se evalúa contra un alcance **declarado, identificable y versionado**
   (`scope_id` + `scope_version`).
2. El alcance y sus criterios de aceptación se definen juntos y son trazables entre sí.
3. Un Run puede transicionar a `completed` **solo si**: su alcance y versión son
   identificables; se satisfacen todos los criterios obligatorios; todos los tests
   requeridos **se ejecutaron realmente** y pasaron; existe la evidencia que el
   contrato exige, trazable a ese Run y a esa versión de alcance; y no se omitió en
   silencio ninguna etapa, criterio o test requerido.
4. **Agotar los pasos provistos por el llamador no es evidencia de completitud.**
5. Que una suite de tests pase no alcanza si el comportamiento requerido por el
   alcance no está representado en los tests y criterios declarados.
6. Un cambio posterior de alcance crea una **versión nueva** con su propio contrato.
   No invalida retroactivamente un Run completado contra una versión anterior válida.
7. `completed` significa que el Run satisfizo su contrato de ejecución. **No**
   significa `approved`, `reviewed`, `delivered` ni `closed` (coherente con §8).
8. No se agrega ningún estado nuevo (p. ej. `PARTIAL`): la evidencia del repositorio
   no estableció su necesidad y ninguna decisión lo autoriza.

**Consecuencias.**

- `execute_pipeline()` **falla cerrado**: sin alcance declarado no puede afirmar
  completitud, y transiciona a `failed` registrando el motivo como evento `ERROR`.
- Un alcance ausente, vacío, con etapas desconocidas o fuera del orden de §7 se
  rechaza al crear el Run (`InvalidScopeError`), antes de ejecutar nada.
- `execute_stage()` **no cambia**: queda fuera del alcance de esta decisión.
- La persistencia conserva `scope`, `executed_stages` y `passed_tests`. Un Run
  guardado antes de DEC-SF-001 carga sin alcance, sin error — regla 6.

## 8 · State Machine

**ARQUITECTURA OBJETIVO.** Estados conceptuales, sin implementación:

```
pending → running → { blocked | failed | completed }
completed → { approved | rejected }
blocked → running          (una vez resuelta la condición de bloqueo)
failed → running            (reintento explícito, no automático)
rejected → pending           (vuelve al inicio de su etapa, con motivo registrado)
```

Reglas:
- `pending`: existe el artefacto de entrada, ningún Agent lo tomó todavía.
- `running`: un Agent está trabajando activamente sobre esa etapa.
- `blocked`: la etapa no puede avanzar por una condición externa (falta un input, un
  Human Gate pendiente, un Guardrail lo impide) — no es lo mismo que `failed`.
- `failed`: el Agent intentó y no pudo producir un artefacto conforme.
- `completed`: el Agent produjo un artefacto; **no implica aprobación**.
- `approved` / `rejected`: veredicto de Validation+Review sobre un artefacto
  `completed`. Solo `approved` habilita la transición de Pipeline (§7).

Ninguna transición ocurre sin que el Coordinator la registre en el Shared State (§9)
con evidencia (§12) y quede en el Audit (§13).

## 9 · Shared State

**ARQUITECTURA OBJETIVO.** Debe mantenerse como estado común, direccionable por ID
(§10):

- `requirements` — el catálogo de Requirements activos e históricos.
- `specifications`, `architecture`, `contracts`, `invariants`, `evals` — un artefacto
  por ID, versionado (§19).
- `plans`, `tasks` — con su árbol de dependencias.
- `agents` — registro de qué Agents existen, su versión, su Eval de comportamiento
  vigente.
- `artifacts` — el código y demás outputs generados, con su Task de origen.
- `evidence` — toda evidencia producida por Validators (§12).
- `decisions` — toda decisión de Coordinator o de un Human Gate, con motivo.
- `execution status` — el estado actual (§8) de cada Task/etapa.

**Separado explícitamente** del `.claude/state/`/`.claude/context/` actuales del ETL
financiero (§4) — pueden coexistir en el mismo repositorio sin mezclarse; el
mecanismo concreto de persistencia del Shared State de la Factory es **NO
DETERMINABLE CON LA INFORMACIÓN DISPONIBLE** en esta versión (podría ser archivos,
una base de datos propia, u otro mecanismo — se decide al diseñar el Kernel).

## 10 · Trazabilidad

Todo artefacto se relaciona mediante: `ID`, `versión`, `estado`, `dependencias`,
`inputs`, `outputs`, `evidencia`. Ejemplo de cadena completa:

```
REQ-001 → SPEC-001 → ARCH-001 → CONTRACT-001 → INV-001 → EVAL-001
        → TASK-001 → CODE-001 → VALIDATION-001 → REVIEW-001 → DELIVERY-001
```

Cada flecha debe ser reconstruible: dado `DELIVERY-001`, debe poder recuperarse toda
la cadena hasta `REQ-001` sin inferencia — el mismo principio que I-013
(`TRACEABILITY`) del Harness financiero, generalizado de "resultado publicado → RAW"
a "software entregado → Requirement original".

## 11 · Governance

- **Contracts**: forma verificable de una Specification. No ambiguos, no
  aspiracionales — si algo no puede verificarse mecánicamente, no es un Contract, es
  una guía.
- **Guardrails**: límites operativos en tiempo de ejecución de un Agent (herramientas
  permitidas, alcance de archivos/paths, límites de llamadas externas). Un Guardrail
  no reemplaza a un Contract — un Contract dice qué debe cumplirse; un Guardrail dice
  qué puede intentarse.
- **Invariants**: propiedades que deben sostenerse siempre, no solo al final de una
  etapa (ver §2.7).
- **Risk**: nivel de autonomía permitido a un Agent o a una transición de Pipeline
  (§17).
- **Human Gates**: puntos del Pipeline donde una persona debe aprobar explícitamente
  antes de continuar — nunca implícitos, siempre declarados por el Contract o el Risk
  Level vigente.

## 12 · Evidence

Una etapa se considera conforme únicamente si existe evidencia de una de estas
categorías — **tomadas directamente de `.github/ARCHITECTURE_HARNESS.md.txt`**, que ya
las define y las usa en producción para el dominio financiero:

- **VERIFICADO POR CÓDIGO**: existe implementación observable que demuestra la
  afirmación.
- **VERIFICADO POR TEST**: existe un test ejecutado que demuestra la propiedad.
- **VERIFICADO POR EJECUCIÓN**: existe una ejecución real cuyo resultado demuestra la
  propiedad.
- **NO DETERMINABLE**: no existe evidencia suficiente — nunca se completa con
  suposición.

**No se acepta conformidad por clasificación nominal**: que un artefacto se llame
"Validation" o esté en la carpeta correcta no lo vuelve válido. Tampoco se acepta:
"el código parece correcto", "el script terminó con exit 0" o "el test pasó" como
prueba automática de que el *sistema completo* (no solo esa pieza) es conforme — el
mismo principio que la sección 4 del Harness financiero ("CERTIFICAR") ya aplica.

## 13 · Audit

Debe registrarse, para cada acción relevante del Pipeline:

- ejecución (qué corrió, cuándo empezó/terminó)
- agente (cuál, qué versión)
- decisión (qué se decidió y por qué)
- input (qué recibió)
- output (qué produjo)
- herramienta (qué tool/MCP usó, si alguno)
- resultado (éxito/fallo/estado)
- timestamp
- evidencia (referencia a §12)

El mecanismo concreto de almacenamiento del Audit es NO DETERMINABLE CON LA
INFORMACIÓN DISPONIBLE en esta versión — la exigencia es sobre *qué* debe quedar
registrado, no *dónde*.

## 14 · Git / Aislamiento

**Conceptual, no implementado.** La Factory debería poder trabajar cambios aislados —
un Requirement o Task en curso no debería interferir con otro en curso en paralelo.
El repositorio ya usa worktrees para aislar trabajo paralelo entre workstreams del ETL
(`.claude/worktrees/`) — es un patrón preexistente que la Factory podría adoptar para
sus propios cambios, pero el mecanismo exacto (una rama por Task, un worktree por
Requirement, otro esquema) es NO DETERMINABLE CON LA INFORMACIÓN DISPONIBLE hasta
diseñar el Kernel.

## 15 · Riesgo

Niveles de autonomía y cuándo debe intervenir una persona: **NO DETERMINABLE CON LA
INFORMACIÓN DISPONIBLE** en el detalle (cuántos niveles, qué umbrales) — lo que sí se
establece como principio (§2, §11) es que existe un Risk Level asociado a cada
Agent/transición, y que ciertas transiciones exigen un Human Gate explícito
independientemente de que toda la evidencia automática sea PASS. Ejemplos de
candidatos a Human Gate obligatorio (a decidir al implementar): Delivery a producción,
cualquier cambio que afecte a Catalaxia (el ETL) desde la Factory, cualquier Contract
nuevo que modifique un Invariant existente.

## 16 · MCP

MCP (Model Context Protocol) es, en este repositorio, un **mecanismo de acceso
controlado a herramientas y contexto externo** — confirmado por inspección: no hay
`.mcp.json` ni configuración de servidores MCP a nivel de repositorio; los servidores
MCP disponibles (Notion, Slack, Gmail, Google Drive/Calendar, etc.) están configurados
del lado del cliente/sesión, no del proyecto.

**Explícito, para evitar un malentendido común**: MCP por sí solo **no** provee
governance, autorización ni auditoría. Es un *gateway* de acceso — la Factory debe
envolver cualquier llamada a través de MCP con sus propios Guardrails (§11) y
registrarla en su propio Audit (§13); MCP no lo hace por la Factory.

## 16.1 · Escalabilidad — descomposición jerárquica

La arquitectura debe aplicarse igual a un cambio de una línea que a un sistema
completo, mediante:

```
Project → Domain → Capability → Feature → Requirement → Task → Implementation Unit
```

Un Requirement pequeño puede saltar directamente a una única Implementation Unit; uno
grande se descompone en múltiples Features, cada una con su propio recorrido completo
del Pipeline (§7). El Classifier (§6) es responsable de determinar en qué nivel de
esta jerarquía entra un Requirement dado.

## 17 · Versionado

Deben versionarse de forma independiente: `Factory-Spec` (este documento — versión
`0.1.0` en su primera emisión), `SDD` (cada Specification tiene su propia versión),
`Contracts`, `Agents` (versión + su Eval de comportamiento vigente), `Blueprints`,
`Artifacts` (código generado, versión ligada a su Task). El esquema exacto de
versionado (semver, hash, secuencial) es NO DETERMINABLE CON LA INFORMACIÓN
DISPONIBLE — se decide al implementar el Kernel, pero el requisito de que cada
categoría se versione *independientemente de las demás* es normativo desde ahora.

## 16.2 · Reutilización

**Blueprints**: plantillas de solución para un tipo de Requirement recurrente (no
existen hoy en el repositorio).

**Component Catalog**: inventario de componentes reutilizables — candidatos ya
identificados en el ETL financiero que la Factory podría catalogar (sin moverlos ni
modificarlos): el patrón de `market_db.py` (puerta única de conexión con guarda
lectura/escritura — F-001), el patrón de checkpoint/resume vía tabla de intentos
append-only (`market_raw_runs`, F-013), el patrón de doble-columna
issuer-vs-instrument (`ticker_canonico`/`venue_ticker`, F-014).

**Capability Catalog**: qué es capaz de hacer el sistema en su conjunto, a nivel de
capacidad de negocio, no de archivo.

**Knowledge**: el conocimiento acumulado de la Factory sobre decisiones pasadas,
errores conocidos, patrones que funcionaron — análogo a `docs/review/FINDINGS.md` del
programa financiero (registro de hallazgos con evidencia, nunca cerrado por
declaración propia), pero para la Factory, no para el ETL.

**Reuse Engine**: el mecanismo que, dado un nuevo Requirement, sugiere Blueprints o
componentes del Catalog aplicables. No implementado; NO DETERMINABLE CON LA
INFORMACIÓN DISPONIBLE cómo determina relevancia (búsqueda semántica, tags,
clasificación del Classifier) — se decide al implementar.

## 18 · Evolución

Una modificación de software ya entregado por la Factory (incluido, eventualmente,
software de Catalaxia) vuelve al mismo ciclo, nunca se parchea por fuera de él:

```
Change Request → Impact Analysis → SDD Update → Plan → Code → Validation → Review → Delivery
```

`Impact Analysis` es una etapa nueva respecto del flujo de un Requirement original:
determina qué Specifications, Contracts, Invariants y Artifacts existentes quedan
afectados antes de tocar nada — mismo principio que la sección 8
("Decisiones de modificación") del Harness financiero: identificar consumidores,
productores, dependencias y evidencia de uso antes de modificar, nunca decidir por
"nombre parecido" o "duplicación aparente".

---

## Glosario mínimo de trazabilidad (referencia rápida)

| Prefijo | Artefacto |
|---|---|
| `REQ-` | Requirement |
| `SPEC-` | Specification |
| `ARCH-` | Architecture |
| `CONTRACT-` | Contract |
| `INV-` | Invariant |
| `EVAL-` | Eval |
| `TASK-` | Task |
| `CODE-` | Code artifact |
| `VALIDATION-` | Evidencia de Validation |
| `REVIEW-` | Decisión de Review |
| `DELIVERY-` | Entrega |
| `CR-` | Change Request |
