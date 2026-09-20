"""Tests F4 — generalizacion SEC multiemisor (YPF + KO).

Estaticos: sin DB. Vivos: requieren F4_YPF_RUN / F4_KO_RUN / F4_KO_RUN2
(run_ids de corridas E2E DEV reales); si faltan => skip (no inventan).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "engine"))

from engine import db as edb  # noqa: E402
from engine.config import load_settings  # noqa: E402
import issuers  # noqa: E402

YPF = "0000904851"
KO = "0000021344"
KO_KEY = "E01M1W68XDCYY7AS1STHXKH084Z"


def _eng():
    return edb.get_engine(load_settings())


def _run_id(name):
    rid = os.environ.get(name)
    if not rid:
        pytest.skip("sin %s (corrida DEV no ejecutada)" % name)
    return rid


# ---------- O: sin forks por emisor ----------

def test_O_sin_scripts_por_emisor():
    eng_dir = REPO / "scripts" / "engine"
    for bad in ("s01_identity_ko.py", "s02_fetch_ko.py", "s03_parse_ko.py",
                "s04_normalize_ko.py", "s02_fetch_ko.py"):
        assert not (eng_dir / bad).exists(), "fork prohibido: %s" % bad


def test_O_registro_sin_logica():
    src = (REPO / "scripts" / "engine" / "issuers.py").read_text(encoding="utf-8")
    imports = [ln.strip() for ln in src.splitlines()
               if ln.strip().startswith(("import ", "from "))]
    for tok in ("requests", "xbrl", "lxml", "sqlalchemy", "subprocess",
                "BeautifulSoup"):
        assert not any(tok in ln for ln in imports), \
            "issuers.py no debe importar logica: %s" % tok
    ypf = issuers.get_by_cik(YPF)
    ko = issuers.get_by_cik(KO)
    assert ypf["issuer_key"] == "YPF" and ypf["golden"]
    assert ypf["forms"] == ["20-F", "20-F/A"] and ypf["min_xbrl"] == 9
    assert ko["issuer_key"] == "KO" and ko["golden"]
    assert ko["legal_name"] == "COCA COLA CO" and ko["jurisdiction"] == "US"
    assert ko["forms"] == ["10-K", "10-K/A"]
    assert issuers.get_by_key("ko")["cik"] == KO
    assert issuers.get_by_cik("9999999999") is None


def _help_ok(script, *flags):
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "engine" / script),
                        "--help"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    for f in flags:
        assert f in r.stdout, "%s sin %s" % (script, f)


def test_cli_aceptan_cik():
    _help_ok("s01_identity.py", "--cik")
    _help_ok("s02_fetch_ypf.py", "--cik", "--forms")
    _help_ok("s03_parse_ypf.py", "--cik", "--min-xbrl")


def test_e2e_passthrough_por_codigo():
    src = (REPO / "scripts" / "engine" / "e2e_orchestrator.py").read_text(
        encoding="utf-8")
    assert '"--cik"' in src and "extra_por_stage" in src
    src01 = (REPO / "scripts" / "engine" / "s01_identity.py").read_text(
        encoding="utf-8")
    assert "resolve_por_cik" in src01 and "YPF_CIK" in src01


# ---------- vivos: requieren corridas DEV ----------

def _gates(eng, run_id):
    with eng.connect() as c:
        return {r[0]: (r[1], r[2]) for r in c.execute(text(
            "SELECT stage_id, state, gate_status FROM engine.stage_runs "
            "WHERE run_id=:r AND id IN (SELECT max(id) FROM engine.stage_runs "
            "WHERE run_id=:r GROUP BY stage_id)"), {"r": run_id})}


def test_A_ypf_continua_pass():
    g = _gates(_eng(), _run_id("F4_YPF_RUN"))
    for s in ("S00_bootstrap", "S01_identity", "S02_fetch", "S03_parse",
              "S04_normalize"):
        assert g[s][1] == "PASS", (s, g.get(s))


def _ko_run():
    return _run_id("F4_KO_RUN")


def test_BCDE_ko_s01_s04_pass():
    g = _gates(_eng(), _ko_run())
    for s in ("S01_identity", "S02_fetch", "S03_parse", "S04_normalize"):
        assert g[s][1] == "PASS", (s, g.get(s))


def test_F_cik_correcto():
    # Los facts llevan el run_id del ultimo escritor (convergencia ON CONFLICT);
    # la verdad por emisor se verifica por CIK.
    with _eng().connect() as c:
        n = c.execute(text(
            "SELECT count(*) FROM derived.fact WHERE cik=:k"), {"k": KO}).scalar()
    assert n > 0


def test_G_entity_key_correcto():
    with _eng().connect() as c:
        keys = {r[0] for r in c.execute(text(
            "SELECT DISTINCT entity_key FROM derived.fact WHERE cik=:k"),
            {"k": KO})}
    assert keys == {KO_KEY}


def test_H_provenance_completa():
    with _eng().connect() as c:
        row = c.execute(text(
            "SELECT count(*) AS n, "
            "count(source_fact_ids) AS sf, "
            "count(input_checkpoint_id) AS ic "
            "FROM derived.fact WHERE cik=:k"),
            {"k": KO}).mappings().first()
    assert row["n"] > 0 and row["sf"] == row["n"] and row["ic"] == row["n"]


def test_I_cero_orphan_entity_key():
    with _eng().connect() as c:
        orph = c.execute(text(
            "SELECT count(DISTINCT d.entity_key) FROM derived.fact d "
            "WHERE d.cik=:k AND NOT EXISTS (SELECT 1 FROM "
            "identity_v1.identifier i WHERE i.entity_key=d.entity_key)"),
            {"k": KO}).scalar()
    assert orph == 0


def test_J2_convergencia_ultimo_escritor():
    # Re-runs convergen (ON CONFLICT): solo el ultimo run KO tiene facts,
    # sin duplicados entre todos. Orden cronologico via F4_KO_RUNS.
    runs = [r.strip() for r in os.environ.get("F4_KO_RUNS", "").split(",")
            if r.strip()] or [_ko_run(), _run_id("F4_KO_RUN2")]
    assert len(runs) >= 2
    with _eng().connect() as c:
        counts = [c.execute(text("SELECT count(*) FROM derived.fact "
                                 "WHERE run_id=:r"), {"r": r}).scalar()
                  for r in runs]
        dups = c.execute(text(
            "SELECT count(*) - count(DISTINCT fact_key) FROM derived.fact "
            "WHERE run_id IN (%s)" % ",".join(":r%d" % i for i in range(len(runs)))),
            {"r%d" % i: r for i, r in enumerate(runs)}).scalar()
    assert all(n == 0 for n in counts[:-1]), counts
    assert counts[-1] > 0
    assert dups == 0


def test_J_idempotencia_ko():
    r1, r2 = _ko_run(), _run_id("F4_KO_RUN2")
    with _eng().connect() as c:
        h = {}
        for r in (r1, r2):
            rep = c.execute(text(
                "SELECT report FROM engine.stage_runs "
                "WHERE run_id=:x AND stage_id='S04_normalize' "
                "ORDER BY id DESC LIMIT 1"), {"x": r}).scalar()
            import json as _j
            h[r] = _j.loads(rep)["integrity"]["hash_out"] if isinstance(
                rep, str) else rep["integrity"]["hash_out"]
        tot = c.execute(text(
            "SELECT count(*), count(DISTINCT fact_key) FROM derived.fact "
            "WHERE run_id IN (:a, :b)"), {"a": r1, "b": r2}).first()
    assert h[r1] == h[r2]
    assert tot[0] == tot[1]  # converge, sin duplicados


def test_K_sin_contaminacion_cruzada():
    with _eng().connect() as c:
        mix = c.execute(text(
            "SELECT count(*) FROM derived.fact WHERE cik=:k AND "
            "entity_key != :e"),
            {"k": KO, "e": KO_KEY}).scalar()
        ypf_ko = c.execute(text(
            "SELECT count(*) FROM derived.fact WHERE cik=:y AND "
            "entity_key=:e"), {"y": YPF, "e": KO_KEY}).scalar()
        raw_ko = c.execute(text(
            "SELECT count(*) FROM fetch_raw.download_log "
            "WHERE raw_path LIKE '%%CIK%s%%'" % KO)).scalar()
    assert mix == 0 and ypf_ko == 0
    assert raw_ko > 0


def _stage_exit(script, *args):
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "engine" / script), *args],
        capture_output=True, text=True, timeout=300)


def test_L_config_invalida_bloquea():
    r = _stage_exit("s01_identity.py", "--cik", "abc")
    assert r.returncode == 1, r.stderr[-500:] + r.stdout[-500:]


def test_M_cik_inexistente_bloquea():
    r = _stage_exit("s01_identity.py", "--cik", "9999999999")
    assert r.returncode == 1, r.stderr[-500:] + r.stdout[-500:]


def test_N_filing_inexistente_bloquea():
    # CIK inexistente: s02 no resuelve entidad/filing y bloquea (exit != 0)
    # sin tocar parsed (un run s03 con 0 filings reemplazaria parsed del
    # emisor y huerfaniza provenance: hallazgo F4 documentado, no repetido).
    r = _stage_exit("s02_fetch_ypf.py", "--cik", "9999999999")
    assert r.returncode != 0, "s02 debe bloquear sin filings"


def test_C11_certifica_ko():
    with _eng().connect() as c:
        row = c.execute(text(
            "SELECT veredicto FROM engine.certifications WHERE run_id=:r "
            "ORDER BY generado_at DESC LIMIT 1"), {"r": _ko_run()}).first()
    assert row and row[0] == "CERTIFICADA"
