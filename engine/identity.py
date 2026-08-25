from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from engine.config import REPO_ROOT

SEC_CATALOG_DIR = REPO_ROOT / "data" / "raw" / "catalogo_edgar"
LEGACY_DIR = REPO_ROOT / "scripts" / "screener" / "datos"
RESOLUTIONS_CSV = REPO_ROOT / "data" / "catalogo" / "engine_identity_resolutions.csv"
YF_RULE_VERSION = "derived_rule:v1"


@dataclass
class SeedStats:
    entities: int = 0
    identifiers: int = 0
    byma_links: int = 0
    yf_symbols: int = 0
    conflicts: list[dict] | None = None

    def __post_init__(self) -> None:
        if self.conflicts is None:
            self.conflicts = []


def load_sec_catalog(engine: Engine) -> Path:
    files = sorted(SEC_CATALOG_DIR.glob("company_tickers_*.json"))
    if not files:
        raise FileNotFoundError(f"No hay company_tickers en {SEC_CATALOG_DIR}; descargar antes (clase B)")
    return files[-1]


def catalog_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_entity(
    conn,
    entity_id: str,
    legal_name: str,
    country: str | None,
    cik: str | None,
    cuit: str | None,
    source: str,
) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM identity.entities WHERE entity_id = :e"),
        {"e": entity_id},
    ).scalar()
    if row:
        return False
    conn.execute(
        text(
            """
            INSERT INTO identity.entities (entity_id, legal_name, country, cik, cuit, id_source)
            VALUES (:eid, :name, :country, :cik, :cuit, :src)
            """
        ),
        {"eid": entity_id, "name": legal_name, "country": country,
         "cik": cik, "cuit": cuit, "src": source},
    )
    return True


def add_identifier(conn, entity_id: str, id_type: str, id_value: str,
                   marketplace: str, source: str) -> bool:
    existing = conn.execute(
        text(
            """
            SELECT entity_id, status FROM identity.identifiers
             WHERE id_type = :t AND id_value = :v AND marketplace = :m
            """
        ),
        {"t": id_type, "v": id_value, "m": marketplace},
    ).first()
    if existing:
        if existing.entity_id != entity_id and existing.status == "ACTIVE":
            raise AssertionError(
                f"Colision no registrada: {id_type}:{id_value}@{marketplace} "
                f"ya apunta a {existing.entity_id}, pedido para {entity_id}"
            )
        return False
    conn.execute(
        text(
            """
            INSERT INTO identity.identifiers
                (entity_id, id_type, id_value, marketplace, source)
            VALUES (:eid, :t, :v, :m, :s)
            """
        ),
        {"eid": entity_id, "t": id_type, "v": id_value, "m": marketplace, "s": source},
    )
    return True


def open_review(conn, run_id: str, id_type: str, id_value: str, marketplace: str,
                candidates: list[str], reason: str) -> None:
    dup = conn.execute(
        text(
            """
            SELECT 1 FROM identity.identifier_reviews
             WHERE id_type=:t AND id_value=:v AND COALESCE(marketplace,'')=COALESCE(:m,'')
               AND status='OPEN'
            """
        ),
        {"t": id_type, "v": id_value, "m": marketplace},
    ).scalar()
    if dup:
        return
    conn.execute(
        text(
            """
            INSERT INTO identity.identifier_reviews
                (id_type, id_value, marketplace, candidate_values, detected_by_run, reason)
            VALUES (:t, :v, :m, CAST(:c AS JSONB), :run, :r)
            """
        ),
        {"t": id_type, "v": id_value, "m": marketplace,
         "c": json.dumps(candidates), "run": run_id, "r": reason},
    )


def seed_from_sec_catalog(engine: Engine, run_id: str) -> SeedStats:
    stats = SeedStats()
    catalog_path = load_sec_catalog(engine)
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))

    entities: dict[str, dict] = {}
    idents: dict[tuple[str, str, str], dict] = {}
    for _entry in raw.values():
        cik10 = str(int(_entry["cik_str"])).zfill(10)
        ticker = str(_entry["ticker"]).strip().upper()
        title = str(_entry["title"]).strip()
        entity_id = f"CIK:{cik10}"
        if entity_id not in entities:
            entities[entity_id] = {
                "eid": entity_id, "name": title, "cik": cik10,
                "src": f"sec_company_tickers:{catalog_path.name}",
            }
        idents.setdefault(("CIK", cik10, "SEC"),
                          {"eid": entity_id, "t": "CIK", "v": cik10, "m": "SEC",
                           "s": f"sec_company_tickers:{catalog_path.name}"})
        if ticker:
            idents.setdefault(("TICKER", ticker, "US"),
                              {"eid": entity_id, "t": "TICKER", "v": ticker, "m": "US",
                               "s": f"sec_company_tickers:{catalog_path.name}"})
            idents.setdefault(("YF_SYMBOL", ticker, "yahoo"),
                              {"eid": entity_id, "t": "YF_SYMBOL", "v": ticker, "m": "yahoo",
                               "s": f"yf_rule_us_listing:{YF_RULE_VERSION}"})

    with engine.begin() as conn:
        existing_entities = {r[0] for r in conn.execute(text("SELECT entity_id FROM identity.entities"))}
        new_entities = [e for e in entities.values() if e["eid"] not in existing_entities]
        if new_entities:
            conn.execute(
                text("INSERT INTO identity.entities (entity_id, legal_name, country, cik, cuit, id_source) "
                     "VALUES (:eid, :name, NULL, :cik, NULL, :src)"),
                new_entities,
            )
            stats.entities = len(new_entities)
        existing_idents = {
            (r[0], r[1], r[2])
            for r in conn.execute(
                text("SELECT id_type, id_value, marketplace FROM identity.identifiers WHERE status='ACTIVE'")
            )
        }
        new_idents = [i for k, i in idents.items() if k not in existing_idents]
        if new_idents:
            conn.execute(
                text("INSERT INTO identity.identifiers (entity_id, id_type, id_value, marketplace, source) "
                     "VALUES (:eid, :t, :v, :m, :s)"),
                new_idents,
            )
            stats.identifiers = sum(1 for i in new_idents if i["t"] in ("CIK", "TICKER"))
            stats.yf_symbols = sum(1 for i in new_idents if i["t"] == "YF_SYMBOL")
    return stats


def cross_check_legacy_and_link_byma(engine: Engine, run_id: str) -> SeedStats:
    stats = SeedStats(byma_links=0, yf_symbols=0)
    sec_by_ticker: dict[str, dict] = {}
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT i.id_value, e.entity_id, e.cik
                  FROM identity.identifiers i
                  JOIN identity.entities e ON e.entity_id = i.entity_id
                 WHERE i.id_type='TICKER' AND i.marketplace='US' AND i.status='ACTIVE'
                """
            )
        )
        for r in rows:
            sec_by_ticker[r.id_value] = {"entity_id": r.entity_id, "cik": r.cik}

    with engine.begin() as conn:
        cedears = LEGACY_DIR / "cedears_byma.csv"
        if cedears.exists():
            with open(cedears, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    byma = row["ticker_byma"].strip().upper()
                    usa = row["ticker_usa"].strip().upper()
                    hit = sec_by_ticker.get(usa)
                    if hit:
                        if add_identifier(conn, hit["entity_id"], "TICKER", byma, "BYMA",
                                          f"legacy_cedears_byma:{cedears.name}"):
                            stats.byma_links += 1
                        ba_symbol = f"{byma}.BA"
                        if add_identifier(conn, hit["entity_id"], "YF_SYMBOL", ba_symbol, "yahoo",
                                          f"yf_rule_byma_suffix:{YF_RULE_VERSION}"):
                            stats.yf_symbols += 1
                    else:
                        open_review(conn, run_id, "TICKER", byma, "BYMA",
                                    [usa], f"CEDEAR sin entidad US en fuente de registro (ticker_usa={usa})")

        conflict_catalog = LEGACY_DIR / "acciones_argentinas_usa.csv"
        if conflict_catalog.exists():
            with open(conflict_catalog, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    usa = row["ticker_usa"].strip().upper()
                    legacy_cik = str(row.get("cik", "")).strip()
                    hit = sec_by_ticker.get(usa)
                    if not hit or not legacy_cik:
                        continue
                    if hit["cik"] != legacy_cik.zfill(10):
                        open_review(
                            conn, run_id, "CIK", legacy_cik.zfill(10), "US",
                            [hit["entity_id"]],
                            f"CONFLICTO catálogo legacy {conflict_catalog.name}: "
                            f"{usa}→CIK {legacy_cik} pero fuente de registro dice {hit['entity_id']} "
                            "(EXT-NEW-012: gana la fuente de registro; revisión manual abierta)",
                        )
                        stats.conflicts.append({"ticker": usa, "legacy_cik": legacy_cik,
                                                "record_entity": hit["entity_id"]})
    return stats


def apply_manual_resolutions(engine: Engine, run_id: str) -> SeedStats:
    stats = SeedStats()
    if not RESOLUTIONS_CSV.exists():
        return stats
    with open(RESOLUTIONS_CSV, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    with engine.begin() as conn:
        for row in rows:
            id_type = row["id_type"].strip().upper()
            id_value = row["id_value"].strip().upper()
            marketplace = row["marketplace"].strip().upper() or "US"
            entity_id = row["entity_id"].strip()
            reason = row["reason"].strip()
            resolved_by = row["resolved_by"].strip()
            if not conn.execute(
                text("SELECT 1 FROM identity.entities WHERE entity_id=:e"), {"e": entity_id}
            ).scalar():
                open_review(conn, run_id, id_type, id_value, marketplace,
                            [entity_id], f"resolucion manual sobre entidad inexistente: {reason}")
                stats.conflicts.append({"id_value": id_value, "issue": "entidad destino inexistente"})
                continue
            src = f"manual_resolution:{RESOLUTIONS_CSV.name}"
            added = add_identifier(conn, entity_id, id_type, id_value, marketplace, src)
            if added:
                stats.identifiers += 1
                if id_type == "TICKER":
                    ba = f"{id_value}.BA"
                    if add_identifier(conn, entity_id, "YF_SYMBOL", ba, "yahoo",
                                      f"yf_rule_byma_suffix:{YF_RULE_VERSION} (via {src})"):
                        stats.yf_symbols += 1
            conn.execute(
                text(
                    """
                    UPDATE identity.identifier_reviews
                       SET status='RESOLVED', resolved_entity_id=:e, resolved_at=now(),
                           resolved_note=:note
                     WHERE id_type=:t AND id_value=:v AND COALESCE(marketplace,'')=COALESCE(:m,'')
                       AND status='OPEN'
                    """
                ),
                {"e": entity_id, "t": id_type, "v": id_value, "m": marketplace,
                 "note": f"{reason} [by {resolved_by}]"},
            )
    return stats


def resolve_golden_ypf(engine: Engine) -> dict:
    with engine.connect() as conn:
        ent = conn.execute(
            text(
                """
                SELECT entity_id, legal_name, cik, cuit FROM identity.entities
                 WHERE cik = '0000904851'
                """
            )
        ).first()
        if not ent:
            return {"present": False}
        idents = conn.execute(
            text(
                """
                SELECT id_type, id_value, marketplace, status
                  FROM identity.identifiers
                 WHERE entity_id = :e
                 ORDER BY id_type, marketplace
                """
            ),
            {"e": ent.entity_id},
        ).all()
    return {
        "present": True,
        "entity_id": ent.entity_id,
        "legal_name": ent.legal_name,
        "cik": ent.cik,
        "cuit": ent.cuit,
        "identifiers": [dict(r._mapping) for r in idents],
    }
