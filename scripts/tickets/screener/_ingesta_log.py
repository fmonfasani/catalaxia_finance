# -*- coding: utf-8 -*-
"""
_ingesta_log -- una fila por DESCARGA, no por empresa
======================================================
POR QUE HACE FALTA
  Hoy la unica huella de una descarga es `empresas.fecha_facts`: una marca por
  empresa que se pisa en cada corrida. Con eso no se puede responder ninguna de
  estas preguntas:

      - esta empresa no tiene datos porque no existen, o porque la bajada fallo?
      - cuando se intento por ultima vez, y que respondio?
      - la ultima descarga trajo algo distinto, o el mismo archivo de siempre?
      - cuantos hechos aporto realmente?

  La primera es la que mas cuesta. Un 404 -- el dato no existe -- y un 429 --
  nos limitaron y hay que reintentar -- hoy se ven exactamente igual: como un
  dato ausente. Y llevan a acciones opuestas: uno se declara, el otro se
  reintenta.

  Es el mismo patron que aparecio en toda la capa de Transform: un silencio no
  se distingue de un cero si nadie lo registra.

QUE APORTA CADA CAMPO

  respuesta     200 / 404 / 429 / 0 (excepcion de red). Separa "no existe" de
                "no pude". Sin esto, un mes de bloqueos por limite de tasa
                parece un mes sin novedades.

  hash          sha256 del contenido. Si coincide con el de la descarga
                anterior, el emisor no publico nada nuevo y NO hace falta
                reprocesar. Convierte "bajar de nuevo" en una operacion barata.

  filas_nuevas  cuantos hechos entraron DE VERDAD. Una descarga exitosa que
                aporta cero filas es un sintoma -- el archivo llego pero el
                parser no lo entendio -- y hoy se ve como un exito.

  bytes         una caida brusca de tamaño frente a la descarga anterior suele
                ser una pagina de error servida con codigo 200.

NO ESCRIBE POR SI SOLO
  Este modulo da la tabla y la funcion de registro. Quien descarga la llama.
  Mantenerlo separado permite que la CNV, EDGAR, dolarito y yfinance usen el
  mismo registro sin acoplarse entre si.
"""
from __future__ import annotations
import datetime as dt
import hashlib

DDL = """
CREATE TABLE IF NOT EXISTS ingesta_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente        TEXT NOT NULL,      -- sec_edgar | cnv_aif2 | dolarito | yfinance
    entidad       TEXT,               -- cik, cuit o ticker, segun la fuente
    recurso       TEXT,               -- que se pidio: companyfacts, submissions, 6-K...
    url           TEXT,
    solicitado_at TEXT NOT NULL,
    duracion_ms   INTEGER,
    respuesta     INTEGER,            -- 200 / 404 / 429 / 0 = excepcion
    bytes         INTEGER,
    hash          TEXT,               -- sha256 del contenido
    sin_cambios   INTEGER,            -- 1 si el hash es igual al de la vez anterior
    filas_nuevas  INTEGER,
    motivo        TEXT                -- por que se bajo, o por que fallo
);
CREATE INDEX IF NOT EXISTS ix_ingesta_entidad ON ingesta_log(fuente, entidad);
CREATE INDEX IF NOT EXISTS ix_ingesta_fecha   ON ingesta_log(solicitado_at);
"""


def crear(con):
    con.executescript(DDL)


def sha256(contenido):
    if contenido is None:
        return None
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8", errors="ignore")
    return hashlib.sha256(contenido).hexdigest()


def hash_anterior(con, fuente, entidad, recurso=None):
    q = ("SELECT hash FROM ingesta_log WHERE fuente=? AND entidad=? "
         "AND hash IS NOT NULL")
    p = [fuente, entidad]
    if recurso:
        q += " AND recurso=?"
        p.append(recurso)
    r = con.execute(q + " ORDER BY id DESC LIMIT 1", p).fetchone()
    return r[0] if r else None


def registrar(con, fuente, entidad, *, recurso=None, url=None, respuesta=None,
              contenido=None, bytes_=None, duracion_ms=None, filas_nuevas=None,
              motivo=None, commit=True):
    """Deja constancia de UN intento de descarga. Devuelve (id, sin_cambios)."""
    h = sha256(contenido)
    prev = hash_anterior(con, fuente, entidad, recurso) if h else None
    sin_cambios = 1 if (h and prev and h == prev) else 0
    if bytes_ is None and contenido is not None:
        bytes_ = len(contenido if isinstance(contenido, (bytes, bytearray))
                     else str(contenido).encode("utf-8", errors="ignore"))
    cur = con.execute(
        """INSERT INTO ingesta_log
           (fuente, entidad, recurso, url, solicitado_at, duracion_ms,
            respuesta, bytes, hash, sin_cambios, filas_nuevas, motivo)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (fuente, str(entidad) if entidad is not None else None, recurso, url,
         dt.datetime.now().isoformat(timespec="seconds"), duracion_ms,
         respuesta, bytes_, h, sin_cambios, filas_nuevas, motivo))
    if commit:
        con.commit()
    return cur.lastrowid, bool(sin_cambios)


def resumen(con, desde=None):
    """Como salio la ultima tanda. Para que una corrida termine diciendo algo."""
    q = "SELECT respuesta, COUNT(*), SUM(COALESCE(filas_nuevas,0)), SUM(sin_cambios) FROM ingesta_log"
    p = []
    if desde:
        q += " WHERE solicitado_at >= ?"
        p.append(desde)
    return con.execute(q + " GROUP BY respuesta ORDER BY 2 DESC", p).fetchall()


def sin_registro(con, fuente, entidades):
    """Entidades que nunca se intentaron. Un hueco sin intento no es un fallo:
    es algo que no se pidio, y se arregla pidiendolo."""
    ya = {r[0] for r in con.execute(
        "SELECT DISTINCT entidad FROM ingesta_log WHERE fuente=?", (fuente,))}
    return [e for e in entidades if str(e) not in ya]
