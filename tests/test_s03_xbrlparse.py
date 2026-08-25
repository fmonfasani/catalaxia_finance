from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.xbrlparse import (  # noqa: E402
    companyfacts_index,
    parse_instance_bytes,
    parse_linkbase_bytes,
    parse_schema_bytes,
    zip_instance_candidates,
)

NS = 'xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ypf="http://www.ypf.com/xbrl" xmlns:us-gaap="http://fasb.org/us-gaap/2024" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'

INSTANCE_FULL = f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl {NS}>
  <xbrli:context id="c_inst">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000904851</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:context id="c_dur">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000904851</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:context id="c_dim">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000904851</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
    <xbrli:scenario>
      <ypf:SegmentAxis dimension="ypf:SegmentAxis"/>
      <xbrldi:explicitMember xmlns:xbrldi="http://xbrl.org/2005/xbrldt" dimension="us-gaap:StatementBusinessSegmentsAxis">ypf:UpstreamMember</xbrldi:explicitMember>
      <xbrldi:typedMember xmlns:xbrldi="http://xbrl.org/2005/xbrldt" dimension="ypf:ContractTypeTypedAxis"><ypf:ContractType>Petrol</ypf:ContractType></xbrldi:typedMember>
    </xbrli:scenario>
  </xbrli:context>
  <xbrli:unit id="u_bbl">
    <xbrli:measure>iso4217:USD</xbrli:measure>
  </xbrli:unit>
  <xbrli:unit id="u_per">
    <xbrli:divide>
      <xbrli:numerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:numerator>
      <xbrli:denominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:denominator>
    </xbrli:divide>
  </xbrli:unit>
  <us-gaap:Assets contextRef="c_inst" unitRef="u_bbl" decimals="-6">12345000000</us-gaap:Assets>
  <us-gaap:Revenues contextRef="c_dur" unitRef="u_bbl" decimals="-6">9876500000</us-gaap:Revenues>
  <ypf:ProduccionPetrolera contextRef="c_dim" unitRef="u_bbl" decimals="0">42.5</ypf:ProduccionPetrolera>
  <ypf:DatoTexto contextRef="c_dur">texto libre sin unidad</ypf:DatoTexto>
  <us-gaap:NILFact xsi:nil="true" contextRef="c_inst"/>
</xbrli:xbrl>"""

LABEL_LB = f"""<?xml version="1.0" encoding="UTF-8"?>
<link:labelLinkbase {NS} xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:roleRef roleURI="http://www.ypf.com/role/Stmt" xlink:href="ypf-2025.xsd#r1" xlink:type="simple"/>
  <link:labelLink xlink:type="extended" xlink:role="http://www.ypf.com/role/Stmt">
    <link:loc xlink:type="locator" xlink:href="ypf-2025.xsd#Assets" xlink:label="loc_assets"/>
    <link:label xlink:type="resource" xlink:label="lab_es" xlink:role="http://www.xbrl.org/2003/role/label" xml:lang="es">Activos</link:label>
    <link:labelArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label" xlink:from="loc_assets" xlink:to="lab_es"/>
  </link:labelLink>
</link:labelLinkbase>"""

CALC_LB = f"""<?xml version="1.0" encoding="UTF-8"?>
<link:calculationLinkbase {NS} xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:calculationLink xlink:type="extended" xlink:role="http://www.ypf.com/role/Stmt">
    <link:loc xlink:type="locator" xlink:href="ypf-2025.xsd#Assets" xlink:label="p"/>
    <link:loc xlink:type="locator" xlink:href="ypf-2025.xsd#Revenues" xlink:label="c"/>
    <link:calculationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item" xlink:from="p" xlink:to="c" weight="1.0" order="1"/>
  </link:calculationLink>
</link:calculationLinkbase>"""

DEF_LB = f"""<?xml version="1.0" encoding="UTF-8"?>
<link:definitionLinkbase {NS} xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xbrldt="http://xbrl.org/2005/xbrldt">
  <link:definitionLink xlink:type="extended" xlink:role="http://www.ypf.com/role/Dim">
    <link:loc xlink:type="locator" xlink:href="ypf-2025.xsd#ProduccionPetrolera" xlink:label="h"/>
    <link:loc xlink:type="locator" xlink:href="ypf-dim.xsd#SegmentAxis" xlink:label="d"/>
    <link:loc xlink:type="locator" xlink:href="ypf-dim.xsd#UpstreamMember" xlink:label="m"/>
    <link:definitionArc xlink:type="arc" xlink:arcrole="http://xbrl.org/int/dim/dimension-domain" xlink:from="d" xlink:to="m"/>
    <link:definitionArc xlink:type="arc" xlink:arcrole="http://xbrl.org/int/dim/hypercube-dimension" xlink:from="hyp" xlink:to="d" xbrldt:dimension="ypf:SegmentAxis"/>
  </link:definitionLink>
</link:definitionLinkbase>"""

SCHEMA = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:xbrli="http://www.xbrl.org/2003/instance"
           xmlns:link="http://www.xbrl.org/2003/linkbase"
           targetNamespace="http://www.ypf.com/xbrl" elementFormDefault="qualified">
  <xs:element name="ProduccionPetrolera" type="xs:decimal"
              xbrli:periodType="duration" xbrli:balance="debit" abstract="false">
    <xs:annotation>
      <xs:documentation>Barriles de petroleo producidos.</xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="DatoTexto" type="xs:string" xbrli:periodType="duration"/>
</xs:schema>"""


class TestInstance:
    def setup_method(self):
        self.res = parse_instance_bytes(INSTANCE_FULL.encode("utf-8"))

    def test_sin_errores(self):
        assert self.res.errors == []
        assert self.res.stats["facts"] == 5

    def test_fact_instantaneo(self):
        f = next(f for f in self.res.facts if f.tag == "Assets")
        assert f.period_kind == "INSTANT"
        assert f.context_id == "c_inst"
        assert f.value_numeric == 12_345_000_000.0
        assert f.taxonomy == "us-gaap"
        assert not self.res.contexts["c_inst"].dimensions

    def test_fact_duration(self):
        f = next(f for f in self.res.facts if f.tag == "Revenues")
        ctx = self.res.contexts[f.context_id]
        assert f.period_kind == "DURATION"
        assert ctx.start_date == "2025-01-01" and ctx.end_date == "2025-12-31"

    def test_unidad_simple(self):
        u = self.res.units["u_bbl"]
        assert u.unit_type == "SIMPLE"
        assert u.measures == ["iso4217:USD"]

    def test_unidad_dividida(self):
        u = self.res.units["u_per"]
        assert u.unit_type == "DIVIDED"
        assert u.numerator == ["iso4217:USD"]
        assert u.denominator == ["xbrli:shares"]

    def test_contexto_dimensional_explicito(self):
        ctx = self.res.contexts["c_dim"]
        explicit = [d for d in ctx.dimensions if not d["typed"]]
        typed = ctx.typed_dimensions
        assert any(d["member"].endswith("UpstreamMember") for d in explicit)
        assert {t["dimension"].rsplit(":", 1)[-1] for t in ctx.typed_dimensions} == \
            {"ContractTypeTypedAxis", "SegmentAxis"}
        assert ctx.dim_count == 3

    def test_fact_dimensional_y_texto(self):
        dim_fact = next(f for f in self.res.facts if f.tag == "ProduccionPetrolera")
        assert dim_fact.taxonomy == "ypf"
        assert dim_fact.is_numeric is True
        texto = next(f for f in self.res.facts if f.tag == "DatoTexto")
        assert texto.is_numeric is False
        assert texto.value_text == "texto libre sin unidad"

    def test_nil_fact(self):
        nil_f = next(f for f in self.res.facts if f.tag == "NILFact")
        assert nil_f.is_nil is True
        assert nil_f.value_numeric is None

    def test_qnames_unicos_por_namespace(self):
        qnames = {f.qname for f in self.res.facts}
        assert "http://fasb.org/us-gaap/2024#Assets" in qnames
        assert "http://www.ypf.com/xbrl#ProduccionPetrolera" in qnames

    def test_xml_roto_devuelve_error(self):
        res = parse_instance_bytes(b"<xbrli:xbrl><unclosed>")
        assert res.errors and res.errors[0]["code"] == "XML_SYNTAX"


class TestLinkbases:
    def test_label(self):
        rels = parse_linkbase_bytes(LABEL_LB.encode(), "lab")
        lb = [r for r in rels if r.linkbase == "LABEL"]
        assert len(lb) == 1
        r = lb[0]
        assert r.from_qname == "Assets"
        assert r.label_text == "Activos"
        assert r.lang == "es"

    def test_calculo_peso(self):
        rels = parse_linkbase_bytes(CALC_LB.encode(), "cal")
        calc = [r for r in rels if r.arc_role.endswith("summation-item")]
        assert len(calc) == 1
        assert calc[0].weight == 1.0
        assert calc[0].order_num == 1.0
        assert calc[0].role == "http://www.ypf.com/role/Stmt"

    def test_definicion_dimension(self):
        rels = parse_linkbase_bytes(DEF_LB.encode(), "def")
        dims = [r for r in rels if r.dimension_qname]
        assert dims and dims[0].dimension_qname.endswith("SegmentAxis")


class TestSchema:
    def test_custom_concepts(self):
        cs = parse_schema_bytes(SCHEMA.encode(), "ypf-2025.xsd")
        by_name = {c.tag: c for c in cs}
        p = by_name["ProduccionPetrolera"]
        assert p.period_type == "duration"
        assert p.balance == "debit"
        assert p.documentation and "petroleo" in p.documentation.lower()
        assert p.taxonomy == "ypf"
        t = by_name["DatoTexto"]
        assert t.period_type == "duration" and t.balance is None


class TestZip:
    def test_zip_con_instancia_schema_linkbase(self):
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("dir/ypf-2025_htm.xml", INSTANCE_FULL)
            zf.writestr("dir/ypf-2025.xsd", SCHEMA)
            zf.writestr("dir/ypf-2025_lab.xml", LABEL_LB)
            zf.writestr("dir/MetaLinks.json", "{}")
        tmp = Path("data/_test_s03.zip")
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_bytes(buf.getvalue())
        try:
            members = list(zipfile.ZipFile(tmp).namelist())
            cands = zip_instance_candidates(members)
            assert cands == ["dir/ypf-2025_htm.xml"]
            data = zipfile.ZipFile(tmp).read(cands[0])
            res = parse_instance_bytes(data)
            assert res.stats["facts"] == 5
        finally:
            tmp.unlink()


class TestCompanyFacts:
    def test_index(self):
        cf = {"facts": {"us-gaap": {"Revenues": {
            "label": "Revenues", "description": "Total revenues",
            "units": {"USD": [
                {"start": "2024-01-01", "end": "2024-12-31", "val": 1},
                {"start": "2025-01-01", "end": "2025-12-31", "val": 2},
            ]}}}}}
        idx = companyfacts_index(cf)
        entry = idx["us-gaap#Revenues"]
        assert entry["obs"] == 2
        assert entry["unit_kinds"] == ["USD"]
        assert entry["first_period"] == "2024-12-31"
        assert entry["last_period"] == "2025-12-31"


@pytest.mark.parametrize("content,ok", [(INSTANCE_FULL, True), (b"<bad>", False)])
def test_smoke_parse(content, ok):
    res = parse_instance_bytes(content.encode() if isinstance(content, str) else content)
    assert (res.stats.get("facts", 0) > 0) is ok or bool(res.errors) != ok
