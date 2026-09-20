# CATALAXIA — REVIEW GATE

Auditor: **CIAA** · Ciclo **AUDIT-02** · 2026-08-25 · Baseline `444ee1a`

---

# DICTAMEN FINAL

## NOT_READY para la Canonical Economic Layer

Emitido con evidencia, no por falta de ella. Las tres precondiciones de integración son
verificables, se verificaron, y **las tres dieron negativo**.

Esto **no** es un juicio sobre la calidad del trabajo. Las tres capas mejoraron de forma
sustantiva desde AUDIT-01, tienen evidencia real y en buena parte reproducible, y **no se
detectó pérdida silenciosa de datos, identidad inventada, mezcla de perímetros ni conversión
de unidades sin declarar** en ninguna de ellas. Lo que falta son los contratos *entre* capas.

---

## GATE POR WORKSTREAM

| Workstream | Objeto | AUDIT-01 | AUDIT-02 |
|---|---|---|---|
| **SEC** | S03 `971ce5d999a2499b-s03` | no auditado | **PASS_WITH_WARNINGS** |
| **CNV** | C3 `8db8692e…` run6 | **BLOCK** | **PASS_WITH_WARNINGS** — bloqueo levantado |
| **MARKET** | M22 `MKT-GOLDEN-…` | PASS_WITH_WARNINGS | **PASS_WITH_WARNINGS** — sostenido |
| **CROSS (L2)** | — | no ejecutable | **EJECUTADA → NOT_READY** |

### El bloqueo de CNV se levanta

`C-C3-007` ya no es un falso PASS: verificado que **cierra `C1-R-001` ⇒ FAIL**. El control
detecta lo que existe para detectar. Ése era el fundamento del BLOCK y desapareció.

### SEC entra y pasa

Primera auditoría del workstream. Los cuatro conteos son exactos, el gate cierra 9/9, la
cadena EXPECTED→PERSISTED no pierde nada (27=27, 0 rechazados, 0 errores) y los 18 tests
pasan por corrida propia.

---

## LAS TRES PRECONDICIONES QUE FALLAN

**1 · No existe contrato de identidad canónico** — F-011 (HIGH)

El join CIK ↔ CUIT ↔ instrumento es *reconstruible* pero atraviesa **tres sistemas de
almacenamiento** sin integridad referencial:

```
identity.entities @5433    7998 entidades · CUIT poblado en 0
identity.identifiers       CIK · TICKER · YF_SYMBOL      (no existe el tipo CUIT)
market_instruments @5432   entity_id=72 (entero) · SIN foreign key
dim_entity @ SQLite        la única fila que ata cuit=30546689979 a cik=0000904851
```

Una capa canónica se construye **exactamente sobre esa junta**.

**2 · Market está físicamente separado y sin guarda** — F-001 (HIGH)

Ningún join SQL puede cruzar Market con SEC/CNV (servidores distintos), y su destino de
escritura por defecto sigue siendo la base que el engine protege — ahora con el script de
escalamiento a 584 instrumentos ya escrito.

**3 · La semántica de checkpoint no es común** — F-013 (MEDIUM)

Tres convenciones divergentes para el artefacto que la capa canónica debería consumir como
unidad de confianza.

---

## FINDINGS

| ID | Sev | WS | Estado | |
|---|---|---|---|---|
| F-001 | HIGH | MARKET | **OPEN** | exposición aumentada: `m6_scale.py` existe, sin guarda |
| F-011 | HIGH | GLOBAL | **NUEVO** | no existe tipo `CUIT` en el modelo de identidad |
| F-003 | MEDIUM | CNV | **OPEN** | degradado desde HIGH: 1 de 3 criterios cumplido |
| F-006 | MEDIUM | GLOBAL | **PARCIAL** | 3 de 4 STATE actualizados; `MARKET_STATE` falso |
| F-007 | MEDIUM | CNV | **NUEVO** | `C-C3-007` admite PASS vacuo por otras dos vías |
| F-008 | MEDIUM | CNV | **NUEVO** | RAW 152 → 377 archivos, sin política de retención |
| F-009 | MEDIUM | SEC | **NUEVO** | 5 de 8 corridas sin estado terminal |
| F-012 | MEDIUM | GLOBAL | **NUEVO** | `git_commit` de los reportes no describe el árbol |
| F-013 | MEDIUM | GLOBAL | **NUEVO** | tres convenciones de checkpoint |
| F-002 | LOW | GLOBAL | **OPEN** | `is_prod` heurística de puerto |
| F-005 | LOW | CNV | **OPEN** | stage report sin manifest embebido |
| F-010 | LOW | GLOBAL | **NUEVO** | `created_at` del checkpoint C3 congelado |
| F-004 | — | CNV | **SUPERSEDED** | decisión de diseño registrada; residual en F-008 |

Ninguno **FALSE POSITIVE**. Ninguno **CLOSED** por completo: F-004 fue superado por una
decisión de diseño y F-006 quedó parcial.

Regla aplicada: **HIGH → normalmente BLOCK.** F-001 y F-011 no bloquean los gates de
workstream —ninguno invalida la evidencia de su checkpoint— pero **son precondición del
gate transversal**, que por eso resulta NOT_READY.

---

## CONDICIONES PARA `READY_FOR_CANONICAL_LAYER`

1. **F-011** — decisión registrada sobre cómo se representa CUIT en el modelo de identidad,
   e implementación que permita resolver el CUIT de una entidad consultando sólo `identity`.
2. **F-001** — decisión registrada sobre el destino de escritura de Market, **antes** de la
   primera corrida de `m6_scale.py`.
3. **F-013** — contrato común de checkpoint, o declaración explícita de que son artefactos
   distintos con el mismo nombre.
4. **F-012** — que `git_commit` identifique unívocamente el código que produjo la evidencia.

Las cuatro son decisiones arquitectónicas, no trabajo de ingeniería mayor. **El auditor no
las toma.**

## CONDICIONES PARA CERTIFICAR C3

5. **F-007** — aserción de contrato (CSV vacío o sin claves conocidas ⇒ FAIL) + test de
   regresión de `C-C3-007`.
6. **F-008** — política de retención decidida antes de escalar a `FINANCIERO`/`TODO`.

---

## DECLARACIÓN DE ALCANCE

- Cero modificaciones a código, tests, migraciones, RAW, evidencia o STATE de workstreams.
- Sólo git de lectura (`log`, `status`, `diff`, `show`). Ninguna operación que altere estado.
- **No se ejecutó** SEC S04, CNV `FINANCIERO`/`TODO`, ni Market M23 masivo.
- Escrituras del auditor, todas dentro del perímetro: `docs/review/*`,
  `.claude/state/AUDITOR_STATE.md`.
- Efectos colaterales declarados: corridas propias de `pytest`
  (`test_s03_xbrlparse.py` 18/18, `test_engine_cnv.py` 8/8). No tocan artefactos de
  workstream.

## CORRECCIONES DEL PROPIO AUDITOR

Tres sospechas propias resultaron infundadas y se descartaron **antes** de emitir finding:
desfase horario de los artefactos de S03 (era UTC vs local), `ON CONFLICT` sin constraint
(existe el índice único `ux_checkpoints_reuse`), y `EMPRESA_PAGE` sin converger (era un
cambio de contenido genuino, y terminó siendo la mejor prueba de que la canonicalización no
enmascara sustancia). Detalle en `FINDINGS.md`.

**AUDIT → EVIDENCE → FINDING → GATE. Ciclo 2 cerrado. El auditor se detiene aquí.**
