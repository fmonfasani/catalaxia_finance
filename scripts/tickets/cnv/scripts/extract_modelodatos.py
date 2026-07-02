from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
EEFF_ROOT = ROOT / "eeff"
OUT_JSON = ROOT / "debug" / "modelodatos_extract.json"
OUT_CSV = ROOT / "debug" / "modelodatos_extract.csv"

ROOT.joinpath("debug").mkdir(exist_ok=True)

RX_MODELO = re.compile(r"<modeloDatos>(.*?)</modeloDatos>", re.S | re.I)


def extract_modelodatos(html_text: str):
    m = RX_MODELO.search(html_text)
    if not m:
        return None
    payload = m.group(1)
    try:
        root = ET.fromstring(f"<root>{payload}</root>")
    except ET.ParseError as exc:
        return {"error": str(exc), "raw": payload[:2000]}

    entidades = []
    for entidad in root.findall("entidad"):
        props = []
        for prop in entidad.findall("propiedad"):
            props.append(
                {
                    "id": prop.get("id"),
                    "claveinformativa": prop.get("claveinformativa"),
                    "visible": prop.get("visible"),
                    "value": prop.text or "",
                }
            )
        entidades.append(
            {
                "id": entidad.get("id"),
                "clave": entidad.get("clave"),
                "tipo": entidad.get("tipo"),
                "visibilidad": entidad.get("visibilidad"),
                "propiedades": props,
            }
        )
    return {"entidades": entidades}


def main():
    rows = []
    for html_path in sorted(EEFF_ROOT.rglob("*.html")):
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        parsed = extract_modelodatos(html_text)
        if not parsed:
            continue
        rows.append(
            {
                "ticker": html_path.parent.name,
                "file": html_path.name,
                "path": str(html_path),
                "entidades": len(parsed.get("entidades", [])),
                "propiedades": sum(len(e.get("propiedades", [])) for e in parsed.get("entidades", [])),
                "sample": json.dumps(parsed.get("entidades", [])[:1], ensure_ascii=False)[:500],
                "error": parsed.get("error", ""),
            }
        )

    OUT_JSON.write_text(json.dumps(rows[:100], ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        import pandas as pd

        df = pd.DataFrame(rows)
        df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    except Exception:
        pass

    print(f"Processed {len(rows)} EEFF files")
    print(f"Wrote {OUT_JSON}")
    if OUT_CSV.exists():
        print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
