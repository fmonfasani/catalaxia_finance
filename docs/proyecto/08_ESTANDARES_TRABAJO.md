# Estándares de trabajo

> Reglas mínimas para que 4 personas trabajen sin pisarse. Cortas y no negociables.

---

## 1. Git flow
- Rama principal: **`main`** (siempre desplegable). Nadie commitea directo a `main`.
- Ramas de trabajo: `feat/<area>-<desc>`, `fix/<desc>`, `infra/<desc>`.
  - Ej.: `feat/screener-filtros`, `feat/api-empresas`, `infra/postgres-vps`.
- 1 PR por historia de Jira. El nombre del PR incluye el ID de Jira (ej. `CAT-14: filtros screener`).

## 2. Commits
- Convención: `tipo(scope): descripción` — `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
  - Ej.: `feat(api): GET /empresas con filtros`.
- Commits chicos y frecuentes; nada de "varios cambios" en uno solo.

## 3. Pull Requests + review
- **Todo va por PR + review de al menos 1 par.** Backend revisa Federico/Mateo; frontend se revisan
  entre Joaquín/Aldana (y Federico si toca contrato).
- Checklist del PR: cumple criterio de aceptación · pasa el smoke test · no rompe el contrato de API ·
  sin debug/credenciales · actualiza doc si cambió algo (ej. `04`).
- Review en < 24 h. Si urge, se pide por el canal.

## 4. El contrato de API es sagrado
- Los front programan contra `04_CONTRATO_API.md`. Si el backend cambia un shape, **primero** se
  actualiza el doc y se avisa; recién después se mergea. Romper el contrato sin avisar = bloquear a 2
  personas.

## 5. Testing mínimo
- **Backend:** cada endpoint con al menos 1 test de happy-path + 1 de error/vacío.
- **Frontend:** smoke manual de la vista (loading/empty/error) antes del PR. Tests de componente
  donde aporte.
- **Nada se marca "done" sin correr de punta a punta** al menos una vez.

## 6. Definition of Ready / Done
- **Ready** (para empezar): criterio de aceptación claro + dependencia disponible/mockeada + estimada
  en Jira.
- **Done** (para cerrar): ver `01_ALCANCE_Y_DOD.md §5`. En una línea: *cumple el criterio, está en PR
  mergeado con review, corre en el entorno, no rompe nada*.

## 7. Comunicación
- Canal del equipo (Slack/WhatsApp): bloqueos se avisan **el mismo día**, no el viernes.
- Los viernes: demo + rúbrica (`07`).
- Decisiones técnicas de fondo se anotan (ADR corto de 5 líneas) para no rediscutir.

## 8. Higiene
- Nada de secretos en el repo (usar `.env`, no commitear `.env`).
- `main` siempre levanta y corre. Si algo la rompe, se revierte primero y se discute después.
