# -*- coding: utf-8 -*-
"""
MATRIZ DE TESTS -- Market Data (10 escenarios del contrato + extras)
=====================================================================
  1  primera corrida
  2  segunda corrida identica          -> idempotencia real (0 writes)
  3  nueva rueda
  4  cambio real en rueda finalizada   -> HISTORICAL_RESTATEMENT
  5  cambio solo en campo de ruido     -> ADJ_NOISE, no escribe
  6  intraday                          -> INTRADAY_UPDATE, no es corrupcion
  7  partial failure (lote)
  8  retry / recovery
  9  RAW corrupto (payload y en disco)
 10  duplicate input
 11  (extra) cuarentena por regresion de cobertura
 12  (extra) bateria completa de gates C-MKT

Sin red: toda fuente es FixtureSource. La base es descartable.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import m2_fetch_engine as eng                              # noqa: E402
import m4_quality as q                                     # noqa: E402
import market_core as core                                 # noqa: E402
from market_source import (FixtureSource, RawCorruptError,  # noqa: E402
                           YahooSource, validar_payload)

from conftest import (META_BUE, META_NY, TZ_BUE, alta_instrumento,  # noqa: E402
                      contar, resultado, ruedas, serie, uno)

HOY_BUE = datetime.now(TZ_BUE).date()
AYER_HABIL = ruedas(1, HOY_BUE - timedelta(days=1))[0]


def _spec(conn, iid="T1", ticker="TST.BA"):
    return alta_instrumento(conn, iid, f"E{iid}", "TST", ticker, "ARS", "BUE")


def _correr(conn, spec, df, stage, metadata=META_BUE, snapshot=True, guion=None):
    src = FixtureSource(guion or [resultado(df, metadata)],
                        snapshot_payload={"last_price": 101.0, "currency": "ARS",
                                          "volume": 1234})
    return eng.run_instrument(conn, spec, src, stage, con_snapshot=snapshot)


def _gates(rep):
    return {g[0]: (g[1], g[2]) for g in rep.gates}


# ------------------------------------------------------ 1. primera corrida

def test_01_primera_corrida(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(30, AYER_HABIL)
    rep = _correr(conn, spec, serie(fechas), "m1")

    assert rep.status == "SUCCESS", rep.error
    assert rep.rows == 30
    assert rep.resumen["por_tipo"] == {"NEW": 30}
    assert rep.resumen["por_motivo"] == {core.R_INITIAL_LOAD: 30}
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily") == 30
    assert uno(conn, "SELECT COUNT(*) FROM market_data_changes "
                     "WHERE change_type='NEW'") == 30
    assert uno(conn, "SELECT status FROM market_fetch_log "
                     "WHERE run_id=%s", (rep.run_id,)) == "SUCCESS"

    # RAW archivado y registrado con su sha real
    rel = uno(conn, "SELECT rel_path FROM market_raw_files "
                    "WHERE run_id=%s AND kind='HISTORY_CSV'", (rep.run_id,))
    p = eng.ROOT / rel
    assert p.exists()
    assert core.sha256_hex(p.read_bytes()) == rep.raw_sha256

    g = _gates(rep)
    for code in ("C-MKT-001", "C-MKT-002", "C-MKT-004", "C-MKT-005",
                 "C-MKT-006", "C-MKT-007", "C-MKT-008", "C-MKT-009",
                 "C-MKT-012", "C-MKT-017"):
        assert g[code][0] == "VALID", (code, g[code])
    assert g["C-MKT-013"][0] == "NOT_APPLICABLE"


# --------------------------------------------- 2. segunda corrida identica

def test_02_segunda_corrida_identica(limpiar):
    conn = limpiar
    spec = _spec(conn)
    df = serie(ruedas(30, AYER_HABIL))
    r1 = _correr(conn, spec, df, "m2a")
    provenance_1 = dict(contar(conn, "SELECT trading_date, source_run_id, "
                                     "source_hash, fetched_at_utc "
                                     "FROM market_price_daily") and
                        {r[0]: (r[1], r[2], r[3]) for r in
                         contar(conn, "SELECT trading_date, source_run_id, "
                                      "source_hash, fetched_at_utc "
                                      "FROM market_price_daily")})
    r2 = _correr(conn, spec, df, "m2b")

    assert r2.status == "SIN_CAMBIOS"
    assert r2.resumen["idempotente"] is True
    assert r2.resumen["filas_escritas"] == 0
    assert r2.resumen["por_tipo"] == {"UNCHANGED": 30}
    # ni una fila de auditoria nueva
    assert uno(conn, "SELECT COUNT(*) FROM market_data_changes "
                     "WHERE curr_run_id=%s", (r2.run_id,)) == 0
    # provenance intacta: sigue apuntando a la corrida que produjo el valor
    provenance_2 = {r[0]: (r[1], r[2], r[3]) for r in
                    contar(conn, "SELECT trading_date, source_run_id, "
                                 "source_hash, fetched_at_utc "
                                 "FROM market_price_daily")}
    assert provenance_2 == provenance_1
    assert all(v[0] == r1.run_id for v in provenance_2.values())
    # el fingerprint del lote es identico entre corridas
    assert r2.batch_hash == r1.batch_hash
    assert _gates(r2)["C-MKT-013"][0] == "VALID"


# -------------------------------------------------------- 3. nueva rueda

def test_03_nueva_rueda(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(31, AYER_HABIL)
    r1 = _correr(conn, spec, serie(fechas[:-1]), "m3a")
    r2 = _correr(conn, spec, serie(fechas), "m3b")

    assert r2.status == "SUCCESS"
    assert r2.resumen["por_tipo"] == {"UNCHANGED": 30, "NEW": 1}
    assert r2.resumen["por_motivo"][core.R_NEW_SESSION] == 1
    assert r2.resumen["filas_escritas"] == 1
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily") == 31
    # solo la rueda nueva quedo con la corrida nueva
    nuevas = contar(conn, "SELECT trading_date FROM market_price_daily "
                          "WHERE source_run_id=%s", (r2.run_id,))
    assert [x[0] for x in nuevas] == [fechas[-1]]
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily "
                     "WHERE source_run_id=%s", (r1.run_id,)) == 30
    assert _gates(r2)["C-MKT-013"][0] == "VALID"     # NEW_SESSION es benigno


# ---------------------------------------- 4. cambio real (rueda finalizada)

def test_04_cambio_real_en_rueda_finalizada(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(30, AYER_HABIL)
    df = serie(fechas)
    _correr(conn, spec, df, "m4a")

    df2 = df.copy()
    objetivo = df2.index[5]
    df2.loc[objetivo, "Close"] = float(df2.loc[objetivo, "Close"]) + 3.0
    df2.loc[objetivo, "High"] = float(df2.loc[objetivo, "Close"]) + 1.0
    r2 = _correr(conn, spec, df2, "m4b")

    assert r2.status == "SUCCESS"
    assert r2.resumen["por_tipo"]["CHANGED"] == 1
    assert r2.resumen["por_motivo"][core.R_HISTORICAL_RESTATEMENT] == 1
    assert r2.resumen["cambios_no_benignos"] == 1
    assert r2.resumen["filas_escritas"] == 1

    fila = contar(conn, """SELECT change_type, reason, old_hash, new_hash,
                                  old_value->>'close', new_value->>'close'
                           FROM market_data_changes
                           WHERE curr_run_id=%s""", (r2.run_id,))
    assert len(fila) == 1
    ct, reason, oh, nh, old_c, new_c = fila[0]
    assert (ct, reason) == ("CHANGED", core.R_HISTORICAL_RESTATEMENT)
    assert oh != nh and float(new_c) == pytest.approx(float(old_c) + 3.0)
    # un restatement historico NO es benigno: el gate lo marca
    assert _gates(r2)["C-MKT-013"][0] == "INVALID"


# ------------------------------------------- 5. cambio solo en campo ruido

def test_05_cambio_solo_en_campo_de_ruido(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(30, AYER_HABIL)
    df = serie(fechas)
    r1 = _correr(conn, spec, df, "m5a")

    df2 = df.copy()
    # re-calculo float del factor de ajuste: ruido relativo ~1e-7
    df2["Adj Close"] = [round(v * (1 + 1e-7), 8) for v in df2["Adj Close"]]
    r2 = _correr(conn, spec, df2, "m5b")

    assert r2.status == "SIN_CAMBIOS"
    # dos defensas en serie: la cuantizacion a 5 digitos significativos absorbe
    # la mayoria del ruido (IDENTICAL) y la tolerancia relativa absorbe el resto
    # (ADJ_NOISE). Ninguna fila puede terminar en CHANGED.
    assert set(r2.resumen["por_tipo"]) == {"UNCHANGED"}
    assert set(r2.resumen["por_motivo"]) <= {"IDENTICAL", core.R_ADJ_NOISE}
    assert r2.resumen["por_motivo"].get(core.R_ADJ_NOISE, 0) > 0
    assert r2.resumen["filas_escritas"] == 0
    assert uno(conn, "SELECT COUNT(*) FROM market_data_changes "
                     "WHERE curr_run_id=%s", (r2.run_id,)) == 0
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily "
                     "WHERE source_run_id=%s", (r1.run_id,)) == 30

    # el mismo campo, movido por encima de la tolerancia, SI es un cambio
    df3 = df.copy()
    df3["Adj Close"] = [round(v * 1.01, 8) for v in df3["Adj Close"]]
    r3 = _correr(conn, spec, df3, "m5c")
    assert r3.resumen["por_motivo"][core.R_ADJ_CLOSE_RECALC] == 30
    assert r3.resumen["filas_escritas"] == 30
    # y el business_hash NO cambio: solo el full_hash
    assert r3.batch_hash == r1.batch_hash


# -------------------------------------------------------------- 6. intraday

def test_06_intraday(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(29, AYER_HABIL) + [HOY_BUE]
    df = serie(fechas)
    _correr(conn, spec, df, "m6a")

    # el mercado sigue abierto: la rueda del dia se mueve
    df2 = df.copy()
    hoy_idx = df2.index[-1]
    df2.loc[hoy_idx, "Close"] = float(df2.loc[hoy_idx, "Close"]) + 2.5
    df2.loc[hoy_idx, "High"] = float(df2.loc[hoy_idx, "Close"]) + 0.5
    df2.loc[hoy_idx, "Volume"] = int(df2.loc[hoy_idx, "Volume"]) + 5000
    df2.loc[hoy_idx, "Adj Close"] = float(df2.loc[hoy_idx, "Close"]) * 0.93
    r2 = _correr(conn, spec, df2, "m6b")

    assert r2.resumen["por_tipo"]["CHANGED"] == 1
    assert r2.resumen["por_motivo"][core.R_INTRADAY_UPDATE] == 1
    assert r2.resumen["cambios_no_benignos"] == 0      # NO es corrupcion
    assert _gates(r2)["C-MKT-013"][0] == "VALID"
    # el valor nuevo quedo persistido con la corrida nueva
    assert float(uno(conn, """SELECT close FROM market_price_daily
                              WHERE instrument_id='T1' AND trading_date=%s""",
                    (HOY_BUE,))) == pytest.approx(
        float(df2.loc[hoy_idx, "Close"]), rel=1e-9)
    # la sesion del dia esta clasificada como CURRENT y las previas FINALIZED
    assert core.session_state(HOY_BUE, TZ_BUE) == core.CURRENT
    assert core.session_state(fechas[0], TZ_BUE) == core.FINALIZED
    # una fecha posterior a hoy seria FUTURE (gate C-MKT-008)
    assert core.session_state(HOY_BUE + timedelta(days=1), TZ_BUE) == core.FUTURE


# ------------------------------------------------------- 7. partial failure

def test_07_partial_failure_en_lote(limpiar):
    conn = limpiar
    s1 = alta_instrumento(conn, "T1", "E1", "AAA", "TST.BA", "ARS", "BUE")
    s2 = alta_instrumento(conn, "T2", "E2", "BBB", "TST", "USD", "NYSE",
                          itype="ADR")
    fechas = ruedas(20, AYER_HABIL)

    ok = _correr(conn, s1, serie(fechas), "m7")
    caido = eng.run_instrument(
        conn, s2,
        FixtureSource([RuntimeError("HTTP 502 upstream")]), "m7")

    assert ok.status == "SUCCESS"
    assert caido.status == "FAILED"
    assert "502" in caido.error
    # el instrumento sano quedo intacto; el caido no escribio nada
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily "
                     "WHERE instrument_id='T1'") == 20
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily "
                     "WHERE instrument_id='T2'") == 0
    # la falla queda registrada como hecho, con fuente y motivo
    assert uno(conn, "SELECT status FROM market_fetch_log WHERE run_id=%s",
               (caido.run_id,)) == "FAILED"
    assert uno(conn, "SELECT error_type FROM market_fetch_log WHERE run_id=%s",
               (caido.run_id,)) == "RuntimeError"
    assert uno(conn, "SELECT status FROM market_raw_runs WHERE run_id=%s",
               (caido.run_id,)) == "FAILED"
    assert _gates(caido)["C-MKT-002"][0] == "INVALID"
    # no se archivo RAW de una corrida fallida
    assert uno(conn, "SELECT COUNT(*) FROM market_raw_files WHERE run_id=%s",
               (caido.run_id,)) == 0


# ------------------------------------------------------- 8. retry/recovery

def test_08_retry_dentro_de_la_fuente():
    """El reintento vive en la Source: 2 fallos y a la tercera responde."""
    fechas = ruedas(10, AYER_HABIL)
    df = serie(fechas)
    intentos = {"n": 0}

    class _Tk:
        history_metadata = META_BUE

        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, **params):
            intentos["n"] += 1
            if intentos["n"] < 3:
                raise ConnectionError("rate limited")
            return df

    class _YF:
        __version__ = "fake"

        @staticmethod
        def Ticker(symbol):
            return _Tk(symbol)

    src = YahooSource(retries=2, backoff_s=0)
    src._yf = _YF
    res = src.fetch("TST.BA")
    assert res.ok and res.attempts == 3 and res.rows == 10

    # agotados los reintentos, la falla se reporta (no se inventa un vacio)
    intentos["n"] = -99
    src2 = YahooSource(retries=1, backoff_s=0)
    src2._yf = _YF
    r2 = src2.fetch("TST.BA")
    assert not r2.ok and r2.error_type == "ConnectionError" and r2.attempts == 2


def test_08b_recovery_tras_falla(limpiar):
    """Una corrida fallida no deja estado sucio y la siguiente se recupera."""
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(20, AYER_HABIL)

    r_fail = eng.run_instrument(
        conn, spec, FixtureSource([TimeoutError("timeout")]), "m8a")
    assert r_fail.status == "FAILED"
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily") == 0

    r_ok = _correr(conn, spec, serie(fechas), "m8b")
    assert r_ok.status == "SUCCESS" and r_ok.rows == 20
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily") == 20
    # la corrida fallida no es candidata a prev_run
    prev = uno(conn, "SELECT prev_run_id FROM market_data_changes "
                     "WHERE curr_run_id=%s LIMIT 1", (r_ok.run_id,))
    assert prev is None

    # y una tercera corrida identica vuelve a ser idempotente
    r3 = _correr(conn, spec, serie(fechas), "m8c")
    assert r3.status == "SIN_CAMBIOS" and r3.resumen["filas_escritas"] == 0


# ---------------------------------------------------------- 9. RAW corrupto

def test_09_payload_corrupto_no_se_persiste(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(20, AYER_HABIL)
    _correr(conn, spec, serie(fechas), "m9a")
    antes = contar(conn, "SELECT trading_date, source_hash "
                         "FROM market_price_daily ORDER BY 1")

    import pandas as pd
    basura = pd.DataFrame({"foo": [1, 2, 3]})
    with pytest.raises(RawCorruptError):
        validar_payload(basura)

    rep = eng.run_instrument(
        conn, spec,
        FixtureSource([RawCorruptError("columnas ausentes: ['Open',...]")]),
        "m9b")
    assert rep.status == "FAILED"
    assert _gates(rep)["C-MKT-002"][0] == "INVALID"
    # la serie previa quedo intacta, byte por byte
    assert contar(conn, "SELECT trading_date, source_hash "
                        "FROM market_price_daily ORDER BY 1") == antes


def test_09b_raw_alterado_en_disco_lo_detecta_el_gate(limpiar):
    conn = limpiar
    spec = _spec(conn)
    rep = _correr(conn, spec, serie(ruedas(20, AYER_HABIL)), "m9c")

    b = q.Bateria(conn, "gate-raw-ok", raw_root=eng.ROOT)
    b.gates_globales(["T1"])
    conn.commit()
    g15 = [r for r in b.resultados if r["check"] == "C-MKT-015"][0]
    assert g15["severity"] == "VALID", g15["detail"]

    rel = uno(conn, "SELECT rel_path FROM market_raw_files "
                    "WHERE run_id=%s AND kind='HISTORY_CSV'", (rep.run_id,))
    p = eng.ROOT / rel
    original = p.read_bytes()
    p.write_bytes(original.replace(b"100.0", b"999.0", 1))
    try:
        b2 = q.Bateria(conn, "gate-raw-tamper", raw_root=eng.ROOT)
        b2.gates_globales(["T1"])
        conn.commit()
        g = [r for r in b2.resultados if r["check"] == "C-MKT-015"][0]
        assert g["severity"] == "INVALID"
        assert "alterados=1" in g["detail"]
    finally:
        p.write_bytes(original)


# ------------------------------------------------------ 10. duplicate input

def test_10_duplicate_input(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(20, AYER_HABIL)
    df = serie(fechas)
    import pandas as pd
    dup = pd.concat([df, df.iloc[[7]]])                    # fecha repetida identica
    rep = _correr(conn, spec, dup, "m10a")

    assert rep.rows == 20                                  # deduplicado
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily") == 20
    g = _gates(rep)
    assert g["C-MKT-005"][0] == "WARNING" and "1 fecha" in g["C-MKT-005"][1]

    # duplicado CONFLICTIVO (mismo dia, valores distintos) -> INVALID
    otra = df.iloc[[7]].copy()
    otra["Close"] = float(otra["Close"].iloc[0]) + 9.0
    dup2 = pd.concat([df, otra])                           # `otra` es la ultima
    rep2 = _correr(conn, spec, dup2, "m10b")
    g2 = _gates(rep2)
    assert g2["C-MKT-005"][0] == "INVALID"
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily") == 20
    # gano la ultima aparicion, y quedo auditada como cambio
    assert float(uno(conn, """SELECT close FROM market_price_daily
                              WHERE trading_date=%s""",
                    (fechas[7],))) == pytest.approx(float(otra["Close"].iloc[0]))


# ------------------------------ 11. cuarentena por regresion de cobertura

def test_11_cuarentena_por_regresion_de_cobertura(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(40, AYER_HABIL)
    _correr(conn, spec, serie(fechas), "m11a")
    antes = contar(conn, "SELECT trading_date, close FROM market_price_daily "
                         "ORDER BY 1")

    truncada = serie(fechas[-10:])                        # la fuente devuelve 10
    rep = eng.run_instrument(
        conn, spec, FixtureSource([resultado(truncada, META_BUE)]), "m11b")

    assert rep.status == "QUARANTINED"
    assert contar(conn, "SELECT trading_date, close FROM market_price_daily "
                        "ORDER BY 1") == antes            # nada se toco
    assert uno(conn, "SELECT status FROM market_raw_runs WHERE run_id=%s",
               (rep.run_id,)) == "PARTIAL"
    # el RAW sospechoso igual se archiva (evidencia), pero no se ingesta
    assert uno(conn, "SELECT COUNT(*) FROM market_raw_files WHERE run_id=%s",
               (rep.run_id,)) == 2
    assert _gates(rep)["C-MKT-003"][0] == "INVALID"


def test_11b_ruedas_ausentes_se_auditan_pero_no_se_borran(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(40, AYER_HABIL)
    _correr(conn, spec, serie(fechas), "m11c")

    import pandas as pd
    df = serie(fechas)
    faltan = df.drop(df.index[[3, 4]])                     # 38 filas: 95% > umbral
    rep = _correr(conn, spec, faltan, "m11d")

    assert rep.status in ("SUCCESS", "SIN_CAMBIOS")
    assert rep.faltantes == 2
    assert uno(conn, "SELECT COUNT(*) FROM market_price_daily") == 40
    assert uno(conn, """SELECT COUNT(*) FROM market_data_changes
                        WHERE curr_run_id=%s AND change_type='MISSING'""",
               (rep.run_id,)) == 2


# ---------------------------------------------- 12. bateria completa gates

def test_12_bateria_de_gates_completa(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(60, AYER_HABIL)
    df = serie(fechas, dividendos={fechas[10]: 1.25}, splits={fechas[30]: 2.0})
    _correr(conn, spec, df, "m12a")
    _correr(conn, spec, df, "m12b")

    b = q.Bateria(conn, "gates-full", raw_root=eng.ROOT)
    b.gates_globales(["T1"])
    resumen = b.gates_instrumento("T1")
    conn.commit()

    por_check = {}
    for r in b.resultados:
        prev = por_check.get(r["check"])
        if prev is None or q.SEV_ORDER[r["severity"]] > q.SEV_ORDER[prev]:
            por_check[r["check"]] = r["severity"]

    esperados = [f"C-MKT-{i:03d}" for i in range(1, 18)]
    assert sorted(por_check) == esperados, sorted(por_check)
    assert q.veredicto(b.resultados) == "PASS"
    assert all(v in ("VALID", "NOT_APPLICABLE") for v in por_check.values()), \
        {k: v for k, v in por_check.items() if v not in ("VALID", "NOT_APPLICABLE")}
    assert resumen["hash_mismatch"] == 0
    assert resumen["incoherencias_ohlc"] == 0
    # corporate actions separadas de la serie
    assert uno(conn, "SELECT COUNT(*) FROM market_corporate_actions "
                     "WHERE action_type='DIVIDEND'") == 1
    assert uno(conn, "SELECT COUNT(*) FROM market_corporate_actions "
                     "WHERE action_type='STOCK_SPLIT'") == 1


def test_12b_gate_detecta_moneda_divergente(limpiar):
    conn = limpiar
    spec = alta_instrumento(conn, "T1", "E1", "TST", "TST.BA", "ARS", "BUE")
    rep = _correr(conn, spec, serie(ruedas(10, AYER_HABIL)), "m12c",
                  metadata={**META_BUE, "currency": "USD"})
    g = _gates(rep)
    assert g["C-MKT-006"][0] == "INVALID"
    assert "esperada=ARS" in g["C-MKT-006"][1] and "fuente=USD" in g["C-MKT-006"][1]


def test_12c_gate_detecta_fecha_futura(limpiar):
    conn = limpiar
    spec = _spec(conn)
    fechas = ruedas(9, AYER_HABIL) + [HOY_BUE + timedelta(days=3)]
    rep = _correr(conn, spec, serie(fechas), "m12d")
    g = _gates(rep)
    assert g["C-MKT-008"][0] == "INVALID"


def test_12d_fingerprint_reconstruible_desde_la_base(limpiar):
    """La propiedad central: business_hash y full_hash se reconstruyen desde
    market_price_daily, sin columnas auxiliares."""
    conn = limpiar
    spec = _spec(conn)
    df = serie(ruedas(45, AYER_HABIL), dividendos={ruedas(45, AYER_HABIL)[5]: 0.7})
    rep = _correr(conn, spec, df, "m12e")

    filas = contar(conn, """SELECT trading_date, open, high, low, close,
                                   adj_close, volume, dividends, stock_splits,
                                   source_hash
                            FROM market_price_daily ORDER BY trading_date""")
    recon = []
    for (d, o, h, l, c, ac, v, dv, sp, sh) in filas:
        F = lambda x: None if x is None else float(x)     # noqa: E731
        r = core.make_row("T1", d, F(o), F(h), F(l), F(c), F(ac),
                          int(v), F(dv), F(sp))
        assert r.full_hash == sh
        recon.append(r)
    assert core.batch_hash(recon) == rep.batch_hash
