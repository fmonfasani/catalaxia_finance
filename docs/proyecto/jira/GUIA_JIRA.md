# Guía de Jira — crear el proyecto e importar el backlog

> Cómo dejar Jira listo en ~20 min con el backlog ya cargado (`jira_import.csv`:
> 7 épicas · 34 historias · 108 puntos · 4 sprints). Pensado para **Jira Cloud** (gratis hasta 10 usuarios).

---

## 1. Crear el proyecto
1. En Jira → **Projects → Create project → Scrum** (queremos sprints).
2. Nombre: **Catalaxia Screener** · Key: **CAT** (los issues quedan `CAT-1`, `CAT-2`…).
3. Tipo: *Team-managed* o *Company-managed* — cualquiera sirve. (*Company-managed* da import más completo.)

## 2. Configurar antes de importar
- **Usuarios:** invitá a Federico, Mateo, Joaquín y Aldana (con esos nombres/emails) para que el
  campo *Assignee* mapee al importar.
- **Componentes** (Project settings → Components): `Infra`, `Datos`, `Backend`,
  `Frontend-Screener`, `Frontend-Detalle`, `QA`.
- **Story Points:** si no aparece el campo, activalo (Board settings → Estimation → Story Points).

## 3. Importar el CSV
1. **Settings (⚙) → System → External System Import → CSV** (o en team-managed: *Project settings →
   Import*).
2. Subí `jira_import.csv`. Delimitador: coma. Encoding: UTF-8.
3. **Mapeo de columnas** (la parte clave):

| Columna del CSV | Campo de Jira |
|---|---|
| Issue Type | Issue Type |
| Summary | Summary |
| Epic Name | Epic Name *(solo lo usan las filas Epic)* |
| Epic Link | Epic Link *(linkea cada Story a su épica)* |
| Assignee | Assignee |
| Sprint | Sprint *(crea Sprint 1–4 al importar)* |
| Story Points | Story Points |
| Component | Components |
| Labels | Labels |
| Priority | Priority |

4. Confirmá. Jira crea las **7 épicas**, las **34 historias** linkeadas, y los **4 sprints**.

> Si tu plan no importa el campo *Sprint* directamente, importá igual y después arrastrá las historias
> a cada sprint en el Backlog (están etiquetadas por sprint en la columna).

## 4. Después de importar
- **Backlog:** vas a ver Sprint 1–4 con sus historias. Revisá que los puntos por sprint estén
  parejos (~27 pts c/u).
- **Board:** columnas sugeridas **To Do → In Progress → In Review → Done** (agregá *In Review* para
  reflejar el paso de PR/review de `08`).
- **Iniciar Sprint 1** cuando arranquen. Duración: 1 semana (coincide con el ciclo de `07`).

## 5. Convención de trabajo en Jira (alineado con `08`)
- 1 rama y 1 PR por historia; el PR lleva el ID (ej. `CAT-14: filtros screener`).
- Mover la tarjeta a **In Review** al abrir el PR, a **Done** al mergear (cumpliendo la DoD).
- Los viernes (`07`): revisar el board, cerrar el sprint, abrir el siguiente.

## 6. Campo de rendimiento (opcional)
Si querés registrar la **rúbrica de `07`** en Jira: creá un campo custom numérico "Rúbrica semanal"
o llevala aparte en una planilla. Recomendación: **planilla aparte** (Jira mide trabajo, no personas).

## 7. Resumen de carga
| Sprint | Fechas | Historias | Puntos |
|---|---|---|---|
| Sprint 1 · Fundamentos | Mié 15 → Vie 24 Jul | 11 | ~38 |
| Sprint 2 · Integración | Lun 27 → Vie 31 Jul | 7 | ~25 |
| Sprint 3 · Funcionalidad | Lun 3 → Vie 7 Ago | 9 | ~26 |
| Sprint 4 · QA + entrega | Lun 10 → Vie 14 Ago | 7 | ~19 |
| **Total** | 15/07 → 14/08 | **34** | **108** |
