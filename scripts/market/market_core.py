# -*- coding: utf-8 -*-
"""
MARKET CORE -- logica pura de la capa Market Data (sin I/O, sin red, sin DB)
============================================================================
Unica fuente de verdad para:

  * normalizacion numerica  (norm_num / norm_vol / qsig)
  * fingerprints            (row_hashes -> business_hash + full_hash)
  * estado de sesion        (FINALIZED / CURRENT / FUTURE)
  * clasificacion de cambio (NEW / UNCHANGED / CHANGED + motivo)

Contrato de fingerprints
------------------------
business_hash : instrument_id | trading_date | O H L C | volumen | dividendos
                | splits.  TODOS esos campos estan persistidos en
                market_price_daily, por lo tanto el business_hash es
                RECONSTRUIBLE desde la base. La deteccion de cambios compara
                business_hash(actual) vs business_hash(reconstruido de la DB),
                nunca contra source_hash (que es el full_hash y ademas incluye
                Adj Close).

full_hash     : business + Adj Close cuantizado a 5 digitos significativos.
                Es lo que se persiste en market_price_daily.source_hash como
                fingerprint contractual de trazabilidad.

Por que Adj Close queda FUERA del business_hash: Yahoo recalcula el factor de
ajuste en cada corrida y devuelve ruido float relativo ~1e-6. Incluirlo haria
que toda la serie apareciera CHANGED en cada corrida (bug historico de la
fase). El ruido se absorbe con TOL_ADJ_REL y se reporta como campo de ruido.

Por que norm_num redondea a 6 decimales ANTES de persistir: Yahoo entrega
float32 (12.699999809265137). NUMERIC(18,8) truncaria a 12.69999981 y el hash
recalculado desde la base no coincidiria con el calculado desde el DataFrame
-> cambios fantasma. Redondeando a 6 decimales el valor sobrevive el
round-trip float -> NUMERIC(18,8) -> float sin perdida.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------- constantes

TOL_ADJ_REL = 1e-5          # tolerancia relativa de Adj Close (campo de ruido)
QSIG_OHLC = 8               # digitos significativos para OHLC en el hash
QSIG_ADJ = 5                # digitos significativos para Adj Close en el hash
PRICE_DECIMALS = 6          # redondeo previo a NUMERIC(18,8)

# estados de sesion
FINALIZED = "FINALIZED"     # rueda cerrada: cualquier cambio es restatement
CURRENT = "CURRENT"         # rueda del dia en la tz del mercado: puede moverse
FUTURE = "FUTURE"           # fecha posterior a hoy en la tz del mercado: invalida

# motivos de cambio (market_data_changes.reason)
R_INITIAL_LOAD = "INITIAL_LOAD"
R_NEW_SESSION = "NEW_SESSION"
R_INTRADAY_UPDATE = "INTRADAY_UPDATE"
R_CORPORATE_ACTION = "CORPORATE_ACTION"
R_VOLUME_RESTATEMENT = "VOLUME_RESTATEMENT"
R_HISTORICAL_RESTATEMENT = "HISTORICAL_RESTATEMENT"
R_ADJ_CLOSE_RECALC = "ADJ_CLOSE_RECALC"
R_ADJ_NOISE = "ADJ_NOISE"

# motivos que NO son sospecha de corrupcion (esperados por diseno)
BENIGN_REASONS = {R_INITIAL_LOAD, R_NEW_SESSION, R_INTRADAY_UPDATE,
                  R_CORPORATE_ACTION, R_ADJ_NOISE}


# ------------------------------------------------------------- normalizacion

def qsig(x: Any, digits: int = QSIG_OHLC) -> Optional[float]:
    """Cuantiza a N digitos significativos. None-safe."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:                                   # NaN
        return None
    return float(f"{f:.{digits}g}")


def norm_num(x: Any) -> Optional[float]:
    """float redondeado a PRICE_DECIMALS. None-safe. NaN -> None."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:
        return None
    return round(f, PRICE_DECIMALS)


def norm_vol(x: Any) -> Optional[int]:
    """Volumen entero. None-safe. NaN/basura -> None."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:
        return None
    return int(f)


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# -------------------------------------------------------------- fingerprints

def row_hashes(instrument_id, trading_date, o, h, l, c, adj, vol, div, split):
    """Devuelve (business_hash, full_hash) para una rueda.

    Todos los argumentos deben venir ya normalizados (norm_num / norm_vol) o
    leidos desde la base y convertidos a float/int. La funcion es simetrica:
    llamarla con los valores del DataFrame o con los valores releidos de
    PostgreSQL produce el mismo par de hashes.
    """
    base = "|".join(str(x) for x in (
        instrument_id, trading_date,
        qsig(o), qsig(h), qsig(l), qsig(c),
        vol, qsig(div), qsig(split)))
    bh = sha256_hex(base.encode())
    adj_q = "" if adj is None else str(qsig(adj, QSIG_ADJ))
    return bh, sha256_hex((base + "|" + adj_q).encode())


def batch_hash(rows) -> str:
    """Fingerprint del lote completo: SHA256 de los business_hash ordenados
    por fecha. Cambia si y solo si cambia algun hecho de negocio."""
    return sha256_hex("\n".join(
        r.business_hash for r in sorted(rows, key=lambda r: r.trading_date)
    ).encode())


# ------------------------------------------------------------------ modelo

@dataclass(frozen=True)
class PriceRow:
    trading_date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    adj_close: Optional[float]
    volume: Optional[int]
    dividends: float
    stock_splits: float
    business_hash: str
    full_hash: str

    @property
    def values(self):
        return (self.open, self.high, self.low, self.close, self.adj_close,
                self.volume, self.dividends, self.stock_splits)


@dataclass
class NormalizeReport:
    rows: list = field(default_factory=list)
    actions: list = field(default_factory=list)     # (date, type, value, ratio, hash)
    duplicates_dropped: int = 0
    duplicate_dates: list = field(default_factory=list)
    duplicates_conflicting: int = 0                 # duplicado con valores distintos
    nan_rows: int = 0
    tz: Optional[str] = None


def make_row(instrument_id, d, o, h, l, c, adj, vol, div, split) -> PriceRow:
    o, h, l, c = norm_num(o), norm_num(h), norm_num(l), norm_num(c)
    adj = norm_num(adj)
    vol = norm_vol(vol)
    div = norm_num(div) or 0.0
    split = norm_num(split) or 0.0
    bh, fh = row_hashes(instrument_id, d, o, h, l, c, adj, vol, div, split)
    return PriceRow(d, o, h, l, c, adj, vol, div, split, bh, fh)


def normalize_history(df, instrument_id) -> NormalizeReport:
    """DataFrame de yfinance -> filas normalizadas + corporate actions.

    * La fecha de mercado se toma del indice tz-aware TAL CUAL (nunca se
      convierte a UTC: eso correria la rueda un dia en BYMA/NYSE).
    * Indices duplicados: se conserva la ULTIMA aparicion y se reporta. Si las
      apariciones difieren en valores, se cuenta aparte (duplicate input
      conflictivo, escenario 10 de la matriz).
    """
    rep = NormalizeReport()
    if df is None or len(df) == 0:
        return rep
    # kind="stable": ante fechas repetidas el orden de origen se preserva, asi
    # "gana la ultima aparicion" es una regla determinista y no un azar del
    # algoritmo de ordenamiento.
    df = df.sort_index(kind="stable")
    rep.tz = str(getattr(df.index, "tz", None))

    def col(name, i):
        return df[name].iloc[i] if name in df.columns else None

    por_fecha = {}
    orden = []
    for i in range(len(df)):
        idx = df.index[i]
        d = idx.date() if hasattr(idx, "date") else idx
        row = make_row(instrument_id, d,
                       col("Open", i), col("High", i), col("Low", i),
                       col("Close", i), col("Adj Close", i), col("Volume", i),
                       col("Dividends", i), col("Stock Splits", i))
        if d in por_fecha:
            rep.duplicates_dropped += 1
            rep.duplicate_dates.append(d)
            if por_fecha[d].full_hash != row.full_hash:
                rep.duplicates_conflicting += 1
        else:
            orden.append(d)
        por_fecha[d] = row                       # ultima aparicion gana

    for d in orden:
        r = por_fecha[d]
        if r.close is None and r.open is None:
            rep.nan_rows += 1
        rep.rows.append(r)
        if r.dividends:
            rep.actions.append((d, "DIVIDEND", r.dividends, None, r.business_hash))
        if r.stock_splits:
            rep.actions.append((d, "STOCK_SPLIT", r.stock_splits,
                                abs(r.stock_splits), r.business_hash))
    return rep


# --------------------------------------------------------- estado de sesion

def session_state(trading_date: date, market_tz, now_utc: datetime = None) -> str:
    """FINALIZED / CURRENT / FUTURE segun la fecha de HOY en la tz del mercado.

    No se hardcodea ningun mercado: la tz llega del indice que devolvio la
    fuente para ese instrumento.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        hoy = now_utc.astimezone(market_tz).date() if market_tz else now_utc.date()
    except Exception:
        hoy = now_utc.date()
    if trading_date > hoy:
        return FUTURE
    if trading_date == hoy:
        return CURRENT
    return FINALIZED


# ------------------------------------------------- clasificacion de cambios

@dataclass
class RowDecision:
    trading_date: date
    change_type: str          # NEW | UNCHANGED | CHANGED
    reason: str
    session: str
    persist: bool             # si hay que escribir la fila
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None


def _as_dict(row: PriceRow) -> dict:
    return {"open": row.open, "high": row.high, "low": row.low,
            "close": row.close, "adj_close": row.adj_close,
            "volume": row.volume, "dividends": row.dividends,
            "stock_splits": row.stock_splits}


def classify_row(new: PriceRow, old: Optional[PriceRow], session: str,
                 first_load: bool = False) -> RowDecision:
    """Decide NEW / UNCHANGED / CHANGED y el motivo, comparando
    business_hash(nuevo) vs business_hash(reconstruido de la DB)."""
    if old is None:
        return RowDecision(
            new.trading_date, "NEW",
            R_INITIAL_LOAD if first_load else R_NEW_SESSION,
            session, True, None, new.business_hash, None, _as_dict(new))

    if new.business_hash != old.business_hash:
        if session == CURRENT:
            reason = R_INTRADAY_UPDATE
        elif (new.dividends != old.dividends
              or new.stock_splits != old.stock_splits):
            reason = R_CORPORATE_ACTION
        elif (new.open, new.high, new.low, new.close) == \
             (old.open, old.high, old.low, old.close):
            reason = R_VOLUME_RESTATEMENT
        else:
            reason = R_HISTORICAL_RESTATEMENT
        return RowDecision(new.trading_date, "CHANGED", reason, session, True,
                           old.business_hash, new.business_hash,
                           _as_dict(old), _as_dict(new))

    # negocio identico: solo puede diferir Adj Close (campo de ruido)
    if new.full_hash != old.full_hash:
        if new.adj_close is None or old.adj_close is None:
            return RowDecision(new.trading_date, "CHANGED", R_ADJ_CLOSE_RECALC,
                               session, True, old.full_hash, new.full_hash,
                               _as_dict(old), _as_dict(new))
        den = max(abs(old.adj_close), 1e-12)
        if abs(new.adj_close - old.adj_close) / den > TOL_ADJ_REL:
            return RowDecision(new.trading_date, "CHANGED", R_ADJ_CLOSE_RECALC,
                               session, True, old.full_hash, new.full_hash,
                               _as_dict(old), _as_dict(new))
        # variacion por debajo de tolerancia -> ruido, no se persiste
        return RowDecision(new.trading_date, "UNCHANGED", R_ADJ_NOISE,
                           session, False, old.full_hash, new.full_hash)

    return RowDecision(new.trading_date, "UNCHANGED", "IDENTICAL", session,
                       False, old.full_hash, new.full_hash)


def classify_batch(nuevas, existentes: dict, market_tz, now_utc=None):
    """nuevas: [PriceRow]; existentes: {date: PriceRow reconstruida de la DB}.
    Devuelve [RowDecision] en el mismo orden que `nuevas`."""
    first_load = not existentes
    return [classify_row(r, existentes.get(r.trading_date),
                         session_state(r.trading_date, market_tz, now_utc),
                         first_load)
            for r in nuevas]


def summarize(decisions) -> dict:
    """Resumen por tipo y por motivo + si la corrida es idempotente."""
    por_tipo, por_motivo = {}, {}
    for d in decisions:
        por_tipo[d.change_type] = por_tipo.get(d.change_type, 0) + 1
        por_motivo[d.reason] = por_motivo.get(d.reason, 0) + 1
    escritas = sum(1 for d in decisions if d.persist)
    sospechosas = [d for d in decisions
                   if d.change_type == "CHANGED" and d.reason not in BENIGN_REASONS]
    return {"total": len(decisions), "por_tipo": por_tipo,
            "por_motivo": por_motivo, "filas_escritas": escritas,
            "idempotente": escritas == 0,
            "cambios_no_benignos": len(sospechosas),
            "fechas_no_benignas": [str(d.trading_date) for d in sospechosas[:20]]}


# ----------------------------------------------------------- validez OHLC

def ohlc_violations(row: PriceRow) -> list:
    """Lista de violaciones de coherencia OHLC de UNA fila (vacia = sana)."""
    v = []
    o, h, l, c = row.open, row.high, row.low, row.close
    if None in (o, h, l, c):
        v.append("NULL_OHLC")
        return v
    eps = 1e-9
    if h < l - eps:
        v.append("HIGH_LT_LOW")
    if h < o - eps:
        v.append("HIGH_LT_OPEN")
    if h < c - eps:
        v.append("HIGH_LT_CLOSE")
    if l > o + eps:
        v.append("LOW_GT_OPEN")
    if l > c + eps:
        v.append("LOW_GT_CLOSE")
    if o <= 0 or c <= 0 or h <= 0 or l <= 0:
        v.append("NON_POSITIVE")
    if row.volume is not None and row.volume < 0:
        v.append("NEGATIVE_VOLUME")
    return v
