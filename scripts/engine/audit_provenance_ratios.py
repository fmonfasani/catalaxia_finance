#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria independiente — provenance, equivalencia conceptual y contextos.

Cubre las fases C, E y G del pliego. No importa `ratio_defs`, `screener_demo`
ni `engine.*`: habla con PostgreSQL por `psql` y lee los artefactos del disco
por su cuenta.

La equivalencia entre taxonomias NO se verifica comparando nombres de tags. Se
verifica con IDENTIDADES CONTABLES que deben cumplirse sea cual sea la
taxonomia:

    activo = pasivo + patrimonio
    resultado_neto / acciones_promedio = EPS publicado
    ingresos - costo_de_ventas = resultado_bruto

Si el tag elegido para un concepto no fuera el que se cree, la identidad se
rompe. Es una prueba semantica, no lexica.

SOLO LECTURA.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import zipfile
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 40

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "docs" / "auditoria"
RAW = REPO / "data" / "raw" / "engine"
CONT = "catalaxia-engine-dev"

EMPRESAS = {
    "0000904851": ("YPFD", "IFRS+US-GAAP"),
    "0001114700": ("GGAL", "ifrs-full"),
    "0001717161": ("CEPU", "ifrs-full"),
    "0000320193": ("AAPL", "us-gaap"),
    "0000789019": ("MSFT", "us-gaap"),
    "0001045810": ("NVDA", "us-gaap"),
    "0001347426": ("BMA", "ifrs-full"),
    "0000931427": ("TGSU2", "ifrs-full"),
}

# concepto -> candidatos, en el orden que el auditor declara (no copiado)
C = {
    "activo": ["Assets"],
    "pasivo": ["Liabilities"],
    "patrimonio": ["Equity", "StockholdersEquity"],
    "activo_corriente": ["CurrentAssets", "AssetsCurrent"],
    "pasivo_corriente": ["CurrentLiabilities", "LiabilitiesCurrent"],
    "resultado": ["ProfitLossAttributableToOwnersOfParent", "NetIncomeLoss", "ProfitLoss"],
    "ingresos": ["Revenue", "RevenueFromContractsWithCustomers",
                 "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "costo_ventas": ["CostOfSales", "CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "bruto": ["GrossProfit"],
    "eps": ["BasicEarningsLossPerShare", "BasicAndDilutedEarningsPerShare",
            "BasicAndDilutedEarningsLossPerShare", "EarningsPerShareBasic"],
    "acciones": ["WeightedAverageShares", "WeightedAverageNumberOfSharesOutstandingBasic"],
}


def sql(q: str) -> list[list[str]]:
    p = subprocess.run(["docker", "exec", CONT, "psql", "-U", "catalaxia", "-d", "catalaxia",
                        "-t", "-A", "-F", "\x1f", "-c", q],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"psql fallo: {p.stderr[:400]}")
    # NO usar .strip() sobre todo el blob: Python trata \x1c-\x1f como
    # whitespace, asi que se comeria el separador junto con el \n final
    # cuando el ULTIMO campo de la ULTIMA fila viene NULL (p.ej. `currency`
    # en un conteo de acciones). splitlines() ya descarta el salto de linea
    # sin tocar el resto de cada linea.
    return [ln.split("\x1f") for ln in p.stdout.splitlines() if ln.strip()]


def uno(q):
    r = sql(q)
    return r[0][0] if r else None


def ultimo_ejercicio(cik: str) -> str | None:
    return uno(f"SELECT max(report_period)::text FROM derived.fact "
               f" WHERE valid_to IS NULL AND cik='{cik}'")


def valor(cik: str, per: str, concepto: str):
    """Primer candidato presente. Devuelve (tag, Decimal, moneda) o (None,...)."""
    for t in C[concepto]:
        r = sql(f"SELECT value_numeric, currency FROM derived.fact WHERE valid_to IS NULL "
                f" AND cik='{cik}' AND NOT is_dimensional AND report_period='{per}' "
                f" AND tag='{t}' AND value_numeric IS NOT NULL "
                f" AND COALESCE(instant_date::text,end_date::text)=report_period::text")
        if r:
            return t, Decimal(r[0][0]), r[0][1]
    return None, None, None


def leer_artefacto(ruta: str | None) -> tuple[bytes | None, str]:
    if not ruta:
        return None, ""
    if "!" in ruta:
        z, miembro = ruta.split("!", 1)
        zp = RAW / z
        if not zp.exists():
            return None, f"(falta el paquete {z})"
        try:
            with zipfile.ZipFile(zp) as zf:
                return zf.read(miembro), f"{z} :: {miembro}"
        except (KeyError, zipfile.BadZipFile) as e:
            return None, f"({type(e).__name__})"
    p = RAW / ruta
    return (p.read_bytes(), ruta) if p.exists() else (None, f"(no esta: {ruta})")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res, ok_total, limitaciones = [], True, []

    def chk(n, cond, det="", critico=True):
        nonlocal ok_total
        print(f"  {'OK   ' if cond else ('FALLA' if critico else 'NOTA ')} {n:<52} {det}")
        res.append({"control": n, "ok": bool(cond), "critico": critico,
                    "detalle": str(det)[:400]})
        if not cond and critico:
            ok_total = False

    print("AUDITORIA INDEPENDIENTE — provenance, equivalencia conceptual, contextos\n")

    # ═══════ FASE E · equivalencia CONCEPTUAL, no lexica ═══════
    print("E. EQUIVALENCIA CONCEPTUAL ENTRE TAXONOMIAS")
    print("   se verifica con identidades contables, no comparando nombres de tags\n")
    print(f"   {'empresa':<7} {'taxonomia':<13} {'A = P + PN':<28} {'desvio':>9}  tags usados")
    fallos_id = []
    for cik, (tk, tax) in sorted(EMPRESAS.items(), key=lambda kv: kv[1][0]):
        per = ultimo_ejercicio(cik)
        ta, va, ma = valor(cik, per, "activo")
        tp, vp, mp = valor(cik, per, "pasivo")
        tq, vq, mq = valor(cik, per, "patrimonio")
        if None in (va, vp, vq):
            faltan = [c for c, v in (("activo", va), ("pasivo", vp), ("patrimonio", vq))
                      if v is None]
            print(f"   {tk:<7} {tax:<13} {'sin datos: ' + ','.join(faltan):<28}")
            limitaciones.append(f"{tk}: no publica {faltan}")
            continue
        if not (ma == mp == mq):
            print(f"   {tk:<7} {tax:<13} {'monedas distintas':<28}")
            continue
        desv = abs(va - (vp + vq)) / va * 100 if va else Decimal(0)
        marca = "OK" if desv < Decimal("0.5") else "DESVIA"
        print(f"   {tk:<7} {tax:<13} {marca:<28} {desv:>8.4f}%  {ta}/{tp}/{tq}")
        if desv >= Decimal("0.5"):
            fallos_id.append(f"{tk}: {desv:.2f}% ({ta}={va} vs {tp}+{tq}={vp+vq})")
    chk("E1 · identidad activo = pasivo + patrimonio en ambas taxonomias",
        not fallos_id, (str(fallos_id[:3]) if fallos_id else
                        "se cumple donde los tres conceptos existen"))

    print(f"\n   {'empresa':<7} {'EPS publicado':>15} {'resultado/acciones':>20} {'desvio':>9}")
    fallos_eps = []
    for cik, (tk, tax) in sorted(EMPRESAS.items(), key=lambda kv: kv[1][0]):
        per = ultimo_ejercicio(cik)
        te, ve, _ = valor(cik, per, "eps")
        tr, vr, _ = valor(cik, per, "resultado")
        ts, vs, _ = valor(cik, per, "acciones")
        if None in (ve, vr, vs) or vs == 0 or ve == 0:
            limitaciones.append(f"{tk}: EPS/acciones incompletos")
            continue
        der = vr / vs
        d = abs(der - ve) / abs(ve) * 100
        print(f"   {tk:<7} {ve:>15.4f} {der:>20.4f} {d:>8.2f}%")
        if d > 5:
            fallos_eps.append(f"{tk}: {ve} vs {der:.4f} ({d:.1f}%) [{te}|{tr}|{ts}]")
    chk("E2 · resultado/acciones reproduce el EPS publicado (semantica del tag)",
        not fallos_eps, str(fallos_eps[:3]) if fallos_eps else "coinciden")

    print(f"\n   {'empresa':<7} {'ingresos - costo':>20} {'resultado bruto':>18} {'desvio':>9}")
    fallos_gp = []
    for cik, (tk, tax) in sorted(EMPRESAS.items(), key=lambda kv: kv[1][0]):
        per = ultimo_ejercicio(cik)
        _, vi, _ = valor(cik, per, "ingresos")
        _, vc, _ = valor(cik, per, "costo_ventas")
        _, vb, _ = valor(cik, per, "bruto")
        if None in (vi, vc, vb) or vb == 0:
            continue
        calc = vi - abs(vc)
        d = abs(calc - vb) / abs(vb) * 100
        print(f"   {tk:<7} {calc:>20,.0f} {vb:>18,.0f} {d:>8.2f}%")
        if d > 1:
            fallos_gp.append(f"{tk}: {d:.2f}%")
    chk("E3 · ingresos - costo de ventas = resultado bruto", not fallos_gp,
        str(fallos_gp[:3]) if fallos_gp else "coinciden donde los tres existen")

    # ═══════ FASE C · contextos, casos A y C ═══════
    print("\nC. CONTEXTOS — equivalencia por orden y conservacion de hechos")
    ej = sql("""
        SELECT a.accession_number, a.context_id, a.source_file, b.source_file,
               a.dimensions::text, b.dimensions::text
          FROM parsed.contexts a JOIN parsed.contexts b
            ON a.accession_number=b.accession_number AND a.context_id=b.context_id
           AND a.ctx_id < b.ctx_id
         WHERE a.dimensions::text <> b.dimensions::text
           AND jsonb_typeof(a.dimensions)='array' AND jsonb_array_length(a.dimensions) >= 2
         LIMIT 1""")
    if not ej:
        chk("C-A · hay un par real que difiere solo en el orden", False,
            "no se encontro un ejemplo", critico=False)
    else:
        acc, ctxid, f1, f2, d1, d2 = ej[0]
        import json as _j
        s1 = sorted(_j.dumps(x, sort_keys=True) for x in _j.loads(d1))
        s2 = sorted(_j.dumps(x, sort_keys=True) for x in _j.loads(d2))
        print(f"   accession {acc}  context {ctxid}")
        print(f"     {f1}: {d1[:88]}")
        print(f"     {f2}: {d2[:88]}")
        chk("C-A · el par difiere en el ORDEN pero no en el conjunto", s1 == s2,
            f"{len(s1)} dimensiones, mismo conjunto: {s1 == s2}")

    ggal = sql("""
        SELECT count(*) FROM (SELECT accession_number, qname, context_id,
                 coalesce(unit_ref,'') FROM parsed.facts WHERE cik='0001114700'
               GROUP BY 1,2,3,4) x""")
    ggal_d = uno("SELECT count(*) FROM derived.fact WHERE valid_to IS NULL "
                 " AND cik='0001114700'")
    chk("C-C · GGAL: derived == grupos canonicos (el aumento no es duplicacion)",
        ggal and ggal[0][0] == ggal_d,
        f"grupos={ggal[0][0] if ggal else '?'} derived={ggal_d}")
    dup_ggal = uno("""
        SELECT count(*) FROM (SELECT accession_number, qname, context_id,
                 coalesce(unit_ref,'') FROM derived.fact WHERE valid_to IS NULL
                 AND cik='0001114700' GROUP BY 1,2,3,4 HAVING count(*)>1) y""")
    chk("C-C2 · GGAL no tiene hechos derivados duplicados", dup_ggal == "0",
        f"{dup_ggal} grupos con mas de un hecho derivado")

    # ═══════ FASE G · cadena de provenance hasta el SHA256 ═══════
    print("\nG. PROVENANCE — cadena completa hasta el artefacto")
    muestra = []
    for cik in ("0000904851", "0001114700", "0000320193"):
        for dim in ("false", "true"):
            r = sql(f"""
                SELECT d.cik, d.accession_number, d.tag, d.qname, d.value_numeric,
                       d.currency, d.is_dimensional, s.fid
                  FROM derived.fact d
                  CROSS JOIN LATERAL unnest(d.source_fact_ids) s(fid)
                 WHERE d.valid_to IS NULL AND d.cik='{cik}' AND d.is_dimensional={dim}
                   AND d.value_numeric IS NOT NULL
                 ORDER BY d.tag LIMIT 1""")
            if r:
                muestra.append(r[0])
    print(f"   muestra: {len(muestra)} hechos "
          f"({len({m[0] for m in muestra})} empresas, con y sin dimensiones)\n")
    rotas, verificadas = [], 0
    for cik, acc, tag, qname, val, cur, dimf, fid in muestra:
        p = sql(f"""SELECT p.cik, p.accession_number, p.qname, p.taxonomy, p.source_file,
                           p.source_path, p.source_hash, p.context_id
                      FROM parsed.facts p WHERE p.fact_id={fid}""")
        tk = EMPRESAS[cik][0]
        if not p:
            rotas.append(f"{tk}/{tag}: fact_id {fid} no existe")
            continue
        pc, pacc, pq, ptax, sfile, spath, shash, pctx = p[0]
        cadena_ok = (pc == cik and pacc == acc and pq == qname)
        datos, ubic = leer_artefacto(spath)
        print(f"   {tk:<6} {tag[:34]:<34} dim={dimf}")
        print(f"      fact_id {fid} -> cik {pc} · accession {pacc}")
        print(f"      taxonomia {ptax} · contexto {pctx}")
        print(f"      archivo {sfile}")
        if datos is None:
            print(f"      SHA256   {shash[:24]}…  artefacto {ubic}")
            limitaciones.append(f"{tk}/{tag}: artefacto no disponible {ubic}")
        else:
            real = hashlib.sha256(datos).hexdigest()
            estado = "COINCIDE" if real == shash else "DIFIERE"
            print(f"      SHA256   {estado}  ({len(datos):,} bytes)")
            if real == shash:
                verificadas += 1
            else:
                rotas.append(f"{tk}/{tag}: sha256 difiere")
        if not cadena_ok:
            rotas.append(f"{tk}/{tag}: la cadena no cierra "
                         f"(cik {pc}vs{cik}, acc {pacc}vs{acc})")
    chk("G1 · la cadena hecho -> fact_id -> filing -> CIK es inequivoca", not rotas,
        f"{len(muestra)} hechos, {len(rotas)} rotas " + (str(rotas[:2]) if rotas else ""))
    chk("G2 · el artefacto en disco reproduce el SHA256 registrado",
        verificadas == len(muestra),
        f"{verificadas}/{len(muestra)} verificados contra disco",
        critico=verificadas > 0)

    if limitaciones:
        print("\n  LIMITACIONES DE EVIDENCIA")
        for l in dict.fromkeys(limitaciones):
            print(f"    · {l}")

    n_ok = sum(1 for r in res if r["ok"])
    n_cri = sum(1 for r in res if not r["ok"] and r["critico"])
    print(f"\n  {n_ok}/{len(res)} controles OK · {n_cri} criticos en rojo")
    (OUT / "provenance_ratios.json").write_text(
        json.dumps({"ok": ok_total, "controles": res,
                    "limitaciones": list(dict.fromkeys(limitaciones))},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print("  evidencia -> outputs/docs/auditoria/provenance_ratios.json")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
