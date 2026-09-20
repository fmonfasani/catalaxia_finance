# Imagen de la API (FastAPI + SQLAlchemy/ORM adentro).
# Copiar como  backend/Dockerfile  en el repo.
FROM python:3.11-slim

# deps del sistema mínimas (asyncpg no necesita build en slim moderno; añadir si hace falta)
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# El ORM (SQLAlchemy 2.0 + asyncpg) es parte de esta imagen, no un contenedor aparte.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
