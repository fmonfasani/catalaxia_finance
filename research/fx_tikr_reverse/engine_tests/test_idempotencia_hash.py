"""Ejes 1-2: idempotencia + hash. Sin red."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from common import assert_in_sandbox, sha256_bytes, write_raw_noreplace  # noqa: E402


def test_write_raw_idempotente(tmp_path):
    target = Path(str(ROOT / "raw") + "_test_idem") / "a.json"
    # tmp_path está fuera del sandbox: sólo probamos la primitiva con path sandbox
    probe = ROOT / "raw" / "instruments" / "_test_idem_probe.json"
    try:
        r1 = write_raw_noreplace(probe, b'{"a":1}')
        r2 = write_raw_noreplace(probe, b'{"a":1}')
        assert r1["action"] == "CREATED"
        assert r2["action"] == "EXISTS_IDENTICAL"
        assert r1["sha256"] == r2["sha256"]
        r3 = write_raw_noreplace(probe, b'{"a":2}')
        assert r3["action"] == "VERSIONED"  # jamás sobrescribe
        assert Path(r3["path"]) != probe
    finally:
        probe.unlink(missing_ok=True)
        for p in probe.parent.glob("_test_idem_probe*"):
            p.unlink(missing_ok=True)


def test_raw_a3500_hash_coherente():
    d = ROOT / "raw" / "bcra" / "a3500"
    files = sorted(d.glob("*.json"))
    assert len(files) > 100, "se esperan >100 RAW diarios (ventanas POC+EXT)"
    for p in files[:5]:
        env = json.loads(p.read_text(encoding="utf-8"))
        meta = env["meta"]
        for k in ("source_url", "retrieved_at", "source_date", "sha256", "http_status"):
            assert meta.get(k) not in (None, ""), (p.name, k)
        canon = json.dumps(env["payload"], sort_keys=True, ensure_ascii=False).encode("utf-8")
        assert sha256_bytes(canon) == meta["sha256"], p.name


def test_sandbox_rechaza_fuera():
    try:
        assert_in_sandbox(ROOT.parent / "data" / "screener.db")
    except SystemExit as e:
        assert "REFUSADO" in str(e)
    else:
        raise AssertionError("debió rechazar path de producción")
