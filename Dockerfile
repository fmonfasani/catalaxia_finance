FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY scripts/screener/requirements.txt ./screener_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r screener_requirements.txt

COPY . .

RUN mkdir -p data/logs data/raw/companyfacts data/raw/submissions

ENV PYTHONPATH=/app/scripts/tickets/screener:/app/scripts/tickets/sec_edgar/scripts:/app/scripts/tickets

CMD ["python", "scripts/tickets/screener/run_update.py", "--daily"]