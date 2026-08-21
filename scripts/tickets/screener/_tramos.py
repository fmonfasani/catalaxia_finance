# -*- coding: utf-8 -*-
"""
_tramos -- los errores de unidad vienen en BLOQUES, no de a uno
================================================================
HALLAZGO QUE MOTIVA ESTO
  GCLA tiene 444 hechos sospechosos. Mirados de a uno parecen 444 problemas;
  mirados por periodo son 13 documentos con TODOS sus ~35 conceptos marcados; y
  mirados en el tiempo son un TRAMO CONTIGUO de 2020-06 a 2023-09.

  En ese tramo el documento declara '$' y da facturaciones de 102 a 224 dolares
  al año. Desde 2023-12, con LA MISMA declaracion '$', los numeros pasan a ser
  correctos (217 millones). La declaracion no cambio; los numeros si.

  Eso no es ruido: es alguien que cargo los balances con otro criterio durante
  tres años y lo mantuvo. Por eso conviene tratarlo como un bloque con una
  decision, y no como 444 decisiones sueltas.

POR QUE EL TRAMO ES MEJOR EVIDENCIA QUE LA FILA
  Una fila fuera de banda puede ser una empresa rara, un periodo atipico o un
  error. Trece periodos seguidos, con los 35 conceptos, todos desviados por el
  MISMO factor, no puede ser otra cosa que la unidad.

  Y el criterio se vuelve exigible: si el desvio no es consistente dentro del
  tramo, no es un problema de unidad y el tramo no se propone.

Solo LECTURA. Este modulo detecta y propone; no escribe.
"""
from __future__ import annotations
import collections
import statistics


def desvio_por_periodo(con, cuit, min_conceptos=5):
    """[(period_end, desvio_mediano, n_marcados, n_total)] ordenado por fecha."""
    filas = con.execute(
        """SELECT period_end,
                  SUM(CASE WHEN usd_clase IN ('unidad','no_unidad') THEN 1 ELSE 0 END),
                  COUNT(*),
                  GROUP_CONCAT(usd_desvio)
           FROM cnv_estados_norm
           WHERE cuit=? AND valor_usd IS NOT NULL
           GROUP BY period_end ORDER BY period_end""", (cuit,)).fetchall()
    out = []
    for pe, marc, tot, desv in filas:
        if tot < min_conceptos:
            continue
        ds = [float(x) for x in (desv or "").split(",") if x not in ("", "None")]
        out.append((pe, statistics.median(ds) if ds else 0.0, marc, tot))
    return out


def detectar(con, cuit, min_cobertura=0.6, min_periodos=2, tol_consistencia=0.75,
             banda=None):
    """Tramos contiguos de periodos con la unidad desviada.

    min_cobertura     fraccion de conceptos marcados para considerar al periodo
                      afectado. Con 0,6 se exige que la MAYORIA del documento
                      este fuera, no un concepto suelto.
    min_periodos      un tramo de un solo periodo no es un tramo: se deja para
                      la deteccion fila por fila.
    tol_consistencia  fraccion MINIMA de periodos del tramo que tienen que
                      implicar la MISMA potencia de 1.000.

                      OJO con la medida: la primera version miraba la dispersion
                      de los desvios crudos y descartaba tramos buenos. El desvio
                      se mide contra el BORDE de la banda, asi que una empresa
                      cuya facturacion varia queda a distancias distintas del
                      borde aunque el error de escala sea el mismo. GCLA
                      2021-09..2023-09 -- nueve periodos, todos con factor 1.000
                      -- se descartaba por "dispersion 1,2".

                      Lo que importa no es que los desvios sean iguales, sino que
                      todos redondeen a la misma potencia.
    banda             (p5, p95) en log10 de USD. Si se pasa, se COMPRUEBA que el
                      factor propuesto devuelva los valores a la banda, en vez de
                      confiar en el redondeo.

                      Hace falta: FIPL 2025-12..2026-03 tiene Revenue de 12 y 20
                      pesos, desvio -6,2, y el redondeo propone 1e6. Pero
                      12 x 1e6 = 12 millones de pesos = 7.922 USD, y la banda
                      arranca en 111.672. El factor "cierra" en el redondeo y no
                      en la cuenta: ese caso no es de unidad y no debe proponerse.
    """
    per = desvio_por_periodo(con, cuit)
    afect = [(pe, d) for pe, d, m, t in per if t and (m / t) >= min_cobertura]
    if not afect:
        return []
    idx = {pe: i for i, (pe, *_ ) in enumerate(per)}
    tramos, actual = [], []
    for pe, d in afect:
        if actual and idx[pe] == idx[actual[-1][0]] + 1:
            actual.append((pe, d))
        else:
            if len(actual) >= min_periodos:
                tramos.append(actual)
            actual = [(pe, d)]
    if len(actual) >= min_periodos:
        tramos.append(actual)

    out = []
    for t in tramos:
        ds = [d for _, d in t]
        med = statistics.median(ds)
        # la potencia de 1.000 que implica CADA periodo, no el promedio
        ks = [round(abs(d) / 3.0) * (1 if d < 0 else -1) for d in ds]
        k_mayor = collections.Counter(ks).most_common(1)[0]
        acuerdo = k_mayor[1] / len(ks)
        k = k_mayor[0]
        factor = 1000.0 ** k
        ok = acuerdo >= tol_consistencia and k != 0
        # COMPROBACION, no redondeo: el corregido tiene que caer en la banda.
        entra = None
        if ok and banda:
            p5, p95 = banda
            corr = [d + (p5 if d < 0 else p95) + 3.0 * k for d in ds]
            entra = sum(1 for x in corr if p5 - 0.5 <= x <= p95 + 0.5) / len(corr)
            ok = ok and entra >= tol_consistencia
        out.append({
            "desde": t[0][0], "hasta": t[-1][0], "periodos": len(t),
            "desvio_mediano": round(med, 2),
            "dispersion": round((max(ds) - min(ds)) if len(ds) > 1 else 0.0, 2),
            "acuerdo": round(acuerdo, 2),
            "entra_en_banda": None if entra is None else round(entra, 2),
            "consistente": ok,
            "factor": factor,
        })
    return out
