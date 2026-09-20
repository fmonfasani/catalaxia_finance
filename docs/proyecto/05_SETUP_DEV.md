# Guía de entorno de desarrollo (local)

> Cómo levantar el proyecto en tu máquina en < 30 min. Para todo el equipo.

---

## 1. Requisitos
- **Python 3.11+**, **Node 18+**, **Git**.
- PostgreSQL 16 local (opcional; se puede desarrollar contra el SQLite validado al inicio).

## 2. Repos / estructura
```
catalaxia-cedears-prod/     ← pipeline + data ya validada (existe)
  data/screener_export.json     ← 572 empresas (entregable del pipeline)
  data/instrumentos.csv          ← 733 instrumentos
backend/                    ← API FastAPI (nuevo, Mateo/Federico)
frontend/                   ← Next.js (nuevo, Joaquín/Aldana)
```

## 3. Backend (FastAPI)
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt          # fastapi uvicorn sqlalchemy asyncpg pydantic
cp .env.example .env                      # completar DATABASE_URL
uvicorn app.main:app --reload            # → http://localhost:8000  · /docs (Swagger)
```
`.env`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/catalaxia
# o para arrancar sin postgres: sqlite+aiosqlite:///./data/screener.db
CORS_ORIGINS=http://localhost:3000
```
**Cargar datos en local:** `python scripts/cargar_datos.py` (lee `screener_export.json` +
`instrumentos.csv` → tablas). Verifica: 572 empresas, 733 instrumentos.

## 4. Frontend (Next.js)
```bash
cd frontend
npm install
cp .env.local.example .env.local          # NEXT_PUBLIC_API_URL=http://localhost:8000/v1
npm run dev                               # → http://localhost:3000
```
**Modo mock (sin backend):** setear `NEXT_PUBLIC_API_URL=/mocks` y servir los JSON de
`04_CONTRATO_API.md` desde `public/mocks/`. Así Joaquín y Aldana arrancan el día 1.

## 5. Flujo diario
1. `git pull` de `main`, crear rama `feat/...` (ver `08_ESTANDARES_TRABAJO.md`).
2. Backend: correr contra la data local; si tocás el shape, actualizá `04_CONTRATO_API.md`.
3. Frontend: contra mocks hasta que Federico avise la URL de staging de la VPS; después contra la VPS.
4. PR → review → merge. Nunca a `main` directo.

## 6. Datos: la fuente de verdad
- **No se regenera el pipeline** para desarrollar. Usás los entregables ya validados
  (`screener_export.json`, `instrumentos.csv`). El pipeline solo lo corre Federico/jobs.
- Si un dato falta o parece raro: **no se inventa**, se marca (flag) o se consulta.
