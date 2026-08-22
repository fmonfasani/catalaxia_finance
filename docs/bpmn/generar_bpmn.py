# -*- coding: utf-8 -*-
"""
Genera los diagramas BPMN 2.0 del pipeline, importables en Bizagi Modeler.

POR QUE GENERADO Y NO DIBUJADO A MANO
  El pipeline cambia -- esta semana se agregaron s1_bimoneda, s7c_cagr y s7d.
  Un .bpmn dibujado a mano queda desactualizado en la primera modificacion y
  nadie se entera; uno generado se vuelve a emitir y refleja el codigo real.

  La lista de tareas sale del orden efectivo de run_all.py, no de memoria.

SALIDA
  docs/bpmn/01-pipeline-etl.bpmn        el ETL completo, por capas
  docs/bpmn/02-auditor-mensual.bpmn     el auditor y su punto de decision
  docs/bpmn/03-actualizador-diario.bpmn el ciclo diario

USO
  python docs/bpmn/generar_bpmn.py
  Despues: Bizagi Modeler -> Archivo -> Importar -> BPMN 2.0 XML
"""
from __future__ import annotations
from pathlib import Path
from xml.sax.saxutils import escape

SALIDA = Path(__file__).resolve().parent

# ancho/alto de cada figura y separaciones del layout automatico
W_TASK, H_TASK = 150, 70
W_GW, H_GW = 50, 50
W_EV, H_EV = 36, 36
DX, LANE_H, X0, Y0 = 200, 130, 60, 60


class Proceso:
    """Arma un BPMN de un solo pool con carriles, en disposicion horizontal."""

    def __init__(self, id_, nombre, carriles):
        self.id, self.nombre = id_, nombre
        self.carriles = carriles          # [(id, nombre)]
        self.nodos = []                   # (id, tipo, nombre, carril, col)
        self.flujos = []                  # (id, origen, destino, etiqueta)
        self._n = 0

    def nodo(self, tipo, nombre, carril, col):
        self._n += 1
        i = f"{self.id}_n{self._n}"
        self.nodos.append((i, tipo, nombre, carril, col))
        return i

    def flujo(self, a, b, etiqueta=None):
        i = f"{self.id}_f{len(self.flujos) + 1}"
        self.flujos.append((i, a, b, etiqueta))
        return i

    # -------------------------------------------------------------- layout
    def _geom(self):
        fila = {c[0]: k for k, c in enumerate(self.carriles)}
        g = {}
        for i, tipo, _, carril, col in self.nodos:
            w, h = ((W_EV, H_EV) if tipo.endswith("Event")
                    else (W_GW, H_GW) if "Gateway" in tipo else (W_TASK, H_TASK))
            cx = X0 + col * DX + W_TASK / 2
            cy = Y0 + fila[carril] * LANE_H + LANE_H / 2
            g[i] = (cx - w / 2, cy - h / 2, w, h)
        return g

    def xml(self):
        g = self._geom()
        ancho = max((x + w for x, _, w, _ in g.values()), default=800) + 80
        L = []
        A = L.append
        A('<?xml version="1.0" encoding="UTF-8"?>')
        A('<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'
          ' xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"'
          ' xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"'
          ' xmlns:di="http://www.omg.org/spec/DD/20100524/DI"'
          ' targetNamespace="http://catalaxia/bpmn" id="defs_%s">' % self.id)
        A(f'  <bpmn:collaboration id="col_{self.id}">')
        A(f'    <bpmn:participant id="pool_{self.id}" name="{escape(self.nombre)}"'
          f' processRef="{self.id}"/>')
        A('  </bpmn:collaboration>')
        A(f'  <bpmn:process id="{self.id}" isExecutable="false">')
        A('    <bpmn:laneSet>')
        for cid, cnom in self.carriles:
            A(f'      <bpmn:lane id="{cid}" name="{escape(cnom)}">')
            for i, _, _, carril, _ in self.nodos:
                if carril == cid:
                    A(f'        <bpmn:flowNodeRef>{i}</bpmn:flowNodeRef>')
            A('      </bpmn:lane>')
        A('    </bpmn:laneSet>')
        for i, tipo, nombre, _, _ in self.nodos:
            ent = [f for f in self.flujos if f[2] == i]
            sal = [f for f in self.flujos if f[1] == i]
            A(f'    <bpmn:{tipo} id="{i}" name="{escape(nombre)}">')
            for f in ent:
                A(f'      <bpmn:incoming>{f[0]}</bpmn:incoming>')
            for f in sal:
                A(f'      <bpmn:outgoing>{f[0]}</bpmn:outgoing>')
            A(f'    </bpmn:{tipo}>')
        for fid, a, b, et in self.flujos:
            nm = f' name="{escape(et)}"' if et else ""
            A(f'    <bpmn:sequenceFlow id="{fid}"{nm} sourceRef="{a}" targetRef="{b}"/>')
        A('  </bpmn:process>')
        # ----------------------------------------------------------- diagrama
        A(f'  <bpmndi:BPMNDiagram id="dia_{self.id}">')
        A(f'    <bpmndi:BPMNPlane id="pla_{self.id}" bpmnElement="col_{self.id}">')
        alto = len(self.carriles) * LANE_H
        A(f'      <bpmndi:BPMNShape id="sh_pool_{self.id}" bpmnElement="pool_{self.id}"'
          f' isHorizontal="true">')
        A(f'        <dc:Bounds x="20" y="{Y0 - 10}" width="{ancho}" height="{alto}"/>')
        A('      </bpmndi:BPMNShape>')
        for k, (cid, _) in enumerate(self.carriles):
            A(f'      <bpmndi:BPMNShape id="sh_{cid}" bpmnElement="{cid}"'
              f' isHorizontal="true">')
            A(f'        <dc:Bounds x="50" y="{Y0 - 10 + k * LANE_H}"'
              f' width="{ancho - 30}" height="{LANE_H}"/>')
            A('      </bpmndi:BPMNShape>')
        for i, _, _, _, _ in self.nodos:
            x, y, w, h = g[i]
            A(f'      <bpmndi:BPMNShape id="sh_{i}" bpmnElement="{i}">')
            A(f'        <dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}"/>')
            A('      </bpmndi:BPMNShape>')
        for fid, a, b, _ in self.flujos:
            xa, ya, wa, ha = g[a]
            xb, yb, wb, hb = g[b]
            A(f'      <bpmndi:BPMNEdge id="ed_{fid}" bpmnElement="{fid}">')
            A(f'        <di:waypoint x="{xa + wa:.0f}" y="{ya + ha / 2:.0f}"/>')
            if abs((ya + ha / 2) - (yb + hb / 2)) > 5:
                A(f'        <di:waypoint x="{xb + wb / 2:.0f}" y="{ya + ha / 2:.0f}"/>')
            A(f'        <di:waypoint x="{xb:.0f}" y="{yb + hb / 2:.0f}"/>')
            A('      </bpmndi:BPMNEdge>')
        A('    </bpmndi:BPMNPlane>')
        A('  </bpmndi:BPMNDiagram>')
        A('</bpmn:definitions>')
        return "\n".join(L)


# ============================================================ 1. ETL COMPLETO
def etl():
    p = Proceso("etl", "Pipeline ETL - Catalaxia", [
        ("l_ext", "1 Extraccion"),
        ("l_nor", "2 Normalizacion e identidad"),
        ("l_val", "3 Unidad, moneda y validacion"),
        ("l_der", "4 Derivacion"),
        ("l_pub", "5 Publicacion"),
    ])
    ini = p.nodo("startEvent", "Corrida del pipeline", "l_ext", 0)
    # --- extraccion
    e1 = p.nodo("task", "Bajar SEC EDGAR\n(construir_base)", "l_ext", 1)
    gw1 = p.nodo("exclusiveGateway", "Presento algo nuevo?", "l_ext", 2)
    e2 = p.nodo("task", "Bajar CNV\n(job1..job8)", "l_ext", 3)
    e3 = p.nodo("task", "Bajar MEP\n(dolarito)", "l_ext", 4)
    # --- normalizacion
    n1 = p.nodo("task", "s0 Unir fuentes\ny resolver identidad", "l_nor", 5)
    n2 = p.nodo("task", "Calendario fiscal\n(s2a)", "l_nor", 6)
    # --- validacion
    v1 = p.nodo("task", "s1 Bimoneda\n+ banda por concepto", "l_val", 7)
    v2 = p.nodo("task", "Coherencia interna", "l_val", 8)
    gw2 = p.nodo("exclusiveGateway", "Certifica?", "l_val", 9)
    v3 = p.nodo("task", "Marcar y declarar\nlo que no cierra", "l_val", 10)
    # --- derivacion
    d1 = p.nodo("task", "s2 Ratios CNV\n(TTM)", "l_der", 11)
    d2 = p.nodo("task", "s4/s7 Ensamblar\ny unificar", "l_der", 12)
    d3 = p.nodo("task", "s7b PER\ns7c CAGR USD\ns7d dos fuentes", "l_der", 13)
    # --- publicacion
    b1 = p.nodo("task", "s8 Calidad\ns9 Guards", "l_pub", 14)
    b2 = p.nodo("task", "Publicar\nscreener / screener_v2", "l_pub", 15)
    fin = p.nodo("endEvent", "Datos publicados", "l_pub", 16)

    for a, b, et in [(ini, e1, None), (e1, gw1, None), (gw1, e2, "si"),
                     (gw1, e3, "no, ya esta al dia"), (e2, e3, None),
                     (e3, n1, None), (n1, n2, None), (n2, v1, None),
                     (v1, v2, None), (v2, gw2, None), (gw2, v3, "hay dudas"),
                     (gw2, d1, "todo cierra"), (v3, d1, None), (d1, d2, None),
                     (d2, d3, None), (d3, b1, None), (b1, b2, None),
                     (b2, fin, None)]:
        p.flujo(a, b, et)
    return p


# ========================================================= 2. AUDITOR MENSUAL
def auditor():
    p = Proceso("aud", "Auditor general (mensual)", [
        ("a_med", "Medicion"),
        ("a_cla", "Clasificacion"),
        ("a_dec", "Decision humana"),
    ])
    ini = p.nodo("startEvent", "Primer dia del mes", "a_med", 0)
    m1 = p.nodo("task", "Cobertura\ncontra la expectativa", "a_med", 1)
    m2 = p.nodo("task", "Completitud\nde periodos", "a_med", 2)
    m3 = p.nodo("task", "Frescura\ny consistencia", "a_med", 3)
    m4 = p.nodo("task", "Comparar contra\nla corrida anterior", "a_med", 4)
    c1 = p.nodo("task", "Clasificar cada hueco\npor CAUSA", "a_cla", 5)
    gw = p.nodo("exclusiveGateway", "De que tipo?", "a_cla", 6)
    c2 = p.nodo("task", "Reprocesar el crudo\n(sin red)", "a_cla", 7)
    c3 = p.nodo("task", "Arreglar identidad\n(sin red)", "a_cla", 7)
    c4 = p.nodo("task", "Proponer descarga\nquirurgica", "a_cla", 8)
    d1 = p.nodo("userTask", "Revisar el informe\ny autorizar", "a_dec", 9)
    fin = p.nodo("endEvent", "Auditoria cerrada", "a_dec", 10)

    for a, b, et in [(ini, m1, None), (m1, m2, None), (m2, m3, None),
                     (m3, m4, None), (m4, c1, None), (c1, gw, None),
                     (gw, c2, "en crudo sin parsear"), (gw, c3, "no asociado"),
                     (gw, c4, "no descargado"), (c2, d1, None), (c3, d1, None),
                     (c4, d1, None), (d1, fin, None)]:
        p.flujo(a, b, et)
    return p


# ===================================================== 3. ACTUALIZADOR DIARIO
def actualizador():
    p = Proceso("act", "Actualizador (diario)", [
        ("d_det", "Deteccion"),
        ("d_baj", "Descarga"),
        ("d_pro", "Proceso"),
    ])
    ini = p.nodo("startEvent", "Todos los dias", "d_det", 0)
    t1 = p.nodo("task", "Leer indice de\npresentaciones", "d_det", 1)
    gw = p.nodo("exclusiveGateway", "Hay algo nuevo?", "d_det", 2)
    fin0 = p.nodo("endEvent", "Nada que hacer", "d_det", 3)
    b1 = p.nodo("task", "Bajar SOLO esa\npresentacion", "d_baj", 3)
    b2 = p.nodo("task", "Registrar en\ningesta_log", "d_baj", 4)
    p1 = p.nodo("task", "Reprocesar SOLO\nlo afectado", "d_pro", 5)
    p2 = p.nodo("task", "Certificar que\nno rompio nada", "d_pro", 6)
    gw2 = p.nodo("exclusiveGateway", "Certifica?", "d_pro", 7)
    p3 = p.nodo("task", "Revertir\ny avisar", "d_pro", 8)
    fin = p.nodo("endEvent", "Base actualizada", "d_pro", 9)

    for a, b, et in [(ini, t1, None), (t1, gw, None), (gw, fin0, "no"),
                     (gw, b1, "si"), (b1, b2, None), (b2, p1, None),
                     (p1, p2, None), (p2, gw2, None), (gw2, p3, "no"),
                     (gw2, fin, "si"), (p3, fin, None)]:
        p.flujo(a, b, et)
    return p


if __name__ == "__main__":
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, proc in (("01-pipeline-etl", etl()),
                         ("02-auditor-mensual", auditor()),
                         ("03-actualizador-diario", actualizador())):
        f = SALIDA / f"{nombre}.bpmn"
        f.write_text(proc.xml(), encoding="utf-8")
        print(f"   {f.name:<30}{len(proc.nodos):>3} nodos, {len(proc.flujos):>3} flujos")
    print("\n   Bizagi Modeler -> Archivo -> Importar -> BPMN 2.0 XML")
