"""RAW store CNV: persistencia inmutable, direccionada por contenido.

Decisiones:

* La ruta se deriva del SHA-256 del cuerpo -> la idempotencia es estructural:
  volver a bajar el mismo documento produce la MISMA ruta y no reescribe nada.
* Nunca se sobreescribe. Si la ruta existe, se re-lee del disco y se compara el
  hash; una diferencia es corrupcion del RAW, no un caso normal.
* Un mismo GUID con dos SHA distintos NO es un conflicto: son dos versiones y
  ambas se conservan (CNV republica presentaciones).
* El hash que CNV declara en el upload (`hash` del JSON de adjuntos) NO sirve para
  idempotencia: C0-CNV-006 lo probo distinto del SHA-256 del archivo servido.
  Se guarda como metadato y se compara para reportar, jamas para decidir.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from engine.config import REPO_ROOT

CNV_RAW_ROOT = REPO_ROOT / "data" / "raw" / "engine" / "cnv"

WRITTEN = "WRITTEN"
SIN_CAMBIOS = "SIN_CAMBIOS"

EXT_BY_KIND = {"EMPRESA_PAGE": ".html", "VISOR": ".html", "VALET_KEY": ".json"}
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_b64(content: bytes) -> str:
    return base64.b64encode(hashlib.sha256(content).digest()).decode()


# Decision (2026-08-25, C2->C3 execution session): EMPRESA_PAGE and VISOR embed
# per-request randomness BY SERVER DESIGN, confirmed with a real byte-diff between
# two live fetches of the same URL minutes apart:
#   - EMPRESA_PAGE: cache-busting `?v=<random-guid>` query-strings on static
#     asset <link>/<script> tags (CSS/JS versioning), regenerated every request.
#   - VISOR: an ASP.NET anti-forgery `RequestVerificationToken` hidden input,
#     cryptographically random per request/session (a security feature, not
#     business content).
# Because of this, sha256-of-raw-bytes can NEVER match across two fetches of
# these two artifact kinds, so it cannot answer "did the substantive content
# change" (used by the C-C3-006 idempotency gate). RAW storage keeps hashing
# and addressing by the FULL raw bytes exactly as before (this function does
# NOT touch what gets written to disk or how) -- this is a SEPARATE hash used
# only to decide whether re-fetching produced the same substantive content.
# Scoped narrowly to these 2 confirmed noise patterns; anything else differing
# still counts as a real change.
_RE_ASSET_CACHEBUST = re.compile(
    rb"(\?v=)[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_RE_ANTIFORGERY_TOKEN = re.compile(
    rb'(name="RequestVerificationToken"\s+value=")[^"]+(")')

CANONICALIZABLE_KINDS = ("EMPRESA_PAGE", "VISOR")


def canonicalize(content: bytes, kind: str) -> bytes:
    """Strips the 2 confirmed per-request-random patterns, if applicable to `kind`."""
    if kind not in CANONICALIZABLE_KINDS:
        return content
    canon = _RE_ASSET_CACHEBUST.sub(rb"\1CANON", content)
    canon = _RE_ANTIFORGERY_TOKEN.sub(rb"\1CANON\2", canon)
    return canon


def canonical_sha256(content: bytes, kind: str) -> str:
    """Idempotency hash: same value iff substantive content matches, ignoring the
    2 known-volatile patterns above. NOT used for RAW storage/addressing."""
    return sha256_bytes(canonicalize(content, kind))


def safe_name(name: str, max_len: int = 80) -> str:
    stem = SAFE.sub("_", name).strip("_")
    return stem[:max_len] or "sin_nombre"


@dataclass
class StoredArtifact:
    kind: str
    key: str
    rel_path: str
    abs_path: Path
    sha256: str
    sha256_b64: str
    bytes: int
    action: str                      # WRITTEN | SIN_CAMBIOS
    duplicate_of: str | None = None  # rel_path del primer artefacto con el mismo sha


class RawStore:
    def __init__(self, cuit: str, root: Path = CNV_RAW_ROOT):
        self.cuit = cuit
        self.root = Path(root)
        self.base = self.root / f"CUIT{cuit}"
        self.index_path = self.root / "_index" / "sha256_index.jsonl"
        self._index: dict[str, str] = {}
        self._load_index()
        self.stats = {WRITTEN: 0, SIN_CAMBIOS: 0, "duplicates": 0, "bytes_written": 0}

    def _load_index(self) -> None:
        if not self.index_path.exists():
            return
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._index.setdefault(rec["sha256"], rec["rel_path"])

    def _append_index(self, sha: str, rel_path: str, kind: str, key: str, run_id: str | None) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"sha256": sha, "rel_path": rel_path, "kind": kind,
                                 "key": key, "run_id": run_id}, ensure_ascii=False) + "\n")

    def rel_path_for(self, kind: str, key: str, sha: str, nombre: str | None = None) -> str:
        short = sha[:16]
        if kind == "EMPRESA_PAGE":
            return f"CUIT{self.cuit}/empresa/{short}.html"
        if kind == "VISOR":
            return f"CUIT{self.cuit}/visor/{key}/{short}.html"
        if kind == "VALET_KEY":
            return f"CUIT{self.cuit}/valetkey/{key}/{short}.json"
        if kind == "BLOB":
            ext = Path(nombre or "").suffix.lower() or ".bin"
            return f"CUIT{self.cuit}/blob/{key}/{short}{ext}"
        return f"CUIT{self.cuit}/otros/{safe_name(kind)}/{short}.bin"

    def store(self, kind: str, key: str, content: bytes, nombre: str | None = None,
              run_id: str | None = None) -> StoredArtifact:
        sha = sha256_bytes(content)
        rel = self.rel_path_for(kind, key, sha, nombre)
        path = self.root / rel
        duplicate_of = self._index.get(sha)
        if duplicate_of and duplicate_of != rel:
            self.stats["duplicates"] += 1

        if path.exists():
            on_disk = sha256_bytes(path.read_bytes())
            if on_disk != sha:
                raise IOError(f"RAW corrupto en {rel}: disco={on_disk[:12]} esperado={sha[:12]}")
            action = SIN_CAMBIOS
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".part")
            tmp.write_bytes(content)
            tmp.replace(path)
            action = WRITTEN
            self.stats["bytes_written"] += len(content)
        self.stats[action] += 1
        if sha not in self._index:
            self._index[sha] = rel
            self._append_index(sha, rel, kind, key, run_id)
        return StoredArtifact(kind=kind, key=key, rel_path=rel, abs_path=path, sha256=sha,
                              sha256_b64=sha256_b64(content), bytes=len(content),
                              action=action, duplicate_of=duplicate_of if duplicate_of != rel else None)

    def versions(self, kind: str, key: str) -> list[str]:
        """Todas las versiones RAW conservadas para una misma clave logica."""
        rel = Path(self.rel_path_for(kind, key, "0" * 64))
        folder = self.root / rel.parent
        if not folder.exists():
            return []
        return sorted(p.name for p in folder.iterdir() if p.is_file() and not p.name.endswith(".part"))

    def verify(self, rel_path: str, expected_sha: str) -> tuple[bool, str | None]:
        path = self.root / rel_path
        if not path.exists():
            return False, "MISSING_ON_DISK"
        actual = sha256_bytes(path.read_bytes())
        return (actual == expected_sha), (None if actual == expected_sha else actual)
