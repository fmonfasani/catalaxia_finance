# -*- coding: utf-8 -*-
"""
_foco -- trabajar sobre UN papel en vez de sobre los 572
=========================================================
POR QUE
  s0..s9 procesan todo el universo de una pasada. Para entender por que a una
  empresa le sale un numero raro hay que reprocesar 572, que tarda y ademas
  mezcla su problema con el de las demas. Con foco se mira una sola y se ve.

DOS SIGNIFICADOS SEGUN EL SCRIPT, Y NO ES UN CAPRICHO
  Los scripts del pipeline se dividen en dos clases:

    RECONSTRUCTORES  s0 (cnv_estados_norm, mapa_entidades), s2 (ratios_cnv),
                     s4 (screener). Hacen DROP + CREATE de su tabla.
    MODIFICADORES    s3, s6, s7, s8, s9. Solo INSERT/UPDATE.

  En un modificador, el foco restringe las escrituras: se recalcula ese papel y
  los demas quedan como estaban. Es seguro y es lo que uno espera.

  En un reconstructor, el foco NO PUEDE escribir. Si s4 reconstruyera `screener`
  con un solo ticker, borraria los otros 571. Ahi el foco es de SOLO LECTURA: se
  muestra que saldria para ese papel y no se toca la base. Es diagnostico, no
  una corrida parcial.

  Esa asimetria esta puesta a proposito. Un `--ticker` que en un script filtra y
  en otro vacia la tabla seria una trampa esperando a alguien con prisa.

COMO SE USA
    python s8_calidad.py --ticker ALUA          # recalcula solo ALUA
    SCREENER_TICKER=ALUA python s8_calidad.py   # lo mismo, por entorno
    python s4_ensamblar.py --ticker ALUA        # solo muestra; no escribe

  Acepta varios: --ticker ALUA,MIRG,CELU

DESDE EL CODIGO
    from _foco import Foco
    foco = Foco()                          # lee sys.argv y el entorno
    ...
    cur.execute("SELECT ... FROM screener WHERE 1=1" + foco.sql("ticker"), foco.params())
    foco.exigir_lectura("s4_ensamblar")    # en los reconstructores, antes de escribir
"""
from __future__ import annotations
import os
import sys


class Foco:
    def __init__(self, argv=None):
        argv = list(sys.argv[1:] if argv is None else argv)
        crudo = os.environ.get("SCREENER_TICKER", "")
        for i, a in enumerate(argv):
            if a in ("--ticker", "--solo") and i + 1 < len(argv):
                crudo = argv[i + 1]
            elif a.startswith("--ticker=") or a.startswith("--solo="):
                crudo = a.split("=", 1)[1]
        self.tickers = [t.strip().upper() for t in crudo.split(",") if t.strip()]

    def __bool__(self):
        return bool(self.tickers)

    @property
    def activo(self):
        return bool(self.tickers)

    def sql(self, col="ticker", prefijo=" AND "):
        """Fragmento WHERE. Vacio si no hay foco, para no cambiar nada."""
        if not self.tickers:
            return ""
        marcas = ",".join("?" * len(self.tickers))
        return f"{prefijo}UPPER({col}) IN ({marcas})"

    def params(self):
        return list(self.tickers)

    def alcanza(self, ticker):
        """True si este ticker entra en el foco (o si no hay foco)."""
        return (not self.tickers) or (str(ticker or "").upper() in self.tickers)

    def anuncia(self):
        if self.tickers:
            print(f"  FOCO: solo {', '.join(self.tickers)} "
                  f"(los demas papeles no se tocan)")

    def exigir_lectura(self, script):
        """En un reconstructor: si hay foco, se informa y NO se escribe.

        Devuelve True cuando hay foco, para que el script corte antes de la
        parte destructiva. La alternativa -- reconstruir con un solo ticker --
        vaciaria la tabla para los otros 571.
        """
        if not self.tickers:
            return False
        print(f"\n  {script} RECONSTRUYE su tabla entera, asi que con --ticker")
        print(f"  funciona en modo SOLO LECTURA: se muestra que saldria para")
        print(f"  {', '.join(self.tickers)} y no se escribe nada.")
        print(f"  Para reconstruir de verdad, correlo sin --ticker.")
        return True
