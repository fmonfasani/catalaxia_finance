"""EV/Sales — el primer ratio del motor canonico (S1).

Cubre las diez familias del contrato de tests para este ratio:

  1 formula correctness      6 zero denominator
  2 identity isolation       7 provenance completeness
  3 cross-entity contam.     8 idempotency
  4 FY vs TTM identity       9 mutation
  5 missing input           10 persistence

COMO SE MANIPULA LA BASE SIN ROMPERLA
Los tests que necesitan un dato adverso lo insertan dentro de una transaccion
que SIEMPRE se revierte (`_tx`). Nada queda escrito. Los que solo miden el
estado corren en lectura pura sobre lo que el motor ya persistio.

EL DONANTE DE METADATA
Para fabricar un hecho que PASE la guarda de pertenencia hay que respetar su
regla: `qname` del hecho derivado igual al de la fila de `parsed.facts` que
citan sus `source_fact_ids`. Por eso los escenarios clonan una fila real del
propio emisor y cambian solo `tag` y `value_numeric` -- `tag` no participa de la
guarda, `qname` si. Es la unica forma honesta de probar el resto de las reglas
sin desactivar la primera.
"""
from __future__ import annotations

import hashlib
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine.config import load_settings  # noqa: E402
from engine.db import get_admin_engine  # noqa: E402

import ratio_engine as RE  # noqa: E402

AAPL = "0000320193"
GGAL = "0001114700"   # banco: no publica ningun tag de ingresos -> NOT_CALCULABLE
CEPU = "0001717161"   # no publica ningun tag de deuda financiera


@pytest.fixture(scope="module")
def eng():
    s = load_settings()
    if s.is_prod:
        pytest.skip("EXT-010: no se ejecuta contra produccion")
    return get_admin_engine(s)


@pytest.fixture
def conn(eng):
    with eng.connect() as c:
        yield c


@pytest.fixture
def tx(eng):
    """Conexion con transaccion que se revierte SIEMPRE. Nada queda escrito."""
    with eng.connect() as c:
        t = c.begin()
        try:
            yield c
        finally:
            t.rollback()


def _clonar_fact(c, cik: str, tag_nuevo: str, valor, *, ajeno_de: str | None = None):
    """Clona un hecho real del emisor cambiandole `tag` y valor.

    `qname` se conserva -- es lo que la guarda compara contra `parsed.facts` --
    salvo cuando `ajeno_de` pide justamente lo contrario: robarle los punteros a
    otro emisor, que es el ataque.
    """
    donante = c.execute(text("""
        SELECT * FROM derived.fact
         WHERE valid_to IS NULL AND cik = :c AND is_numeric AND NOT is_dimensional
           AND value_numeric IS NOT NULL
           AND COALESCE(instant_date::text, end_date::text) = report_period::text
           AND report_period = (SELECT max(report_period) FROM derived.fact
                                 WHERE valid_to IS NULL AND cik = :c)
         ORDER BY fact_key LIMIT 1"""), {"c": cik}).mappings().one()
    src = donante["source_fact_ids"]
    if ajeno_de is not None:
        src = c.execute(text("""
            SELECT source_fact_ids FROM derived.fact
             WHERE valid_to IS NULL AND cik = :c AND is_numeric
             ORDER BY report_period DESC, fact_key LIMIT 1"""), {"c": ajeno_de}).scalar_one()
    c.execute(text("""
        INSERT INTO derived.fact (
          fact_key, entity_key, cik, accession_number, form, filing_date,
          report_period, qname, namespace, tag, is_custom, context_id, period_kind,
          start_date, end_date, instant_date, is_dimensional, dim_count, dimensions,
          unit_ref, unit_kind, unit_measure, currency, value_numeric, value_text,
          is_nil, is_numeric, decimals, n_fuentes, source_fact_ids, desempate,
          input_checkpoint_id, run_id, unidad_resuelta)
        VALUES (:fk, :ek, :cik, :acc, :form, :fd, :rp, :qn, :ns, :tag, false, :ctx,
                :pk, :sd, :ed, :idt, false, 0, NULL, :ur, :uk, :um, :cur, :val,
                NULL, false, true, NULL, :nf, :src, 'UNICO', :chk, :run, true)"""), {
        "fk": hashlib.sha256(f"TEST-{tag_nuevo}-{cik}".encode()).hexdigest(),
        "ek": donante["entity_key"], "cik": cik,
        "acc": donante["accession_number"], "form": donante["form"],
        "fd": donante["filing_date"], "rp": donante["report_period"],
        "qn": donante["qname"], "ns": donante["namespace"], "tag": tag_nuevo,
        "ctx": donante["context_id"] + "-test", "pk": donante["period_kind"],
        "sd": donante["start_date"], "ed": donante["end_date"],
        "idt": donante["instant_date"], "ur": donante["unit_ref"],
        "uk": donante["unit_kind"], "um": donante["unit_measure"],
        "cur": donante["currency"], "val": valor, "src": list(src),
        "nf": len(list(src)),
        "chk": donante["input_checkpoint_id"], "run": donante["run_id"]})
    return dict(donante)


# ═══════════════════════════════════════════════ 1 · formula correctness ════

def test_formula_correctness_ev_sales_se_reconstruye_a_mano(conn):
    """El valor persistido debe salir de sus propios insumos, a mano.

    Si la formula cambia y el numero no, o al reves, este test lo ve.
    """
    fila = conn.execute(text("""
        SELECT value, inputs, currency, formula_version FROM derived.ratio
         WHERE canonical_id = 'ev_sales' AND cik = :c AND valid_to IS NULL"""),
        {"c": AAPL}).mappings().one()
    ins = {i["rol"]: i for i in fila["inputs"]}
    mcap = (Decimal(str(ins["precio"]["valor"])) / Decimal(str(ins["precio"]["ratio_adr"]))
            ) * Decimal(str(ins["acciones"]["valor"]))
    ev = mcap + Decimal(str(ins["deuda"]["valor"])) - Decimal(str(ins["efectivo"]["valor"]))
    esperado = ev / Decimal(str(ins["ingresos"]["valor"]))
    assert abs(Decimal(str(fila["value"])) - esperado) < Decimal("0.000002"), (
        f"persistido {fila['value']} != recalculado {esperado}")
    assert fila["formula_version"] == "ev_sales_v1"
    # y los derivados que la fila declara coinciden con los recalculados
    der = {i["concepto"]: Decimal(str(i["valor"]))
           for i in fila["inputs"] if i["rol"] == "derivado"}
    assert abs(der["market_cap"] - mcap) < Decimal("0.01")
    assert abs(der["enterprise_value"] - ev) < Decimal("0.01")


def test_formula_correctness_no_hay_ratio_sin_los_cuatro_insumos(conn):
    """Todo CALCULADO cita ingresos, deuda, efectivo, acciones y precio."""
    filas = conn.execute(text("""
        SELECT cik, inputs FROM derived.ratio
         WHERE canonical_id = 'ev_sales' AND status = 'CALCULADO' AND valid_to IS NULL""")
        ).mappings().all()
    assert filas, "no hay ningun ev_sales calculado para auditar"
    for f in filas:
        roles = {i["rol"] for i in f["inputs"]}
        faltan = {"ingresos", "deuda", "efectivo", "acciones", "precio"} - roles
        assert not faltan, f"{f['cik']} calculado sin citar {faltan}"


# ═════════════════════════════════════════════════ 2 · identity isolation ═══

def test_identity_isolation_sin_assertion_verified_no_hay_ratio(conn):
    """La entidad se resuelve por CIK con assertion VERIFIED, no por ticker."""
    r = RE.calcular_ev_sales(conn, "0009999999")
    assert r["status"] == "REVIEW_REQUIRED"
    assert "VERIFIED" in r["motivo"]
    assert r["entity_key"] is None


def test_identity_isolation_el_entity_key_persistido_es_el_de_identity(conn):
    """El entity_key de cada fila debe ser el que identity_v1 da para ese CIK."""
    filas = conn.execute(text("""
        SELECT r.cik, r.entity_key, i.entity_key AS esperado
          FROM derived.ratio r
          JOIN identity_v1.identifier i
            ON i.id_type = 'CIK' AND i.id_value = r.cik AND i.valid_to IS NULL
         WHERE r.canonical_id = 'ev_sales' AND r.valid_to IS NULL""")).mappings().all()
    assert filas
    for f in filas:
        assert f["entity_key"] == f["esperado"], f"{f['cik']}: entity_key ajeno"


# ═══════════════════════════════════════ 3 · cross-entity contamination ═════

def test_cross_entity_un_fact_ajeno_no_entra_al_ratio(tx):
    """A7 al nivel del motor.

    A CEPU -- al que le falta exactamente UN concepto, `deuda_financiera` -- se
    le inyecta un `Borrowings` cuyos punteros de provenance son de AAPL. Sin la
    guarda el ratio se completaria con un dato ajeno; con la guarda no.
    """
    antes = RE.calcular_ev_sales(tx, CEPU)
    assert antes["status"] == "NOT_CALCULABLE" and "deuda_financiera" in antes["motivo"]

    _clonar_fact(tx, CEPU, "Borrowings", Decimal("90678000000"), ajeno_de=AAPL)

    despues = RE.calcular_ev_sales(tx, CEPU)
    assert despues["status"] == "NOT_CALCULABLE", (
        f"el motor adopto un hecho de AAPL bajo el CIK de CEPU: {despues.get('value')}")
    assert "deuda_financiera" in despues["motivo"], despues["motivo"]
    assert "Borrowings" not in {i.get("tag_elegido") for i in despues["inputs"]}


def test_cross_entity_ningun_insumo_persistido_pertenece_a_otro_emisor(conn):
    """T12 a escala: cada fact_key citado debe ser del mismo emisor de la fila."""
    ajenos = conn.execute(text("""
        SELECT count(*)
          FROM derived.ratio r
          CROSS JOIN LATERAL jsonb_array_elements(r.inputs) i
          JOIN derived.fact d ON d.fact_key = i->>'fact_key'
         WHERE r.valid_to IS NULL AND i ? 'fact_key'
           AND (d.cik <> r.cik OR d.entity_key <> r.entity_key)""")).scalar_one()
    assert ajenos == 0, f"{ajenos} insumos persistidos pertenecen a otro emisor"


def test_cross_entity_la_evidencia_citada_es_del_mismo_cik(conn):
    """La provenance de cada insumo apunta a parsed.facts del mismo emisor."""
    malos = conn.execute(text("""
        SELECT count(*)
          FROM derived.ratio r
          CROSS JOIN LATERAL jsonb_array_elements(r.inputs) i
         WHERE r.valid_to IS NULL
           AND i->'evidencia'->>'parsed_cik' IS NOT NULL
           AND i->'evidencia'->>'parsed_cik' <> r.cik""")).scalar_one()
    assert malos == 0, f"{malos} insumos citan provenance de otro CIK"


# ══════════════════════════════════════════════ 4 · FY vs TTM identity ══════

def test_fy_y_ttm_conviven_y_no_se_pisan(tx):
    """La misma entidad, ratio y periodo con dos ventanas son DOS filas."""
    fy = tx.execute(text("""
        SELECT * FROM derived.ratio
         WHERE canonical_id='ev_sales' AND cik=:c AND valid_to IS NULL"""),
        {"c": AAPL}).mappings().one()
    tx.execute(text("""
        INSERT INTO derived.ratio (
          ratio_key, entity_key, cik, canonical_id, period_end, period_window,
          denominator_basis, currency, value, unit, status, motivo, publicable,
          formula_version, formula, inputs, input_checkpoint_id, run_id)
        SELECT ratio_key || '-ttm', entity_key, cik, canonical_id, period_end,
               'TTM', denominator_basis, currency, value, unit, status, motivo,
               publicable, formula_version, formula, inputs, input_checkpoint_id,
               run_id
          FROM derived.ratio WHERE ratio_key = :rk"""), {"rk": fy["ratio_key"]})
    ventanas = {r[0] for r in tx.execute(text("""
        SELECT period_window FROM derived.ratio
         WHERE canonical_id='ev_sales' AND cik=:c AND period_end=:p
           AND valid_to IS NULL"""), {"c": AAPL, "p": fy["period_end"]})}
    assert ventanas == {"FY", "TTM"}, (
        f"FY y TTM deben coexistir como hechos distintos; hay {ventanas}")


def test_la_identidad_vigente_es_unica_por_ventana(tx):
    """Dos filas VIGENTES con la misma identidad completa no pueden existir."""
    fy = tx.execute(text("""
        SELECT ratio_key FROM derived.ratio
         WHERE canonical_id='ev_sales' AND cik=:c AND valid_to IS NULL"""),
        {"c": AAPL}).scalar_one()
    with pytest.raises(Exception) as e:
        tx.execute(text("""
            INSERT INTO derived.ratio (
              ratio_key, entity_key, cik, canonical_id, period_end, period_window,
              denominator_basis, currency, value, unit, status, motivo, publicable,
              formula_version, formula, inputs, input_checkpoint_id, run_id)
            SELECT ratio_key || '-dup', entity_key, cik, canonical_id, period_end,
                   period_window, denominator_basis, currency, value, unit, status,
                   motivo, publicable, formula_version, formula, inputs,
                   input_checkpoint_id, run_id
              FROM derived.ratio WHERE ratio_key = :rk"""), {"rk": fy})
    assert "ux_ratio_identidad_vigente" in str(e.value)


def test_el_window_declarado_es_fy_y_no_dice_ser_ttm(conn):
    """El motor no sabe hacer TTM. Debe decir FY, no fingir TTM."""
    assert RE.WINDOW == "FY"
    ventanas = {r[0] for r in conn.execute(text(
        "SELECT DISTINCT period_window FROM derived.ratio WHERE canonical_id='ev_sales'"))}
    assert ventanas == {"FY"}, f"ventanas persistidas: {ventanas}"


# ═════════════════════════════════════════════════════ 5 · missing input ════

@pytest.mark.parametrize("cik,concepto", [(GGAL, "ingresos"), (CEPU, "deuda_financiera")])
def test_missing_input_nombra_el_concepto_y_la_cadena(conn, cik, concepto):
    """R6: falta un insumo -> NOT_CALCULABLE nombrando el concepto Y los
    candidatos que se consultaron."""
    r = RE.calcular_ev_sales(conn, cik)
    assert r["status"] == "NOT_CALCULABLE"
    assert concepto in r["motivo"]
    assert "candidatos consultados" in r["motivo"]
    assert r["value"] is None


def test_missing_input_se_persiste_con_provenance_parcial(conn):
    """R7: el hueco se registra. Y la fila dice en que eslabon se corto."""
    f = conn.execute(text("""
        SELECT status, motivo, value, inputs FROM derived.ratio
         WHERE canonical_id='ev_sales' AND cik=:c AND valid_to IS NULL"""),
        {"c": CEPU}).mappings().one()
    assert f["status"] == "NOT_CALCULABLE" and f["value"] is None and f["motivo"]
    roles = {i["rol"] for i in f["inputs"]}
    assert "ingresos" in roles, (
        "CEPU resolvio ingresos antes de cortar en deuda: la fila debe conservarlo")


# ══════════════════════════════════════════════════ 6 · zero denominator ════

def test_zero_denominator_ingresos_cero_no_divide(tx):
    """R3: ingresos = 0 nunca produce una division.

    Se inyecta `Revenue`=0 en AAPL: encabeza la cadena de fallback del concepto
    `ingresos`, asi que gana sobre el tag que AAPL usa realmente.
    """
    assert RE.calcular_ev_sales(tx, AAPL)["status"] == "CALCULADO"
    _clonar_fact(tx, AAPL, "Revenue", Decimal("0"))
    r = RE.calcular_ev_sales(tx, AAPL)
    assert r["status"] == "NOT_CALCULABLE"
    assert "ingresos" in r["motivo"] and "no positivo" in r["motivo"], r["motivo"]
    assert r["value"] is None


def test_zero_denominator_ingresos_negativos_tampoco(tx):
    """R4: un ingreso negativo invierte la lectura del multiplo. Se rechaza."""
    _clonar_fact(tx, AAPL, "Revenue", Decimal("-1000000"))
    r = RE.calcular_ev_sales(tx, AAPL)
    assert r["status"] == "NOT_CALCULABLE" and "no positivo" in r["motivo"]


# ═════════════════════════════════════════ 7 · provenance completeness ══════

def test_provenance_todo_calculado_tiene_la_cadena_entera(conn):
    """R10: ratio -> inputs -> derived.fact -> source_fact_ids -> parsed.facts -> RAW."""
    filas = conn.execute(text("""
        SELECT cik, inputs FROM derived.ratio
         WHERE canonical_id='ev_sales' AND status='CALCULADO' AND valid_to IS NULL""")
        ).mappings().all()
    assert filas
    for f in filas:
        for i in f["inputs"]:
            if i["rol"] in ("derivado", "precio"):
                continue
            ev = i["evidencia"]
            assert ev["estado"] == "COMPLETA", f"{f['cik']}/{i['rol']}: {ev}"
            for campo in ("source_fact_ids", "parsed_cik", "parsed_accession",
                          "source_files", "source_hashes"):
                assert ev.get(campo), f"{f['cik']}/{i['rol']}: falta {campo}"
            assert len(ev["source_hashes"]) >= 1
            assert i["tag_elegido"] in i["cadena_evaluada"], (
                "el tag usado debe pertenecer a la cadena declarada del concepto")


def test_provenance_el_source_hash_existe_en_parsed(conn):
    """El hash citado es el del archivo que la ingesta realmente guardo."""
    malos = conn.execute(text("""
        SELECT count(*)
          FROM derived.ratio r
          CROSS JOIN LATERAL jsonb_array_elements(r.inputs) i
          CROSS JOIN LATERAL jsonb_array_elements_text(i->'evidencia'->'source_fact_ids') s
          LEFT JOIN parsed.facts p ON p.fact_id = s::bigint
         WHERE r.valid_to IS NULL AND r.status='CALCULADO'
           AND (p.fact_id IS NULL
             OR NOT (i->'evidencia'->'source_hashes') ? p.source_hash)""")).scalar_one()
    assert malos == 0, f"{malos} insumos citan un source_hash que no esta en parsed.facts"


# ═══════════════════════════════════════════════════════ 8 · idempotency ════

def test_idempotency_la_clave_no_cambia_entre_calculos(conn):
    """Dos calculos sobre los mismos insumos dan la misma ratio_key."""
    a = RE.ratio_key(RE.calcular_ev_sales(conn, AAPL))
    b = RE.ratio_key(RE.calcular_ev_sales(conn, AAPL))
    assert a == b
    persistida = conn.execute(text("""
        SELECT ratio_key FROM derived.ratio
         WHERE canonical_id='ev_sales' AND cik=:c AND valid_to IS NULL"""),
        {"c": AAPL}).scalar_one()
    assert a == persistida, "recalcular da una clave distinta de la persistida"


def test_idempotency_persistir_dos_veces_no_duplica(tx):
    """R: mismo insumo, misma fila. Se compara por clave, no se hace UPDATE."""
    r = RE.calcular_ev_sales(tx, AAPL)
    run = tx.execute(text("SELECT run_id FROM engine.runs ORDER BY started_at DESC LIMIT 1")
                     ).scalar_one()
    antes = tx.execute(text("SELECT count(*) FROM derived.ratio")).scalar_one()
    assert RE.persistir(tx, r, run, "chk-test") == "SIN_CAMBIO"
    assert RE.persistir(tx, r, run, "chk-test") == "SIN_CAMBIO"
    assert tx.execute(text("SELECT count(*) FROM derived.ratio")).scalar_one() == antes


def test_idempotency_un_insumo_distinto_cierra_la_vigente_y_abre_otra(tx):
    """Cambiar un insumo NO reescribe el valor: cierra el viejo y abre uno nuevo."""
    r = RE.calcular_ev_sales(tx, AAPL)
    run = tx.execute(text("SELECT run_id FROM engine.runs ORDER BY started_at DESC LIMIT 1")
                     ).scalar_one()
    antes = tx.execute(text("SELECT count(*) FROM derived.ratio")).scalar_one()
    r2 = dict(r)
    r2["value"] = float(r["value"]) * 2
    r2["inputs"] = [dict(i, valor=(i.get("valor") or 0)) for i in r["inputs"]]
    r2["inputs"][0] = dict(r2["inputs"][0], valor=1.0)   # ingresos distinto
    assert RE.persistir(tx, r2, run, "chk-test") == "REEMPLAZADO"
    assert tx.execute(text("SELECT count(*) FROM derived.ratio")).scalar_one() == antes + 1
    vig = tx.execute(text("""
        SELECT count(*) FROM derived.ratio
         WHERE canonical_id='ev_sales' AND cik=:c AND valid_to IS NULL"""),
        {"c": AAPL}).scalar_one()
    assert vig == 1, "solo puede quedar una vigente"


# ═══════════════════════════════════════════════════════════ 9 · mutation ═══

def test_mutation_cambiar_un_insumo_cambia_el_resultado(tx):
    """Si duplicar los ingresos no mueve el ratio, la formula no los usa."""
    antes = RE.calcular_ev_sales(tx, AAPL)
    ing = next(i for i in antes["inputs"] if i["rol"] == "ingresos")
    tx.execute(text("UPDATE derived.fact SET value_numeric = value_numeric * 2 "
                    "WHERE fact_key = :fk"), {"fk": ing["fact_key"]})
    despues = RE.calcular_ev_sales(tx, AAPL)
    assert despues["status"] == "CALCULADO"
    assert abs(despues["value"] - antes["value"] / 2) < 1e-6, (
        f"al duplicar los ingresos el ratio deberia partirse a la mitad: "
        f"{antes['value']} -> {despues['value']}")


def test_mutation_quitar_la_guarda_readmite_el_fact_ajeno(tx, monkeypatch):
    """MUTACION CAUSAL — sin la guarda de pertenencia, el hecho de AAPL entra.

    Si esto NO cambiara el resultado, la proteccion la estaria dando otra cosa
    y no la clausula que decimos.
    """
    import ratio_inputs

    _clonar_fact(tx, CEPU, "Borrowings", Decimal("90678000000"), ajeno_de=AAPL)
    con_guarda = RE.calcular_ev_sales(tx, CEPU)
    assert con_guarda["status"] == "NOT_CALCULABLE"

    monkeypatch.setattr(ratio_inputs, "GUARDA_PERTENENCIA", "")
    sin_guarda = RE.calcular_ev_sales(tx, CEPU)
    assert sin_guarda["status"] == "CALCULADO", (
        "sin la guarda el hecho ajeno deberia entrar; si no entra, la proteccion "
        "viene de otra condicion y este test no prueba lo que dice")


# ════════════════════════════════════════════════════════ 10 · persistence ══

def test_persistence_lo_leido_es_lo_calculado(conn):
    """Calcular -> persistir -> leer -> igualdad."""
    for cik in (AAPL, GGAL, CEPU):
        calc = RE.calcular_ev_sales(conn, cik)
        fila = conn.execute(text("""
            SELECT value, status, motivo, currency, period_end::text AS pe,
                   period_window, denominator_basis, formula_version, unit
              FROM derived.ratio
             WHERE canonical_id='ev_sales' AND cik=:c AND valid_to IS NULL"""),
            {"c": cik}).mappings().one()
        assert fila["status"] == calc["status"], cik
        assert fila["pe"] == calc["period_end"], cik
        assert fila["period_window"] == calc["period_window"] == "FY"
        assert fila["denominator_basis"] == "n/a"
        assert fila["formula_version"] == "ev_sales_v1"
        assert fila["unit"] == "veces"
        if calc["status"] == "CALCULADO":
            assert abs(float(fila["value"]) - calc["value"]) < 1e-9, cik
        else:
            assert fila["value"] is None and fila["motivo"]


def test_persistence_los_invariantes_de_la_tabla_se_cumplen(conn):
    """Las CHECK de la migracion, verificadas como datos y no como DDL."""
    n = conn.execute(text("""
        SELECT count(*) FROM derived.ratio
         WHERE (status='CALCULADO' AND (value IS NULL OR jsonb_array_length(inputs)=0))
            OR (status<>'CALCULADO' AND (value IS NOT NULL OR motivo IS NULL))
            OR (publicable AND status<>'CALCULADO')
            OR period_window NOT IN ('FY','TTM','Q','YTD','PIT','FORWARD')""")).scalar_one()
    assert n == 0, f"{n} filas violan el contrato de derived.ratio"


def test_persistence_toda_fila_cita_una_corrida_real(conn):
    """run_id con FK a engine.runs, y ninguna corrida colgada."""
    huerfanas = conn.execute(text("""
        SELECT count(*) FROM derived.ratio r
         WHERE NOT EXISTS (SELECT 1 FROM engine.runs g WHERE g.run_id = r.run_id)""")
        ).scalar_one()
    assert huerfanas == 0
    assert conn.execute(text(
        "SELECT count(*) FROM engine.runs WHERE status='RUNNING'")).scalar_one() == 0
