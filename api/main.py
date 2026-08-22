#!/usr/bin/env python3
"""
Catalaxia Finance API - FastAPI
Endpoints para acceder a ratios de 572 empresas y validaciones

Uso:
  uvicorn main:app --host 127.0.0.1 --port 8100 --reload

Deployment (Docker):
  docker run -p 8100:8100 \
    -e DB_HOST=db \
    -e DB_USER=catalaxia \
    -e DB_PASSWORD=*** \
    catalaxia-api
"""
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import Optional, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Catalaxia Finance API",
    description="Ratios de 572 empresas (S&P 500 + ADR + BYMA-only)",
    version="2.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- handler global de errores con CORS ---
# Starlette atrapa las excepciones no manejadas en ServerErrorMiddleware, que
# corre POR FUERA del CORSMiddleware: esa respuesta 500 sale sin headers CORS y
# el browser se lo muestra al JS como "Failed to fetch", ocultando el status
# real. Devolvemos JSON con los headers puestos a mano para que el front pueda
# leer el error.
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as _HTTPException


def _cors_headers(request: Request) -> dict:
    origin = request.headers.get("origin", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


@app.exception_handler(_HTTPException)
async def http_exception_con_cors(request: Request, exc: _HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "path": request.url.path},
        headers=_cors_headers(request),
    )


@app.exception_handler(Exception)
async def error_no_manejado_con_cors(request: Request, exc: Exception):
    logger.exception("Error no manejado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "tipo": type(exc).__name__,
            "detalle": str(exc)[:300],
            "path": request.url.path,
        },
        headers=_cors_headers(request),
    )


def get_db():
    """Crea conexión a PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            dbname=os.environ.get("DB_NAME", "catalaxia"),
            user=os.environ.get("DB_USER", "catalaxia"),
            password=os.environ.get("DB_PASSWORD", "catalaxia"),
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"DB connection error: {e}")
        raise


def serialize_row(row):
    """Convierte Row de psycopg2 a dict, manejando NULL"""
    if row is None:
        return None
    d = dict(row)
    # Convertir None a null en JSON
    return {k: v if v is not None else None for k, v in d.items()}


@app.get("/")
def health():
    """Status del API"""
    return {
        "status": "ok",
        "message": "Catalaxia Finance API v2",
        "endpoints": [
            "/v2/screener - Todos los ratios (572 empresas)",
            "/v2/screener/{ticker} - Empresa específica",
            "/v2/screener/hist/{ticker} - Histórico de una empresa",
            "/v2/grupos - Empresas por grupo (sp500/adr/byma_only)",
            "/v2/stats - Estadísticas generales",
            "/v1/ratios - (Legacy) Ratios TXAR",
        ],
    }


@app.get("/v2/screener")
def get_screener(
    grupo: Optional[str] = Query(None, description="sp500, adr, byma_only"),
    sector: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Retorna ratios de todas las empresas (o filtradas).
    Formato: 1 fila = 1 empresa con todos sus ratios.
    """
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Columnas FIJAS, no SELECT *. Los endpoints devuelven la fila tal cual
    # (RealDictCursor, sin response_model), asi que los campos del JSON son
    # las columnas de la tabla: con SELECT *, cualquier ADD COLUMN cambia el
    # contrato publico de la API sin tocar Python. Estas son las 45 columnas
    # que ya se servian al 2026-08-22; para publicar una nueva se agrega
    # aca, a proposito.
    query = "SELECT cuit, ticker, ultimo_periodo, grupo, roe, roa, margen_neto, deuda_ebitda, eps, fcf_ce, payout, cagr_eps_5y, cagr_flag, per, price_book, price_sales, precio, market_cap_usd, currency, max_52w, min_52w, flag_cnv_fallback, flag_no_significativo, dato_desactualizado, payout_source, provenance, es_financiera, sector, adr_ratio, fuente_fund, payout_status, ev_ebitda, margen_operativo, precio_ars, precio_usd, ccl, precio_dif_iamc, precio_fuente, cedear_ratio, cedear_x, cusip, dr_level, div_adr_12m, last_div_date, div_yield_adr FROM screener WHERE 1=1"
    params = []

    if grupo:
        query += " AND grupo = %s"
        params.append(grupo)

    if sector:
        query += " AND sector = %s"
        params.append(sector)

    query += " ORDER BY ticker"
    query += " LIMIT %s OFFSET %s"
    params.extend([limit, skip])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Count total
    count_query = "SELECT COUNT(*) FROM screener WHERE 1=1"
    count_params = []
    if grupo:
        count_query += " AND grupo = %s"
        count_params.append(grupo)
    if sector:
        count_query += " AND sector = %s"
        count_params.append(sector)

    cursor.execute(count_query, count_params)
    row = cursor.fetchone()
    total = row['count'] if isinstance(row, dict) else row[0]

    cursor.close()
    conn.close()

    return {
        "count": len(rows),
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [serialize_row(r) for r in rows],
    }


@app.get("/v2/screener/{ticker}")
def get_screener_ticker(ticker: str):
    """Retorna ratios de una empresa específica"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT cuit, ticker, ultimo_periodo, grupo, roe, roa, margen_neto, deuda_ebitda, eps, fcf_ce, payout, cagr_eps_5y, cagr_flag, per, price_book, price_sales, precio, market_cap_usd, currency, max_52w, min_52w, flag_cnv_fallback, flag_no_significativo, dato_desactualizado, payout_source, provenance, es_financiera, sector, adr_ratio, fuente_fund, payout_status, ev_ebitda, margen_operativo, precio_ars, precio_usd, ccl, precio_dif_iamc, precio_fuente, cedear_ratio, cedear_x, cusip, dr_level, div_adr_12m, last_div_date, div_yield_adr FROM screener WHERE ticker = %s",
        (ticker.upper(),),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return {"error": f"Empresa {ticker} no encontrada"}

    return serialize_row(row)


@app.get("/v2/screener/hist/{ticker}")
def get_screener_hist(
    ticker: str,
    limit: int = Query(50, ge=1, le=500),
):
    """
    Retorna histórico de un ticker (todos los snapshots capturados).
    Ordena por period_ref DESC (más reciente primero).
    """
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        """
        SELECT *
        FROM screener_hist
        WHERE ticker = %s
        ORDER BY period_ref DESC, loaded_at DESC
        LIMIT %s
        """,
        (ticker.upper(), limit),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return {"error": f"No history found for {ticker}"}

    return {
        "ticker": ticker.upper(),
        "count": len(rows),
        "data": [serialize_row(r) for r in rows],
    }


@app.get("/v2/grupos")
def get_by_grupo(grupo: str):
    """Retorna todas las empresas de un grupo"""
    if grupo not in ("sp500", "adr", "byma_only"):
        return {"error": "Grupo debe ser: sp500, adr, o byma_only"}

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT ticker, grupo, sector, per, roe, roa, fcf_ce, deuda_ebitda FROM screener WHERE grupo = %s ORDER BY ticker",
        (grupo,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        "grupo": grupo,
        "count": len(rows),
        "data": [serialize_row(r) for r in rows],
    }


@app.get("/v2/stats")
def get_stats():
    """Retorna estadísticas generales"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN grupo='sp500' THEN 1 ELSE 0 END) as sp500_count,
            SUM(CASE WHEN grupo='adr' THEN 1 ELSE 0 END) as adr_count,
            SUM(CASE WHEN grupo='byma_only' THEN 1 ELSE 0 END) as byma_count,
            COUNT(DISTINCT sector) as sector_count,
            COUNT(CASE WHEN roe IS NOT NULL THEN 1 END) as roe_coverage,
            COUNT(CASE WHEN fcf_ce IS NOT NULL THEN 1 END) as fcf_ce_coverage,
            COUNT(CASE WHEN deuda_ebitda IS NOT NULL THEN 1 END) as deuda_ebitda_coverage,
            ROUND(AVG(per)::NUMERIC, 2) as per_promedio,
            ROUND(AVG(roe)::NUMERIC, 4) as roe_promedio,
            ROUND(AVG(roa)::NUMERIC, 4) as roa_promedio,
            ROUND(MAX(precio_usd)::NUMERIC, 2) as precio_max,
            ROUND(MIN(precio_usd)::NUMERIC, 2) as precio_min
        FROM screener
        """
    )
    stats = serialize_row(cursor.fetchone())
    cursor.close()
    conn.close()

    return stats


# ============= LEGACY ENDPOINTS (TXAR) =============


@app.get("/v1/ratios")
def get_ratios_legacy(
    limit: int = Query(100, ge=1, le=10000),
    skip: int = Query(0, ge=0),
):
    """
    Legacy endpoint: Retorna ratios de TXAR en formato 'largo'
    (ticker, concepto, valor, período)
    """
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        """
        SELECT
            ticker, concepto, valor, moneda, escala,
            period_end, nivel_certificacion
        FROM silver_norm
        ORDER BY period_end DESC, concepto
        LIMIT %s OFFSET %s
        """,
        (limit, skip),
    )
    rows = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS n FROM silver_norm")
    # RealDictCursor devuelve dict, no tupla: fetchone()[0] tira KeyError.
    total = cursor.fetchone()["n"]

    cursor.close()
    conn.close()

    return {
        "count": len(rows),
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [serialize_row(r) for r in rows],
    }


@app.get("/v1/validaciones")
def get_validaciones(limit: int = Query(100)):
    """Legacy: Validaciones de datos"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT * FROM validaciones LIMIT %s",
        (limit,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        "count": len(rows),
        "data": [serialize_row(r) for r in rows],
    }


@app.get("/v1/certificacion")
def get_certificacion(limit: int = Query(100)):
    """Legacy: Nivel de certificación por período"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT * FROM certificacion_nueva LIMIT %s",
        (limit,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        "count": len(rows),
        "data": [serialize_row(r) for r in rows],
    }


@app.get("/v1/mep")
def get_mep():
    """Current MEP rate (dólar MEP)"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM mep_actual LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return {"mep": None, "date": None, "note": "No current MEP data"}

    return serialize_row(row)


# ============= JOBS ENDPOINTS (Nuevos) =============

jobs_db = {}
job_counter = 0

@app.get("/v2/jobs")
def get_jobs():
    """Lista todos los jobs"""
    return {
        "count": len(jobs_db),
        "data": list(jobs_db.values())
    }

@app.get("/v2/jobs/{job_id}")
def get_job(job_id: str):
    """Obtiene detalles de un job específico"""
    job = jobs_db.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return job

@app.post("/v2/jobs/create")
def create_job(job_type: str = "update_prices"):
    """Crea un nuevo job"""
    global job_counter
    job_counter += 1
    job_id = f"job_{job_counter}"

    job = {
        "id": job_id,
        "type": job_type,
        "status": "running",
        "progress": 0,
        "created_at": datetime.now().isoformat(),
        "logs": [f"Job {job_id} iniciado"]
    }
    jobs_db[job_id] = job
    return job

@app.get("/v2/jobs/{job_id}/logs")
def get_job_logs(job_id: str):
    """Obtiene logs de un job"""
    job = jobs_db.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return {"logs": job.get("logs", [])}

@app.post("/v2/jobs/{job_id}/update")
def update_job(job_id: str, status: str = None, progress: int = None, log: str = None):
    """Actualiza estado de un job"""
    job = jobs_db.get(job_id)
    if not job:
        return {"error": "Job not found"}

    if status:
        job["status"] = status
    if progress is not None:
        job["progress"] = progress
    if log:
        job["logs"].append(log)

    return job


if __name__ == "__main__":
    import uvicorn
    from datetime import datetime

    uvicorn.run(
        app,
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8100")),
        log_level="info",
    )
