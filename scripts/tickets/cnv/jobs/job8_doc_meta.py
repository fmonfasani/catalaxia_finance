# -*- coding: utf-8 -*-
"""
JOB 8 -- Metadatos de documento CNV  (offline, no toca la red)
===============================================================
Extrae de los HTML ya descargados los campos que la CNV declara de forma
ESTRUCTURADA en cada presentacion, y que hoy se estan tirando:

    TipoBalance               Individual | Consolidado   <- el perimetro contable
    FechaCierre               fecha de cierre del ejercicio presentado
    Moneda                    codigo interno de CNV (7 = ARS)
    NormasContablesAplicadas  NIIF | NCP | ...

Los cuatro viven como <propiedad claveinformativa="..."> dentro del HTML de
publicview aif2. Verificado sobre los 2.145 documentos que alimentan
cnv_estados_v2: TipoBalance esta presente en el 100%.

POR QUE IMPORTA
  Un ROE individual y uno consolidado de la misma empresa son numeros
  distintos. Hoy `cnv_estados_norm` no lleva esa marca, asi que el screener
  publica ratios sin declarar el perimetro -- y, peor, puede combinar
  conceptos de perimetros distintos en un mismo ratio.

SALIDA
  Tabla `cnv_doc_meta (accn PK, tipo_balance, fecha_cierre, moneda_cod,
  norma, parsed_at)`. No modifica ninguna tabla existente.

USO
  python job8_doc_meta.py                     # escribe en data/screener.db
  SCREENER_DB=screener.db.test python job8_doc_meta.py
"""
from __future__ import annotations
import datetime as _dt
import io, os, re, sqlite3, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
HTML_DIR = os.path.join(RAIZ, "scripts", "tickets", "cnv", "eeff", "eeff_html")
DB = os.path.join(RAIZ, "data", os.environ.get("SCREENER_DB", "screener.db"))

CAMPOS = {
    "tipo_balance": "TipoBalance",
    "fecha_cierre": "FechaCierre",
    "moneda_cod": "Moneda",
    "norma": "NormasContablesAplicadas",
}
PAT = {k: re.compile(r'claveinformativa="%s"[^>]*>([^<]{0,80})' % v, re.I)
       for k, v in CAMPOS.items()}

# La CNV mezcla mayusculas: 'Individual' y 'INDIVIDUAL' conviven. Dominio cerrado.
NORM_TIPO = {"individual": "INDIVIDUAL", "consolidado": "CONSOLIDADO"}


def norm_fecha(v: str) -> str:
    """'2024-03-31T03:00:00.000Z' -> '2024-03-31'."""
    return v[:10] if v and len(v) >= 10 else ""


def extraer(path: str) -> dict:
    txt = io.open(path, encoding="utf-8", errors="ignore").read()
    out = {}
    for k, rx in PAT.items():
        m = rx.search(txt)
        out[k] = m.group(1).strip() if m else ""
    out["tipo_balance"] = NORM_TIPO.get(out["tipo_balance"].strip().lower(), "")
    out["fecha_cierre"] = norm_fecha(out["fecha_cierre"])
    return out


def main():
    if not os.path.isdir(HTML_DIR):
        sys.exit("ERROR: no existe %s" % HTML_DIR)
    if not os.path.exists(DB):
        sys.exit("ERROR: no existe %s" % DB)
    print("JOB 8 -- metadatos de documento CNV")
    print("=" * 60)
    print("HTML : %s" % HTML_DIR)
    print("Base : %s\n" % DB)

    con = sqlite3.connect(DB)
    cur = con.cursor()
    accns = [r[0] for r in cur.execute(
        "SELECT DISTINCT accn FROM cnv_estados_v2 WHERE accn IS NOT NULL AND accn!=''")]
    print("Documentos referenciados por cnv_estados_v2: %d" % len(accns))

    ahora = _dt.datetime.now().isoformat(timespec="seconds")
    filas, sin_html, sin_tipo = [], 0, 0
    for a in accns:
        p = os.path.join(HTML_DIR, a + ".html")
        if not os.path.exists(p):
            sin_html += 1
            continue
        d = extraer(p)
        if not d["tipo_balance"]:
            sin_tipo += 1
        filas.append((a, d["tipo_balance"], d["fecha_cierre"],
                      d["moneda_cod"], d["norma"], ahora))

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cnv_doc_meta (
            accn         TEXT PRIMARY KEY,
            tipo_balance TEXT,
            fecha_cierre TEXT,
            moneda_cod   TEXT,
            norma        TEXT,
            parsed_at    TEXT
        )
    """)
    cur.executemany("INSERT OR REPLACE INTO cnv_doc_meta VALUES (?,?,?,?,?,?)", filas)
    con.commit()

    print("  sin HTML en disco      : %d" % sin_html)
    print("  sin TipoBalance        : %d" % sin_tipo)
    print("  filas escritas         : %d" % len(filas))
    print("\n  reparto de TipoBalance:")
    for t, n in cur.execute("SELECT tipo_balance,COUNT(*) FROM cnv_doc_meta GROUP BY 1 ORDER BY 2 DESC"):
        print("     %-14s %5d docs" % (t or "(vacio)", n))
    print("\n  normas contables:")
    for t, n in cur.execute("SELECT norma,COUNT(*) FROM cnv_doc_meta GROUP BY 1 ORDER BY 2 DESC"):
        print("     %-14s %5d docs" % (t or "(vacio)", n))

    # Diagnostico: cuit+periodo alimentados por AMBOS perimetros
    mix = cur.execute("""
        SELECT COUNT(*) FROM (
          SELECT e.cuit, e.period_end
          FROM cnv_estados_v2 e JOIN cnv_doc_meta m ON m.accn = e.accn
          WHERE m.tipo_balance != ''
          GROUP BY e.cuit, e.period_end
          HAVING COUNT(DISTINCT m.tipo_balance) > 1)
    """).fetchone()[0]
    uno = cur.execute("""
        SELECT COUNT(*) FROM (
          SELECT e.cuit, e.period_end
          FROM cnv_estados_v2 e JOIN cnv_doc_meta m ON m.accn = e.accn
          WHERE m.tipo_balance != ''
          GROUP BY e.cuit, e.period_end
          HAVING COUNT(DISTINCT m.tipo_balance) = 1)
    """).fetchone()[0]
    print("\n  DIAGNOSTICO perimetro por cuit+periodo:")
    print("     alimentados por UN solo perimetro : %d" % uno)
    print("     alimentados por AMBOS (mezcla)    : %d  <- aqui hay ratios quimera" % mix)
    con.close()
    print("\nJOB 8 -- OK")


if __name__ == "__main__":
    main()
