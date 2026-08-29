"""Identity v1 — capa de dominio.

Responde una sola pregunta, y la responde con evidencia:

    ¿Como sabe Catalaxia que el CIK X, el CUIT Y y el instrumento Z
    representan la misma entidad economica?

La respuesta NUNCA es "porque el nombre coincide" ni "porque el ticker es el
mismo" ni "porque estaba asi en SQLite". La respuesta es siempre una assertion
con fuente, registro y cita, o bien un REVIEW_REQUIRED abierto.

Este modulo es independiente: no toca el parser SEC, el fetcher de Market ni el
fetcher de CNV. Escribe unicamente en el schema identity_v1.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field

from sqlalchemy import text

# =====================================================================
# Errores del dominio
# =====================================================================


class IdentityError(Exception):
    """Base de los errores de identidad."""


class UnknownEntity(IdentityError):
    """Se referencio una entidad que no existe. No se crea al vuelo."""


class UnusableSource(IdentityError):
    """La fuente esta catalogada como inutilizable para identidad."""


class MissingBridge(IdentityError):
    """Falta el puente entre dos espacios de identificadores."""


class ProcesoFirmandoComoHumano(IdentityError):
    """Un proceso automatico intento registrar una decision humana.

    F-016: el piloto escribia method='HUMAN_DECISION' con el nombre de una
    persona que nunca reviso nada. Una decision humana la toma una persona;
    un proceso puede proponer, nunca ratificar.
    """


PREFIJO_PROCESO = "proc:"


def _exigir_persona(resolved_by: str, que: str) -> None:
    if not resolved_by or resolved_by.startswith(PREFIJO_PROCESO):
        raise ProcesoFirmandoComoHumano(
            f"{que} exige una persona identificable, no {resolved_by!r}. "
            f"Los procesos usan el prefijo {PREFIJO_PROCESO!r} y no pueden ratificar."
        )


# =====================================================================
# entity_key: ULID. Opaco por diseño (D-I-B).
# =====================================================================

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_entity_key() -> str:
    """Genera 'E' + ULID.

    La clave NO se deriva de ningun identificador externo. Si se derivara del
    CIK, corregir un CIK mal atribuido obligaria a reescribir cada FK del
    sistema — exactamente el fallo que Identity v1 existe para impedir.
    """
    ms = int(time.time() * 1000)
    rnd = int.from_bytes(secrets.token_bytes(10), "big")
    n = (ms << 80) | rnd
    out = []
    for _ in range(26):
        out.append(_CROCKFORD[n & 31])
        n >>= 5
    return "E" + "".join(reversed(out))


# =====================================================================
# Normalizacion y validacion de identificadores
# =====================================================================

_RE_NO_DIGITO = re.compile(r"\D")


def norm_cik(v: str) -> str:
    """CIK canonico: 10 digitos con ceros a la izquierda."""
    d = _RE_NO_DIGITO.sub("", str(v))
    if not d:
        raise ValueError(f"CIK sin digitos: {v!r}")
    if len(d) > 10:
        raise ValueError(f"CIK de {len(d)} digitos: {v!r}")
    return d.zfill(10)


def norm_cuit(v: str) -> str:
    """CUIT canonico: 11 digitos sin guiones."""
    d = _RE_NO_DIGITO.sub("", str(v))
    if len(d) != 11:
        raise ValueError(f"CUIT debe tener 11 digitos, tiene {len(d)}: {v!r}")
    return d


def cuit_valido(v: str) -> bool:
    """Digito verificador del CUIT (modulo 11).

    Un CUIT con checksum invalido NO puede entrar como identificador
    autoritativo: seria fabricar identidad.
    """
    try:
        d = norm_cuit(v)
    except ValueError:
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    s = sum(int(c) * p for c, p in zip(d[:10], pesos))
    resto = 11 - (s % 11)
    dv = 0 if resto == 11 else (9 if resto == 10 else resto)
    return dv == int(d[10])


def norm_lei(v: str) -> str:
    """LEI canonico: 20 alfanumericos en mayuscula (ISO 17442)."""
    s = str(v).strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{18}[0-9]{2}", s):
        raise ValueError(f"LEI mal formado: {v!r}")
    return s


NORMALIZADORES = {"CIK": norm_cik, "CUIT": norm_cuit, "LEI": norm_lei}

# Tipos que jamas son identidad juridica (D-I-D). El schema tambien lo impide;
# aca se corta antes para dar un mensaje util.
NUNCA_AUTORITATIVOS = {"TICKER", "YF_SYMBOL", "LEGACY_ENTITY_ID"}


def ref(id_type: str, id_namespace: str, id_value: str) -> str:
    """Referencia textual de un identificador, para left_ref/right_ref."""
    return f"{id_type}:{id_namespace}:{id_value}"


# =====================================================================
# Evidencia — sin esto no hay VERIFIED. No es opcional.
# =====================================================================


@dataclass(frozen=True)
class Evidence:
    source_id: str          # debe existir en identity_v1.source
    source_record: str      # accession, URL, id de registro: localizable
    quote: str              # cita textual: un tercero puede reproducirla
    resolved_by: str        # persona o proceso responsable
    reason: str | None = None
    # F-036: los hechos ESTRUCTURADOS que la fuente declara, no la cita legible.
    # Para GLEIF->CUIT: {"registeredAt": "RA000009", "registeredAs": "30-54668997-9"}.
    # `quote` es prosa para un humano; esto es lo que un auditor contrasta contra
    # la fuente en un solo request. Un CUIT afirmado por GLEIF sin esto lo
    # rechaza `ck_gleif_cuit_declara_autoridad`.
    facts: dict | None = None


@dataclass
class Result:
    status: str                     # VERIFIED | CANDIDATE | REVIEW_REQUIRED | REJECTED
    assertion_id: int | None = None
    identifier_id: int | None = None
    is_authoritative: bool = False
    conflict_id: int | None = None
    review_id: int | None = None
    motivo: str = ""
    detalle: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in ("VERIFIED", "CANDIDATE")


# =====================================================================
# Catalogo de fuentes
# =====================================================================


def source_authority(conn, source_id: str, id_type: str) -> tuple[str, bool]:
    """Devuelve (authority_level, es_autoritativa_para_este_id_type).

    La autoridad es propiedad de la FUENTE, no del dato. GLEIF es autoritativa
    para LEI y CUIT y no dice nada sobre CIK; SEC es autoritativa para CIK y no
    publica LEI. Confundir esto es como se fabrica identidad falsa.
    """
    row = conn.execute(
        text(
            "SELECT authority_level, COALESCE(authoritative_for, '{}') "
            "FROM identity_v1.source WHERE source_id = :s"
        ),
        {"s": source_id},
    ).first()
    if row is None:
        raise UnusableSource(
            f"Fuente '{source_id}' no esta en identity_v1.source. "
            "Registrar la fuente y su nivel de autoridad antes de usarla."
        )
    nivel, para = row
    if nivel == "UNUSABLE":
        raise UnusableSource(f"Fuente '{source_id}' catalogada UNUSABLE para identidad.")
    return nivel, (nivel == "AUTHORITATIVE" and id_type in set(para))


# =====================================================================
# Entidades
# =====================================================================


def create_entity(conn, preferred_name: str, country: str | None = None,
                  entity_key: str | None = None) -> str:
    key = entity_key or new_entity_key()
    conn.execute(
        text(
            "INSERT INTO identity_v1.entity (entity_key, preferred_name, country) "
            "VALUES (:k, :n, :c)"
        ),
        {"k": key, "n": preferred_name, "c": country},
    )
    return key


def resolve_or_create_entity(conn, *, preferred_name: str, id_type: str,
                             id_namespace: str, id_value: str,
                             country: str | None = None) -> tuple[str, bool]:
    """Resuelve la entidad por su identificador autoritativo; la crea si no existe.

    F-023: `create_entity` a secas hacia el piloto no idempotente — cada corrida
    generaba una entidad nueva con un ULID nuevo. Aca se resuelve PRIMERO por el
    identificador, que es lo estable, y se crea solo si nadie lo reclama.

    La clave sigue siendo opaca (D-I-B): no se deriva del identificador, se
    BUSCA por el. Devuelve (entity_key, creada).
    """
    norm = NORMALIZADORES.get(id_type)
    if norm:
        id_value = norm(id_value)
    existente = entity_of(conn, id_type, id_namespace, id_value)
    if existente:
        return existente, False
    return create_entity(conn, preferred_name, country), True


def resolver_por_candidatos(conn, candidatos: list[tuple[str, str, str]]):
    """Resuelve una entidad por CUALQUIERA de sus identificadores autoritativos.

    F-032, segunda mitad. `resolve_or_create_entity` resuelve por UN solo
    identificador: el que se le pasa. Si la entidad ya existe bajo OTRO de sus
    identificadores —porque cambio el orden de las fuentes, o porque una corrida
    anterior la anclo por LEI y esta la busca por CIK— no la encuentra y crea
    una duplicada.

    Aca se buscan TODOS los candidatos. Si dos apuntan a entidades distintas NO
    se fusiona nada: eso es un conflicto y lo tiene que resolver una persona.
    Fusionar por coincidencia parcial seria inventar identidad.

    Devuelve (entity_key | None, conflicto: list[str]).
    """
    hallados: dict[str, list[str]] = {}
    for id_type, id_namespace, id_value in candidatos:
        if not id_value:
            continue
        norm = NORMALIZADORES.get(id_type)
        try:
            v = norm(id_value) if norm else id_value
        except ValueError:
            continue
        ek = entity_of(conn, id_type, id_namespace, v)
        if ek:
            hallados.setdefault(ek, []).append(ref(id_type, id_namespace, v))
    if not hallados:
        return None, []
    if len(hallados) == 1:
        return next(iter(hallados)), []
    return None, [f"{k}: {', '.join(v)}" for k, v in hallados.items()]


def require_entity(conn, entity_key: str) -> None:
    if not conn.execute(
        text("SELECT 1 FROM identity_v1.entity WHERE entity_key = :k"),
        {"k": entity_key},
    ).scalar():
        raise UnknownEntity(
            f"Entidad {entity_key!r} no existe. Identity v1 no crea entidades "
            "implicitamente: una entidad economica se declara, no se infiere."
        )


def entity_of(conn, id_type: str, id_namespace: str, id_value: str) -> str | None:
    """Entidad a la que apunta un identificador autoritativo vigente."""
    return conn.execute(
        text(
            "SELECT entity_key FROM identity_v1.identifier "
            " WHERE id_type=:t AND id_namespace=:n AND id_value=:v "
            "   AND is_authoritative AND valid_to IS NULL"
        ),
        {"t": id_type, "n": id_namespace, "v": id_value},
    ).scalar()


# =====================================================================
# Assertions
# =====================================================================


def _insert_assertion(conn, *, subject_type, entity_key, left_ref, right_ref,
                      relationship, method, confidence, status, ev: Evidence | None,
                      resolution_reason=None) -> int:
    return conn.execute(
        text(
            """
            INSERT INTO identity_v1.assertion
                (subject_type, entity_key, left_ref, right_ref, relationship,
                 method, confidence, status, source_id, source_record, evidence,
                 resolved_by, resolution_reason, source_facts)
            VALUES
                (:st, :ek, :lr, :rr, :rel, :m, :cf, :s, :src, :recd, :ev,
                 :by, :why, CAST(:facts AS JSONB))
            RETURNING assertion_id
            """
        ),
        {
            "st": subject_type, "ek": entity_key, "lr": left_ref, "rr": right_ref,
            "rel": relationship, "m": method, "cf": confidence, "s": status,
            "src": ev.source_id if ev else None,
            "recd": ev.source_record if ev else None,
            "ev": ev.quote if ev else None,
            "by": ev.resolved_by if ev else None,
            "why": resolution_reason or (ev.reason if ev else None),
            "facts": json.dumps(ev.facts) if (ev and ev.facts) else None,
        },
    ).scalar()


def open_conflict(conn, *, id_type, id_namespace, id_value, candidatos: list[str],
                  reason: str, detected_by: str = "identity_v1") -> int:
    return conn.execute(
        text(
            """
            INSERT INTO identity_v1.conflict
                (id_type, id_namespace, id_value, candidate_entity_keys,
                 detected_by, reason)
            VALUES (:t, :n, :v, CAST(:c AS JSONB), :d, :r)
            RETURNING conflict_id
            """
        ),
        {"t": id_type, "n": id_namespace, "v": id_value,
         "c": json.dumps(candidatos), "d": detected_by, "r": reason},
    ).scalar()


def open_review(conn, *, entity_key: str | None, candidatos: dict | list,
                reason: str, evidence: str | None = None) -> int:
    """Abre una review, o devuelve la que ya esta abierta por el mismo motivo.

    F-023: sin esto cada corrida del piloto acumulaba una review nueva por el
    mismo hecho pendiente, y la cola crecia sola. Una review es "lo que el
    sistema admite no saber": no saberlo dos veces no son dos reviews.
    """
    ya = conn.execute(
        text(
            "SELECT review_id FROM identity_v1.review "
            " WHERE status='OPEN' AND reason=:r "
            "   AND entity_key IS NOT DISTINCT FROM :e"
        ),
        {"r": reason, "e": entity_key},
    ).scalar()
    if ya:
        return ya
    return conn.execute(
        text(
            """
            INSERT INTO identity_v1.review
                (entity_key, candidate_identifiers, reason, evidence)
            VALUES (:e, CAST(:c AS JSONB), :r, :ev)
            RETURNING review_id
            """
        ),
        {"e": entity_key, "c": json.dumps(candidatos), "r": reason, "ev": evidence},
    ).scalar()


# =====================================================================
# El punto de entrada principal
# =====================================================================

_METODOS_AUTORITATIVOS = {"REGISTRY", "REGULATORY_DOCUMENT"}


def assert_identifier(conn, *, entity_key: str, id_type: str, id_namespace: str,
                      id_value: str, method: str, evidence: Evidence) -> Result:
    """Afirma que un identificador pertenece a una entidad.

    Nunca decide en silencio. Devuelve uno de:
      VERIFIED         la fuente es autoritativa para este id_type y hay cita
      CANDIDATE        la fuente corrobora pero no establece
      REVIEW_REQUIRED  hay ambiguidad; queda una review abierta
      REJECTED         el identificador ya pertenece autoritativamente a otra
                       entidad; queda un conflict abierto
    """
    require_entity(conn, entity_key)

    norm = NORMALIZADORES.get(id_type)
    if norm:
        id_value = norm(id_value)

    if id_type == "CUIT" and not cuit_valido(id_value):
        return Result(status="REJECTED",
                      motivo=f"CUIT {id_value} no pasa el digito verificador (modulo 11)")

    nivel, es_autoritativa = source_authority(conn, evidence.source_id, id_type)

    # --- que confianza y que estado corresponden ---------------------
    if es_autoritativa and method in _METODOS_AUTORITATIVOS:
        confidence, status, autoritativo = "AUTHORITATIVE", "VERIFIED", True
    elif method == "HUMAN_DECISION":
        if not evidence.reason:
            raise IdentityError(
                "Una decision humana exige resolution_reason: quien decidio y por que."
            )
        _exigir_persona(evidence.resolved_by, "Una decision humana")
        confidence, status, autoritativo = "STRONG", "VERIFIED", True
    elif nivel in ("CORROBORATING", "DISCOVERY_ONLY"):
        confidence, status, autoritativo = "WEAK", "CANDIDATE", False
    else:
        # fuente AUTHORITATIVE pero no para ESTE id_type: corrobora, no establece
        confidence, status, autoritativo = "WEAK", "CANDIDATE", False

    if id_type in NUNCA_AUTORITATIVOS:
        # Un ticker es una convencion de mercado reutilizable, no identidad.
        confidence = "WEAK" if confidence == "AUTHORITATIVE" else confidence
        status, autoritativo = "CANDIDATE", False

    # --- deteccion de conflicto ANTES de escribir ---------------------
    if autoritativo:
        dueno = entity_of(conn, id_type, id_namespace, id_value)
        if dueno == entity_key:
            return Result(status="VERIFIED", is_authoritative=True,
                          motivo="ya afirmado para esta entidad (idempotente)")
        if dueno is not None:
            cid = open_conflict(
                conn, id_type=id_type, id_namespace=id_namespace, id_value=id_value,
                candidatos=[dueno, entity_key],
                reason=(f"{ref(id_type, id_namespace, id_value)} ya es autoritativo "
                        f"de {dueno}; se intento atribuirlo tambien a {entity_key}"),
            )
            aid = _insert_assertion(
                conn, subject_type="ENTITY_IDENTIFIER", entity_key=entity_key,
                left_ref=ref(id_type, id_namespace, id_value), right_ref=None,
                relationship="BELONGS_TO", method=method, confidence="DISPUTED",
                status="REJECTED", ev=evidence,
                resolution_reason=f"conflicto {cid}: identificador ya atribuido a {dueno}",
            )
            return Result(status="REJECTED", assertion_id=aid, conflict_id=cid,
                          motivo=(f"{ref(id_type, id_namespace, id_value)} pertenece a "
                                  f"{dueno}. Un identificador autoritativo no puede "
                                  f"designar dos entidades."),
                          detalle={"entidad_actual": dueno})

        # ¿la entidad ya tiene otro valor autoritativo de este mismo tipo?
        actual = conn.execute(
            text(
                "SELECT id_value FROM identity_v1.identifier "
                " WHERE entity_key=:e AND id_type=:t AND id_namespace=:n "
                "   AND is_authoritative AND valid_to IS NULL"
            ),
            {"e": entity_key, "t": id_type, "n": id_namespace},
        ).scalar()
        if actual is not None and actual != id_value:
            cid = open_conflict(
                conn, id_type=id_type, id_namespace=id_namespace, id_value=None,
                candidatos=[entity_key],
                reason=(f"{entity_key} tiene {id_type} autoritativo {actual} y se "
                        f"afirma {id_value} desde {evidence.source_id}"),
            )
            rid = open_review(
                conn, entity_key=entity_key,
                candidatos={"id_type": id_type, "id_namespace": id_namespace,
                            "vigente": actual, "propuesto": id_value,
                            "fuente_propuesta": evidence.source_id},
                reason=f"{id_type} contradictorio para {entity_key}",
                evidence=evidence.quote,
            )
            aid = _insert_assertion(
                conn, subject_type="ENTITY_IDENTIFIER", entity_key=entity_key,
                left_ref=ref(id_type, id_namespace, id_value), right_ref=None,
                relationship="BELONGS_TO", method=method, confidence="DISPUTED",
                status="REVIEW_REQUIRED", ev=evidence,
                resolution_reason=f"conflicto {cid} / review {rid}",
            )
            return Result(status="REVIEW_REQUIRED", assertion_id=aid,
                          conflict_id=cid, review_id=rid,
                          motivo=(f"{entity_key} ya tiene {id_type} {actual}; "
                                  f"{evidence.source_id} afirma {id_value}. "
                                  "No se elige en silencio."),
                          detalle={"vigente": actual, "propuesto": id_value})

    # --- idempotencia de la propuesta (F-034) --------------------------
    # Los indices unicos solo cubren lo autoritativo. Una propuesta CANDIDATE de
    # la MISMA fuente repetida en otra corrida es la misma propuesta, no una
    # nueva. Dos fuentes DISTINTAS proponiendo el mismo valor si son dos
    # corroboraciones independientes y ambas se conservan.
    if not autoritativo:
        ya = conn.execute(
            text(
                """
                SELECT i.identifier_id FROM identity_v1.identifier i
                  JOIN identity_v1.assertion a USING (assertion_id)
                 WHERE i.entity_key=:e AND i.id_type=:t AND i.id_namespace=:n
                   AND i.id_value=:v AND i.valid_to IS NULL
                   AND a.source_id IS NOT DISTINCT FROM :src
                 LIMIT 1
                """
            ),
            {"e": entity_key, "t": id_type, "n": id_namespace, "v": id_value,
             "src": evidence.source_id},
        ).scalar()
        if ya:
            return Result(status=status, identifier_id=ya, is_authoritative=False,
                          motivo=f"{evidence.source_id} ya propuso este valor (idempotente)")

    # --- escritura ----------------------------------------------------
    aid = _insert_assertion(
        conn, subject_type="ENTITY_IDENTIFIER", entity_key=entity_key,
        left_ref=ref(id_type, id_namespace, id_value), right_ref=None,
        relationship="BELONGS_TO", method=method, confidence=confidence,
        status=status, ev=evidence,
    )
    iid = conn.execute(
        text(
            """
            INSERT INTO identity_v1.identifier
                (entity_key, id_type, id_namespace, id_value, is_authoritative,
                 assertion_id)
            VALUES (:e, :t, :n, :v, :a, :aid)
            RETURNING identifier_id
            """
        ),
        {"e": entity_key, "t": id_type, "n": id_namespace, "v": id_value,
         "a": autoritativo, "aid": aid},
    ).scalar()
    return Result(status=status, assertion_id=aid, identifier_id=iid,
                  is_authoritative=autoritativo,
                  motivo=f"fuente {evidence.source_id} nivel={nivel}")


# =====================================================================
# Puentes entre espacios de identificadores (CIK <-> LEI, ciclo G5)
# =====================================================================


def assert_bridge(conn, *, left_ref_: str, right_ref_: str, method: str,
                  evidence: Evidence) -> Result:
    """Afirma que dos identificadores de espacios distintos son la misma entidad.

    G5: no existe fuente primaria que publique CIK -> LEI. Ni SEC ni GLEIF lo
    hacen. Por eso este puente admite HUMAN_DECISION y por eso la resolucion
    humana es una capacidad PERMANENTE de Identity v1, no un paso transitorio.

    F-016: y por eso mismo un proceso NO puede firmarlo. Si el puente no lo
    ratifico una persona, el estado honesto es REVIEW_REQUIRED.
    """
    # idempotencia (F-023): una propuesta automatica ya vigente no se duplica.
    # Una ratificacion humana si se registra siempre: es un acto nuevo.
    if method != "HUMAN_DECISION":
        ya = conn.execute(
            text(
                "SELECT assertion_id FROM identity_v1.assertion "
                " WHERE subject_type='IDENTIFIER_BRIDGE' AND valid_to IS NULL "
                "   AND left_ref=:l AND right_ref=:r AND method=:m"
            ),
            {"l": left_ref_, "r": right_ref_, "m": method},
        ).scalar()
        if ya:
            return Result(status="CANDIDATE", assertion_id=ya,
                          motivo="puente ya propuesto (idempotente)")

    if method == "HUMAN_DECISION":
        if not evidence.reason:
            raise IdentityError("El puente humano exige resolution_reason.")
        _exigir_persona(evidence.resolved_by, "Ratificar un puente CIK<->LEI")
        confidence, status = "STRONG", "VERIFIED"
    else:
        _, es_aut = source_authority(conn, evidence.source_id,
                                     left_ref_.split(":", 1)[0])
        confidence, status = (("AUTHORITATIVE", "VERIFIED") if es_aut
                              else ("WEAK", "CANDIDATE"))
    aid = _insert_assertion(
        conn, subject_type="IDENTIFIER_BRIDGE", entity_key=None,
        left_ref=left_ref_, right_ref=right_ref_, relationship="SAME_ENTITY",
        method=method, confidence=confidence, status=status, ev=evidence,
    )
    return Result(status=status, assertion_id=aid,
                  is_authoritative=(confidence == "AUTHORITATIVE"))


def bridge_verificado(conn, left_ref_: str, right_ref_: str) -> bool:
    return bool(conn.execute(
        text(
            "SELECT 1 FROM identity_v1.assertion "
            " WHERE subject_type='IDENTIFIER_BRIDGE' AND status='VERIFIED' "
            "   AND valid_to IS NULL "
            "   AND ((left_ref=:l AND right_ref=:r) OR (left_ref=:r AND right_ref=:l))"
        ),
        {"l": left_ref_, "r": right_ref_},
    ).scalar())


# =====================================================================
# GLEIF: LEI -> CUIT
# =====================================================================

# Autoridades de registro que publican un identificador fiscal argentino.
RA_CON_CUIT = {"RA000009": "AFIP", "RA000010": "IGJ/RNS"}


def cuit_desde_gleif(rec: dict) -> tuple[str | None, str]:
    """Extrae el CUIT de un registro GLEIF, o explica por que no se puede.

    G4: el LEI NO es el CUIT y registeredAs NO es siempre un CUIT. Solo cuando
    la registration authority es una que asigna CUIT y el valor pasa el digito
    verificador se puede tomar como identificador fiscal.
    """
    ent = (rec.get("attributes") or rec).get("entity", {}) or {}
    ra = (ent.get("registeredAt") or {}).get("id")
    crudo = ent.get("registeredAs")
    if ra not in RA_CON_CUIT:
        return None, f"registrationAuthority {ra!r} no asigna CUIT"
    if not crudo:
        return None, f"registeredAs vacio (authority {ra})"
    try:
        cuit = norm_cuit(crudo)
    except ValueError as e:
        return None, f"registeredAs {crudo!r} no es un CUIT: {e}"
    if not cuit_valido(cuit):
        return None, f"CUIT {cuit} no pasa el digito verificador"
    return cuit, f"{RA_CON_CUIT[ra]} ({ra}) registeredAs={crudo}"


def gleif_facts(rec: dict) -> dict:
    """Los hechos estructurados del registro GLEIF, para `Evidence.facts` (F-036)."""
    ent = (rec.get("attributes") or rec).get("entity", {}) or {}
    return {"registeredAt": (ent.get("registeredAt") or {}).get("id"),
            "registeredAs": ent.get("registeredAs")}


def link_cuit_desde_gleif(conn, *, entity_key: str, lei: str, gleif_record: dict,
                          source_record: str, resolved_by: str) -> Result:
    """Adjunta el CUIT que GLEIF publica, exigiendo el puente si hace falta.

    Regla dura (G5): si la entidad esta anclada en un CIK, el CUIT que viene por
    la via del LEI solo puede consolidarse si existe un puente CIK<->LEI
    VERIFIED. Sin puente, la cadena CIK -> LEI -> CUIT tiene un eslabon no
    demostrado y el resultado es REVIEW_REQUIRED, nunca VERIFIED automatico.
    """
    require_entity(conn, entity_key)
    lei = norm_lei(lei)
    cuit, motivo = cuit_desde_gleif(gleif_record)
    if cuit is None:
        rid = open_review(
            conn, entity_key=entity_key,
            candidatos={"lei": lei, "cuit": None},
            reason=f"GLEIF no permite derivar CUIT: {motivo}",
            evidence=source_record,
        )
        return Result(status="REVIEW_REQUIRED", review_id=rid,
                      motivo=f"GLEIF no publica CUIT utilizable: {motivo}")

    cik = conn.execute(
        text(
            "SELECT id_value FROM identity_v1.identifier "
            " WHERE entity_key=:e AND id_type='CIK' AND is_authoritative "
            "   AND valid_to IS NULL"
        ),
        {"e": entity_key},
    ).scalar()
    if cik and not bridge_verificado(conn, ref("CIK", "SEC", cik), ref("LEI", "GLEIF", lei)):
        rid = open_review(
            conn, entity_key=entity_key,
            candidatos={"cik": cik, "lei": lei, "cuit": cuit, "via": motivo},
            reason=("falta puente CIK<->LEI verificado; la cadena "
                    "CIK -> LEI -> CUIT no esta demostrada (G5)"),
            evidence=source_record,
        )
        # idempotencia (F-023): la misma carencia no se registra dos veces
        aid = conn.execute(
            text(
                "SELECT assertion_id FROM identity_v1.assertion "
                " WHERE entity_key=:e AND left_ref=:l AND status='REVIEW_REQUIRED' "
                "   AND valid_to IS NULL"
            ),
            {"e": entity_key, "l": ref("CUIT", "AFIP", cuit)},
        ).scalar()
        if aid is None:
            aid = _insert_assertion(
                conn, subject_type="ENTITY_IDENTIFIER", entity_key=entity_key,
                left_ref=ref("CUIT", "AFIP", cuit), right_ref=None,
                relationship="BELONGS_TO", method="CROSS_REFERENCE", confidence="WEAK",
                status="REVIEW_REQUIRED",
                ev=Evidence("GLEIF", source_record, motivo, resolved_by),
                resolution_reason=f"review {rid}: sin puente CIK {cik} <-> LEI {lei}",
            )
        return Result(status="REVIEW_REQUIRED", assertion_id=aid, review_id=rid,
                      motivo=(f"GLEIF publica CUIT {cuit} para el LEI {lei}, pero "
                              f"nada demuestra que ese LEI corresponda al CIK {cik}. "
                              "Requiere resolucion humana."),
                      detalle={"cuit": cuit, "cik": cik, "lei": lei})

    return assert_identifier(
        conn, entity_key=entity_key, id_type="CUIT", id_namespace="AFIP",
        id_value=cuit, method="REGISTRY",
        evidence=Evidence("GLEIF", source_record, motivo, resolved_by,
                          facts=gleif_facts(gleif_record)),
    )


# =====================================================================
# Instrumentos y simbolos
# =====================================================================


def register_instrument(conn, *, entity_key: str, instrument_key: str,
                        instrument_type: str, exchange: str, currency: str,
                        assertion_id: int, ratio_underlying=None) -> str:
    """Registra un instrumento. `assertion_id` es OBLIGATORIO (F-021).

    Decir "este instrumento pertenece a esta entidad" es una afirmacion de
    identidad tan fuerte como cualquier otra: es la que conecta un precio con un
    emisor. Entra con fuente, cita y autor, o no entra.
    """
    require_entity(conn, entity_key)
    conn.execute(
        text(
            """
            INSERT INTO identity_v1.instrument
                (instrument_key, entity_key, instrument_type, exchange, currency,
                 ratio_underlying, assertion_id)
            VALUES (:k, :e, :t, :x, :c, :r, :a)
            """
        ),
        {"k": instrument_key, "e": entity_key, "t": instrument_type, "x": exchange,
         "c": currency, "r": ratio_underlying, "a": assertion_id},
    )
    return instrument_key


def link_symbol(conn, *, instrument_key: str, id_namespace: str, symbol: str) -> int:
    """Asocia un simbolo a un instrumento EXISTENTE.

    Un ticker no crea nada. COUR es Coursera en NASDAQ y otra cosa en otro
    mercado; el simbolo vive en su namespace y no cruza solo.
    """
    if not conn.execute(
        text("SELECT 1 FROM identity_v1.instrument WHERE instrument_key=:k"),
        {"k": instrument_key},
    ).scalar():
        raise UnknownEntity(
            f"Instrumento {instrument_key!r} no existe. Un simbolo no crea "
            "instrumentos ni entidades: primero se declara que se opera."
        )
    return conn.execute(
        text(
            "INSERT INTO identity_v1.instrument_symbol "
            "(instrument_key, id_namespace, symbol) VALUES (:k, :n, :s) "
            "RETURNING symbol_id"
        ),
        {"k": instrument_key, "n": id_namespace, "s": symbol},
    ).scalar()


# =====================================================================
# Resolucion humana
# =====================================================================


def resolve_review(conn, review_id: int, *, reviewer: str, decision: str,
                   reason: str, aplicar: dict | None = None) -> Result:
    """Cierra una review dejando trazabilidad completa.

    `aplicar` opcional: {'entity_key','id_type','id_namespace','id_value'} para
    materializar el identificador que el revisor decidio. La assertion resultante
    queda con method=HUMAN_DECISION, con revisor y con motivo: siempre se sabe
    quien lo decidio y con que argumento.
    """
    row = conn.execute(
        text("SELECT status, entity_key FROM identity_v1.review WHERE review_id=:r"),
        {"r": review_id},
    ).first()
    if row is None:
        raise IdentityError(f"Review {review_id} no existe")
    if row[0] != "OPEN":
        raise IdentityError(f"Review {review_id} ya esta en estado {row[0]}")

    res = Result(status=decision)
    if aplicar:
        # F-037: una decision humana que establece un identificador declara
        # quien y contra que decision, de forma estructurada.
        ev = Evidence("HUMAN", f"review:{review_id}", reason, reviewer, reason=reason,
                      facts={"reviewer": reviewer, "decision_ref": f"review:{review_id}"})
        res = assert_identifier(conn, method="HUMAN_DECISION", evidence=ev, **aplicar)

    aid = res.assertion_id or _insert_assertion(
        conn, subject_type="ENTITY_IDENTIFIER", entity_key=row[1],
        left_ref=None, right_ref=None, relationship=None, method="HUMAN_DECISION",
        confidence="STRONG", status=("REJECTED" if decision == "REJECTED" else "VERIFIED"),
        ev=Evidence("HUMAN", f"review:{review_id}", reason, reviewer, reason=reason),
        resolution_reason=reason,
    )
    conn.execute(
        text(
            """
            UPDATE identity_v1.review
               SET status=:st, reviewer=:rv, decision=:d, decision_reason=:why,
                   resolution_assertion_id=:aid, resolved_at=now()
             WHERE review_id=:r
            """
        ),
        {"st": ("RESOLVED" if decision != "REJECTED" else "REJECTED"), "rv": reviewer,
         "d": decision, "why": reason, "aid": aid, "r": review_id},
    )
    res.review_id = review_id
    res.assertion_id = aid
    return res


def ratificar_bridge(conn, *, cik: str, lei: str, reviewer: str,
                     evidencia_cik: str, evidencia_lei: str, motivo: str,
                     review_id: int | None = None) -> Result:
    """Una PERSONA ratifica un puente CIK<->LEI con evidencia de los dos lados.

    El unico camino por el que un puente llega a VERIFIED. Exige:
      - un revisor que no sea un proceso;
      - evidencia del lado CIK **y** del lado LEI, por separado.

    F-016 tenia dos defectos y este metodo cierra los dos: la firma la ponia un
    script, y la evidencia citaba unicamente el registro GLEIF — es decir, el
    lado LEI — de modo que no demostraba el puente, solo lo afirmaba.
    """
    _exigir_persona(reviewer, "Ratificar un puente CIK<->LEI")
    for nombre, texto in (("evidencia_cik", evidencia_cik), ("evidencia_lei", evidencia_lei)):
        if not texto or len(texto.strip()) < 30:
            raise IdentityError(
                f"{nombre} debe ser una cita verificable por un tercero, no {texto!r}. "
                "Un puente sin evidencia de AMBOS extremos no esta demostrado (G5)."
            )
    cik, lei = norm_cik(cik), norm_lei(lei)
    ev = Evidence(
        "HUMAN", f"ratificacion:{reviewer}",
        f"[CIK {cik}] {evidencia_cik.strip()}  ||  [LEI {lei}] {evidencia_lei.strip()}",
        reviewer, reason=motivo,
        facts={"reviewer": reviewer, "decision_ref": f"bridge:{cik}<->{lei}",
               "cik": cik, "lei": lei})
    res = assert_bridge(conn, left_ref_=ref("CIK", "SEC", cik),
                        right_ref_=ref("LEI", "GLEIF", lei),
                        method="HUMAN_DECISION", evidence=ev)
    if review_id is not None:
        conn.execute(
            text(
                """
                UPDATE identity_v1.review
                   SET status='RESOLVED', reviewer=:rv, decision='BRIDGE_RATIFICADO',
                       decision_reason=:why, resolution_assertion_id=:aid, resolved_at=now()
                 WHERE review_id=:r AND status='OPEN'
                """
            ),
            {"rv": reviewer, "why": motivo, "aid": res.assertion_id, "r": review_id},
        )
        res.review_id = review_id
    return res


def supersede_assertion(conn, assertion_id: int, *, nueva: int) -> None:
    """Cierra una assertion y la encadena a su sucesora.

    No borra ni reescribe: la historica queda legible y a partir de aca el
    trigger tg_assertion_inmutable impide modificarla.
    """
    conn.execute(
        text(
            "UPDATE identity_v1.assertion SET valid_to = now(), superseded_by = :n "
            " WHERE assertion_id = :a AND valid_to IS NULL"
        ),
        {"a": assertion_id, "n": nueva},
    )


# =====================================================================
# Lectura
# =====================================================================


def resolution_report(conn, entity_key: str) -> dict:
    row = conn.execute(
        text("SELECT * FROM identity_v1.v_entity_resolution WHERE entity_key=:k"),
        {"k": entity_key},
    ).mappings().first()
    return dict(row) if row else {}


def trace(conn, entity_key: str) -> list[dict]:
    """Todas las assertions de una entidad, para auditar la cadena completa."""
    return [dict(r) for r in conn.execute(
        text(
            "SELECT assertion_id, subject_type, left_ref, right_ref, method, "
            "       confidence, status, source_id, source_record, evidence, "
            "       resolved_by, valid_to "
            "  FROM identity_v1.assertion WHERE entity_key=:k "
            " ORDER BY assertion_id"
        ),
        {"k": entity_key},
    ).mappings()]
