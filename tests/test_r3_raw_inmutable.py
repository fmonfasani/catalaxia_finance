# -*- coding: utf-8 -*-
"""
R3 — RAW INMUTABLE
==================
Verifica la estrategia "ARCHIVE, NO DELETE":
  1. El RAW existente no desaparece tras una nueva ingesta.
  2. Una nueva version no sobrescribe destructivamente la anterior.
  3. El SHA256 de la version anterior permanece verificable.
  4. El archive conserva provenance suficiente.
  5. Una colision de nombre no destruye datos.
  6. Una reejecucion es segura/idempotente.
  7. No existe DELETE sobre RAW en el camino productivo auditado.
  8. Los paths temporales/test no se confunden con RAW productivo.
  9. Los consumidores posteriores siguen funcionando (path principal).
 10. No se rompe la cadena RAW -> PARSED.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCREENER = REPO / "scripts" / "tickets" / "screener"
SEC_EDGAR = REPO / "scripts" / "tickets" / "sec_edgar" / "scripts"
RAW_REAL = REPO / "data" / "raw"

sys.path.insert(0, str(SCREENER))

import _raw_inmutable as ri  # noqa: E402
import run_update  # noqa: E402


def _snapshot_raw_real():
    if not RAW_REAL.exists():
        return {}
    return {str(p.relative_to(REPO)): p.read_bytes()
            for p in sorted(RAW_REAL.rglob("*")) if p.is_file()}


SNAP_RAW_REAL = _snapshot_raw_real()


class _Log:
    def __init__(self):
        self.lines = []

    def log(self, msg):
        self.lines.append(msg)


def _setup_raw(tmp_path, cik="1", viejo=("v1", "v1s")):
    """Crea data/raw con companyfacts y submissions viejas para un CIK."""
    raw = tmp_path / "data" / "raw"
    (raw / "companyfacts").mkdir(parents=True, exist_ok=True)
    (raw / "submissions").mkdir(parents=True, exist_ok=True)
    f_facts = raw / "companyfacts" / f"CIK{cik}.json"
    f_subs = raw / "submissions" / f"CIK{cik}.json"
    f_facts.write_text(json.dumps({"v": viejo[0], "cik": cik}), encoding="utf-8")
    f_subs.write_text(json.dumps({"v": viejo[1], "cik": cik}), encoding="utf-8")
    return raw, f_facts, f_subs


def _con_empresas(cik="1"):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE empresas (cik TEXT PRIMARY KEY, ticker_ppal TEXT, nombre TEXT)")
    con.execute("INSERT INTO empresas VALUES (?,?,?)", (cik, "TICK", f"Empresa {cik}"))
    return con


def _descargar_success(root):
    def descargar_empresa(con, ticker, cik, nombre):
        for tipo in ("companyfacts", "submissions"):
            p = root / "data" / "raw" / tipo / f"CIK{cik}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"v": "new", "cik": cik, "tipo": tipo}),
                         encoding="utf-8")
        return ("us-gaap", 10, 100)
    return descargar_empresa


def _fake_construir_base(monkeypatch, root, behavior="success"):
    fake = types.ModuleType("construir_base")

    def descargar_empresa(con, ticker, cik, nombre):
        if behavior == "success":
            return _descargar_success(root)(con, ticker, cik, nombre)
        return None

    fake.descargar_empresa = descargar_empresa
    monkeypatch.setitem(sys.modules, "construir_base", fake)


# ── 1 y 2. El RAW previo no desaparece; la nueva version no lo pisa ──

def test_raw_no_desaparece_tras_nueva_ingesta(tmp_path, monkeypatch):
    raw, f_facts, _ = _setup_raw(tmp_path)
    viejo_bytes = f_facts.read_bytes()
    _fake_construir_base(monkeypatch, tmp_path, "success")
    monkeypatch.setattr(run_update, "ROOT", tmp_path)
    ok = run_update.re_download_edgar(_con_empresas(), ["1"], _Log())
    assert ok == 1
    stale = sorted((raw / "_stale").rglob("CIK1.json"))
    assert len(stale) == 2, "companyfacts y submissions archivadas"
    conservado = {p.read_bytes() for p in stale}
    assert viejo_bytes in conservado, "el RAW previo sigue existiendo (archivado)"
    # version nueva en el path principal, NO pisando la anterior
    nuevo = json.loads(f_facts.read_text(encoding="utf-8"))
    assert nuevo["v"] == "new"
    assert f_facts.read_bytes() != viejo_bytes


# ── 3. SHA256 de la version anterior verificable ──

def test_sha256_version_anterior_verificable(tmp_path):
    p = tmp_path / "raw" / "companyfacts" / "CIK5.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps({"v": "old"})
    p.write_text(contenido, encoding="utf-8")
    prov = ri.archivar(p, razon="re_download_edgar")
    assert prov is not None
    archivo = Path(prov["ruta_archivado"])
    assert archivo.exists()
    assert ri.sha256(archivo) == prov["sha256"]
    assert prov["sha256"] == __import__("hashlib").sha256(contenido.encode()).hexdigest()


# ── 4. El archive conserva provenance ──

def test_archive_conserva_provenance(tmp_path):
    p = tmp_path / "raw" / "submissions" / "CIK7.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"v": "old"}), encoding="utf-8")
    prov = ri.archivar(p, razon="re_download_edgar")
    meta_p = Path(prov["ruta_archivado"]).with_name(
        Path(prov["ruta_archivado"]).name + ".meta.json")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    for k in ("razon", "nombre_original", "tipo", "origen_rel", "raw_dir",
              "sha256", "ts"):
        assert k in meta and meta[k], f"falta provenance {k}"
    assert meta["razon"] == "re_download_edgar"
    assert meta["nombre_original"] == p.name
    assert meta["tipo"] == "submissions"
    assert meta["origen_rel"] == f"submissions/{p.name}"
    assert meta["sha256"] == prov["sha256"]
    # registro en ingesta_log con razon + fingerprint
    con = sqlite3.connect(":memory:")
    rid = ri.registrar(con, "7", meta["tipo"], prov["sha256"],
                       razon="re_download_edgar", bytes_=prov["bytes"])
    assert rid is not None
    fila = con.execute(
        "SELECT entidad, recurso, hash, motivo FROM ingesta_log").fetchone()
    assert fila[0] == "7" and fila[1] == "submissions"
    assert fila[2] == prov["sha256"]
    assert fila[3].startswith("R3:archivado:re_download_edgar")


# ── 5. Colision de nombre: nunca destruye datos ──

def test_colision_nombre_no_destruye_datos(tmp_path):
    raw = tmp_path / "raw" / "submissions"
    raw.mkdir(parents=True, exist_ok=True)
    p = raw / "CIK9.json"
    p.write_text("A", encoding="utf-8")
    prov1 = ri.archivar(p, razon="re_download_edgar")
    p.write_text("B", encoding="utf-8")
    prov2 = ri.archivar(p, razon="re_download_edgar")  # misma ts => colision
    assert prov1["ruta_archivado"] != prov2["ruta_archivado"]
    archivados = list((tmp_path / "raw" / "_stale").rglob("CIK9*.json"))
    contenidos = {a.read_text() for a in archivados}
    assert {"A", "B"} <= contenidos, "ambas versiones preservadas, nada pisado"
    # sin .meta.json contados como datos
    assert len(archivados) >= 2


# ── 6. Reejecucion segura / idempotente ──

def test_reejecucion_idempotente(tmp_path):
    p = tmp_path / "raw" / "companyfacts" / "CIK3.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps({"v": "old"})
    p.write_text(contenido, encoding="utf-8")
    prov = ri.archivar(p, razon="re_download_edgar")
    assert prov is not None
    # segunda pasada: el archivo ya no esta en el path principal => no-op
    assert ri.archivar(p, razon="re_download_edgar") is None
    # restaurar no sobrescribe una version nueva
    p.write_text("nuevo", encoding="utf-8")
    assert ri.restaurar(prov) is None
    # si el path principal quedo vacio, restaura el previo
    p.unlink()
    rest = ri.restaurar(prov)
    assert rest == Path(prov["origen_abs"])
    assert p.read_text(encoding="utf-8") == contenido
    # restaurar de nuevo: no-op (ya existe)
    assert ri.restaurar(prov) is None


# ── 7. No existe DELETE sobre RAW en el camino productivo ──

RX_DESTRUCTIVO = re.compile(
    r"\.unlink\(|os\.remove\(|os\.unlink\(|Path\.unlink\(|shutil\.rmtree\(|\.truncate\(")


def test_no_delete_sobre_raw_camino_productivo():
    fuentes = sorted(SCREENER.glob("*.py")) + sorted(SEC_EDGAR.glob("*.py"))
    for py in fuentes:
        lineas = py.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lineas):
            if not RX_DESTRUCTIVO.search(ln):
                continue
            contexto = " ".join(lineas[max(0, i - 3):i + 1])
            assert ("data/raw" not in contexto and "raw_dir" not in contexto
                    and "raw/" not in contexto), \
                f"{py.name}:{i + 1}: operacion destructiva sobre RAW: {ln}"


def test_run_update_no_unlinka_raw():
    src = (SCREENER / "run_update.py").read_text(encoding="utf-8")
    assert "f.unlink()" not in src
    unlinks = [l.strip() for l in src.splitlines() if ".unlink(" in l]
    assert unlinks, "el archivo conserva al menos un unlink de temporal"
    assert all("tmp" in l for l in unlinks), unlinks


# ── 8. Temporales/test no se confunden con RAW productivo ──

def test_tmp_y_test_no_tocan_raw_productivo(tmp_path, monkeypatch):
    raw, f_facts, _ = _setup_raw(tmp_path)
    viejo = f_facts.read_bytes()
    _fake_construir_base(monkeypatch, tmp_path, "success")
    monkeypatch.setattr(run_update, "ROOT", tmp_path)
    assert run_update.re_download_edgar(_con_empresas(), ["1"], _Log()) == 1
    # todo el archive quedo bajo el data/raw del tmp, jamas en el real
    assert (tmp_path / "data" / "raw" / "_stale").exists()
    assert not (RAW_REAL / "_stale").exists()
    assert viejo not in (RAW_REAL / "companyfacts" / "CIK1.json").read_bytes() \
        if (RAW_REAL / "companyfacts" / "CIK1.json").exists() else True
    # el data/raw real quedo exactamente igual
    assert _snapshot_raw_real() == SNAP_RAW_REAL


# ── 9 y 10. Consumidores y cadena RAW -> PARSED siguen intactas ──

def test_consumidores_y_cadena_raw_parsed(tmp_path, monkeypatch):
    raw, f_facts, f_subs = _setup_raw(tmp_path)
    # modulo REAL de construir_base: get_json_cache es el consumidor de RAW del
    # camino productivo; se patchea SOLO descargar_empresa para no usar red.
    sys.path.insert(0, str(SEC_EDGAR))
    import construir_base as cb
    monkeypatch.setattr(cb, "descargar_empresa", _descargar_success(tmp_path))
    monkeypatch.setattr(run_update, "ROOT", tmp_path)
    assert run_update.re_download_edgar(_con_empresas(), ["1"], _Log()) == 1
    # los consumidores posteriores (parsers s03/xbrlparse/construir_base)
    # leen el path principal estandar y lo parsean como antes
    nuevo = json.loads(f_facts.read_text(encoding="utf-8"))
    assert nuevo == {"v": "new", "cik": "1", "tipo": "companyfacts"}
    json.loads(f_subs.read_text(encoding="utf-8"))   # subs parseable
    data, era_cache = cb.get_json_cache("https://x/CIK1.json", f_facts, forzar=False)
    assert era_cache is True
    assert data == nuevo
    # el previo sigue legible desde el archive (evidencia intacta)
    stale = sorted((raw / "_stale").rglob("CIK1.json"))
    assert len(stale) == 2
    assert {json.loads(p.read_text(encoding="utf-8"))["v"] for p in stale} == {"v1", "v1s"}


# ── INV4: falla de re-descarga => RAW previo disponible y recuperable ──

def test_falla_red_restaura_previo(tmp_path, monkeypatch):
    raw, f_facts, f_subs = _setup_raw(tmp_path)
    viejo_facts = f_facts.read_bytes()
    viejo_subs = f_subs.read_bytes()
    _fake_construir_base(monkeypatch, tmp_path, "failure")
    monkeypatch.setattr(run_update, "ROOT", tmp_path)
    log = _Log()
    con = _con_empresas()
    ok = run_update.re_download_edgar(con, ["1"], log)
    assert ok == 0
    # el path principal queda con el RAW previo (restaurado, nunca vacio)
    assert f_facts.read_bytes() == viejo_facts
    assert f_subs.read_bytes() == viejo_subs
    # el archive se conserva como evidencia
    assert len(list((raw / "_stale").rglob("CIK1.json"))) == 2
    assert any("RESTORE R3" in l for l in log.lines)
    # la restauracion queda registrada
    motivos = [r[0] for r in con.execute(
        "SELECT motivo FROM ingesta_log WHERE motivo LIKE 'R3:%'")]
    assert any("restaurado" in m for m in motivos)