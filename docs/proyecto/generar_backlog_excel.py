# -*- coding: utf-8 -*-
"""Backlog Catalaxia -> Excel: una hoja por sprint + hoja de progreso general.
34 tareas / 108 pts / 4 sprints. Estilo webshooks. Con dropdowns de estado/avance,
barras de progreso y formulas vivas (el progreso se actualiza al marcar Estado/Avance).

    python docs/proyecto/generar_backlog_excel.py  -> docs/proyecto/Backlog_Catalaxia_Sprints.xlsx
"""
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import DataBarRule, CellIsRule
from openpyxl.utils import get_column_letter

# ---- paleta webshooks ----
NAVY="1A2744"; BLUE="3B82F6"; BLUED="1A4D8F"; ORANGE="F5821F"; GREEN="43A047"
LB3="F4F8FE"; LB="DCEAFF"; GRID="D6E2F2"; BODY="3A4458"; GRAYL="6B7589"; WHITE="FFFFFF"
FONT="Calibri"
ACC={"Federico":BLUED,"Mateo":BLUE,"Joaquín":GREEN,"Aldana":ORANGE}
ROLES={"Federico":"Tech Lead · Infra · Datos · QA","Mateo":"Backend · Jobs",
       "Joaquín":"Frontend Screener","Aldana":"Frontend Detalle"}

def F(sz=10,b=False,color=BODY,it=False): return Font(name=FONT,size=sz,bold=b,color=color,italic=it)
def fill(c): return PatternFill("solid",fgColor=c)
def side(): return Side(style="thin",color=GRID)
BORDER=Border(left=side(),right=side(),top=side(),bottom=side())
CEN=Alignment(horizontal="center",vertical="center",wrap_text=True)
LEFT=Alignment(horizontal="left",vertical="center",wrap_text=True)

# ---- backlog (Epic Link, Assignee, Sprint, Story Points, Priority) ----
B=[
 # Sprint 1
 ("S1","Definir contrato de API + entregar mocks (día 1)","Backend","Federico","Muy alta",3),
 ("S1","Esquema PostgreSQL (empresas + instrumentos)","Datos","Federico","Alta",3),
 ("S1","Migrar/cargar 572 empresas + 733 instrumentos a Postgres","Datos","Federico","Alta",5),
 ("S1","Configurar Postgres en la VPS + backups diarios","Infra","Federico","Alta",3),
 ("S1","Deploy API base + HTTPS (nginx/certbot) + CORS","Infra","Federico","Alta",5),
 ("S1","Scaffold FastAPI + conexión Postgres async","Backend","Mateo","Alta",3),
 ("S1","GET /empresas + GET /cobertura + /health","Backend","Mateo","Alta",5),
 ("S1","Scaffold Next.js + layout (sidebar/topbar)","Screener","Joaquín","Alta",3),
 ("S1","Tabla screener contra mocks del contrato","Screener","Joaquín","Media",3),
 ("S1","Base del front + ruta detalle contra mocks","Detalle","Aldana","Media",3),
 ("S1","Componentes base (cards, chips, tabla)","Detalle","Aldana","Media",2),
 # Sprint 2
 ("S2","GET /empresas/{id} (fundamentales + instrumentos anidados)","Backend","Mateo","Alta",5),
 ("S2","GET /instrumentos con filtros + paginación","Backend","Mateo","Media",3),
 ("S2","Verificar 733 instrumentos + dividendos ADR en Postgres","Datos","Federico","Media",3),
 ("S2","Asistir a frontends a consumir la VPS (CORS/staging)","Infra","Federico","Alta",2),
 ("S2","Screener contra API real + toggle ARS/USD","Screener","Joaquín","Alta",5),
 ("S2","Sorting + paginación server-side (screener)","Screener","Joaquín","Media",2),
 ("S2","Detalle contra API real + panel de instrumentos","Detalle","Aldana","Alta",5),
 # Sprint 3
 ("S3","Filtros compuestos en /empresas (per, roe, solo_limpias)","Backend","Mateo","Alta",3),
 ("S3","POST /jobs/{tipo} + GET /jobs/{id}/status","Jobs","Mateo","Media",3),
 ("S3","Scheduler de jobs en la VPS (precios/financials)","Jobs","Federico","Media",3),
 ("S3","Filtros min/max + filtro por flag de calidad","Screener","Joaquín","Alta",3),
 ("S3","Export CSV del screener","Screener","Joaquín","Media",2),
 ("S3","Panel de jobs en vivo (polling)","Screener","Joaquín","Media",3),
 ("S3","Dividendos ADR + yield (detalle)","Detalle","Aldana","Media",3),
 ("S3","Vista CEDEAR (precio con ratio de conversión)","Detalle","Aldana","Alta",3),
 ("S3","Comparador (mismo universo) + chips de provenance","Detalle","Aldana","Media",3),
 # Sprint 4
 ("S4","Tests de endpoints + manejo de errores","Backend","Mateo","Alta",3),
 ("S4","openapi.json documentado","Backend","Mateo","Media",2),
 ("S4","Hardening infra + backups verificados + deploy prod","Infra","Federico","Alta",3),
 ("S4","QA de integración end-to-end (checklist)","QA","Federico","Muy alta",3),
 ("S4","Estados vacío/loading/error + responsive (screener)","Screener","Joaquín","Alta",3),
 ("S4","Estados + responsive + disclaimers (detalle)","Detalle","Aldana","Alta",3),
 ("S4","Walkthrough de entrega + README de operación","QA","Federico","Alta",2),
]
SPRINTS=[("S1","Sprint 1 · Semana 1","Fundamentos navegables: infra + API base + fronts contra mocks del contrato."),
         ("S2","Sprint 2 · Semana 2","Datos reales conectados: front consume la API (572 empresas, doble moneda) + panel de instrumentos."),
         ("S3","Sprint 3 · Semana 3","Funcionalidad completa: filtros, export, jobs en vivo, CEDEAR/ADR y comparador."),
         ("S4","Sprint 4 · Semana 4","QA + entrega: tests, hardening, estados/responsive, walkthrough + deploy productivo.")]
HEADERS=["ID","Tarea","Épica","Responsable","Prioridad","Puntos","Avance","Pts ✓","Estado","Notas"]
WIDTHS=[9,52,17,15,11,9,10,9,14,26]
# columnas: A..J
COL={h:get_column_letter(i+1) for i,h in enumerate(HEADERS)}

ESTADOS='"Pendiente,En curso,En review,Hecho,Bloqueado"'
AVANCES='"0,0.25,0.5,0.75,1"'

wb=Workbook()

def style_header_row(ws,row):
    for i,h in enumerate(HEADERS,1):
        c=ws.cell(row=row,column=i,value=h); c.fill=fill(NAVY); c.font=F(10,True,WHITE)
        c.alignment=CEN; c.border=BORDER
    ws.row_dimensions[row].height=22

def sprint_sheet(sid,title,obj):
    tasks=[t for t in B if t[0]==sid]
    ws=wb.create_sheet(title.split(" · ")[0])
    for i,w in enumerate(WIDTHS,1): ws.column_dimensions[get_column_letter(i)].width=w
    # banner
    ws.merge_cells(f"A1:{COL['Notas']}1")
    b=ws["A1"]; b.value=f"{title.upper()}   —   {sum(t[5] for t in tasks)} pts · {len(tasks)} tareas"
    b.fill=fill(NAVY); b.font=F(14,True,WHITE); b.alignment=Alignment(horizontal="left",vertical="center",indent=1)
    ws.row_dimensions[1].height=30
    ws.merge_cells(f"A2:{COL['Notas']}2")
    o=ws["A2"]; o.value="Objetivo: "+obj; o.fill=fill(LB3); o.font=F(10,False,GRAYL,it=True)
    o.alignment=Alignment(horizontal="left",vertical="center",indent=1); ws.row_dimensions[2].height=20
    style_header_row(ws,3)
    r0=4
    for k,(sid2,tarea,epica,resp,prio,pts) in enumerate(tasks):
        r=r0+k
        vals=[f"{sid}-{k+1:02d}",tarea,epica,resp,prio,pts,0,None,"Pendiente",""]
        for i,v in enumerate(vals,1):
            c=ws.cell(row=r,column=i,value=v); c.border=BORDER; c.font=F(9.5)
            c.alignment=LEFT if i in (2,10) else CEN
            if i%2==0: pass
        # zebra
        if k%2==0:
            for i in range(1,11): ws.cell(row=r,column=i).fill=fill(LB3)
        # responsable coloreado
        rc=ws.cell(row=r,column=4); rc.font=F(9.5,True,ACC.get(resp,BODY))
        # puntos bold
        ws.cell(row=r,column=6).font=F(10,True,NAVY)
        # avance formato %
        ws.cell(row=r,column=7).number_format="0%"
        # Pts ✓ = Puntos*Avance
        ws.cell(row=r,column=8,value=f"=F{r}*G{r}").number_format="0.0"
        ws.cell(row=r,column=8).font=F(9.5,True,GREEN); ws.cell(row=r,column=8).alignment=CEN; ws.cell(row=r,column=8).border=BORDER
        ws.row_dimensions[r].height=30
    rt=r0+len(tasks)
    # fila total
    ws.cell(row=rt,column=1,value="TOTAL").font=F(10,True,WHITE)
    for i in range(1,11):
        cc=ws.cell(row=rt,column=i); cc.fill=fill(NAVY); cc.border=BORDER; cc.alignment=CEN
        if cc.font.color is None or cc.value is None: cc.font=F(10,True,WHITE)
    ws.cell(row=rt,column=6,value=f"=SUM(F{r0}:F{rt-1})").font=F(11,True,WHITE)
    ws.cell(row=rt,column=8,value=f"=SUM(H{r0}:H{rt-1})").font=F(11,True,WHITE); ws.cell(row=rt,column=8).number_format="0.0"
    ws.cell(row=rt,column=9,value=f"=IF(F{rt}=0,0,H{rt}/F{rt})").font=F(11,True,ORANGE)
    ws.cell(row=rt,column=9).number_format="0%"
    ws.row_dimensions[rt].height=24
    # data validation
    dvE=DataValidation(type="list",formula1=ESTADOS,allow_blank=True); ws.add_data_validation(dvE)
    dvE.add(f"I{r0}:I{rt-1}")
    dvA=DataValidation(type="list",formula1=AVANCES,allow_blank=True); ws.add_data_validation(dvA)
    dvA.add(f"G{r0}:G{rt-1}")
    # barras en Avance
    ws.conditional_formatting.add(f"G{r0}:G{rt-1}",
        DataBarRule(start_type="num",start_value=0,end_type="num",end_value=1,color=BLUE))
    # colores por Estado
    for txt,col in [("Hecho",GREEN),("En curso",BLUE),("En review",ORANGE),("Bloqueado","C0392B")]:
        ws.conditional_formatting.add(f"I{r0}:I{rt-1}",
            CellIsRule(operator="equal",formula=[f'"{txt}"'],font=F(9.5,True,col)))
    ws.freeze_panes="A4"
    return rt   # fila total

# crear hojas de sprint
totrow={}
for sid,title,obj in SPRINTS:
    totrow[sid]=sprint_sheet(sid,title,obj)

# ---------- hoja PROGRESO (primera) ----------
pg=wb.create_sheet("Progreso",0)
for i,w in enumerate([20,20,42,12,12,14],1): pg.column_dimensions[get_column_letter(i)].width=w
pg.merge_cells("A1:F1"); t=pg["A1"]; t.value="PROYECTO CATALAXIA · TABLERO DE PROGRESO"
t.fill=fill(NAVY); t.font=F(16,True,WHITE); t.alignment=Alignment(horizontal="left",vertical="center",indent=1)
pg.row_dimensions[1].height=34
pg.merge_cells("A2:F2"); s=pg["A2"]; s.value="Screener AR + US · 34 tareas · 108 puntos · 4 sprints (un sábado por sprint)"
s.font=F(10.5,False,GRAYL,it=True); s.alignment=Alignment(horizontal="left",vertical="center",indent=1)

def ref(sid,colL):  # referencia a la celda total de una hoja de sprint
    sheet={"S1":"Sprint 1","S2":"Sprint 2","S3":"Sprint 3","S4":"Sprint 4"}[sid]
    return f"'{sheet}'!{colL}{totrow[sid]}"

# KPIs
kpis=[("Tareas","34"),("Puntos","108"),("Sprints","4"),("Equipo","4")]
r=4
for i,(k,v) in enumerate(kpis):
    cL=get_column_letter(1+i)
    cell=pg.cell(row=r,column=1+i,value=v); cell.font=F(22,True,NAVY); cell.alignment=CEN
    cell.fill=fill(LB); cell.border=BORDER
    lab=pg.cell(row=r+1,column=1+i,value=k); lab.font=F(9,False,GRAYL); lab.alignment=CEN; lab.fill=fill(LB); lab.border=BORDER
# progreso global (col E-F)
pg.cell(row=r,column=5,value="Progreso global").font=F(10,True,NAVY)
pgc=pg.cell(row=r+1,column=5,value=f"=({ref('S1','H')}+{ref('S2','H')}+{ref('S3','H')}+{ref('S4','H')})/108")
pgc.number_format="0%"; pgc.font=F(22,True,ORANGE)
pg.cell(row=r+2,column=5,value="pts hechos / 108").font=F(8.5,False,GRAYL)

# tabla por sprint
r=8
pg.cell(row=r,column=1,value="POR SPRINT").font=F(11,True,NAVY)
r+=1
for i,h in enumerate(["Sprint","Objetivo","Puntos","Pts ✓","Progreso"]):
    c=pg.cell(row=r,column=[1,3,4,5,6][i] if i<5 else 6,value=h)
hdr=["Sprint","","Objetivo","Puntos","Pts ✓","Progreso"]
for i,h in enumerate(["Sprint","Semana","Objetivo (resumen)","Puntos","Pts ✓","%"],1):
    c=pg.cell(row=r,column=i,value=h); c.fill=fill(NAVY); c.font=F(9.5,True,WHITE); c.alignment=CEN; c.border=BORDER
r+=1
sobj={"S1":"Fundamentos","S2":"Datos reales","S3":"Funcionalidad","S4":"QA + entrega"}
for idx,(sid,title,obj) in enumerate(SPRINTS):
    pg.cell(row=r,column=1,value=title.split(" · ")[0]).font=F(9.5,True,[BLUE,GREEN,ORANGE,BLUED][idx])
    pg.cell(row=r,column=2,value=f"Sem {idx+1}").font=F(9.5)
    pg.cell(row=r,column=3,value=sobj[sid]).font=F(9.5)
    pg.cell(row=r,column=4,value=f"={ref(sid,'F')}").font=F(9.5,True,NAVY)
    pg.cell(row=r,column=5,value=f"={ref(sid,'H')}").number_format="0.0"
    pg.cell(row=r,column=6,value=f"={ref(sid,'H')}/{ref(sid,'F')}").number_format="0%"
    for i in range(1,7):
        cc=pg.cell(row=r,column=i); cc.border=BORDER; cc.alignment=CEN if i!=3 else LEFT
        if (r%2)==0:
            pass
    r+=1

# tabla por responsable
r+=1
pg.cell(row=r,column=1,value="POR RESPONSABLE").font=F(11,True,NAVY); r+=1
for i,h in enumerate(["Responsable","Rol","","Puntos","Pts ✓","%"],1):
    c=pg.cell(row=r,column=i,value=h); c.fill=fill(NAVY); c.font=F(9.5,True,WHITE); c.alignment=CEN; c.border=BORDER
r+=1
def sumif(col_key,val,val_col):
    parts=[f"SUMIF('{s}'!{col_key}:{col_key},\"{val}\",'{s}'!{val_col}:{val_col})" for s in ["Sprint 1","Sprint 2","Sprint 3","Sprint 4"]]
    return "="+"+".join(parts)
for resp in ["Federico","Mateo","Joaquín","Aldana"]:
    pg.cell(row=r,column=1,value=resp).font=F(9.5,True,ACC[resp])
    pg.merge_cells(start_row=r,start_column=2,end_row=r,end_column=3)
    pg.cell(row=r,column=2,value=ROLES[resp]).font=F(9,False,GRAYL)
    pg.cell(row=r,column=4,value=sumif("D",resp,"F")).font=F(9.5,True,NAVY)
    pg.cell(row=r,column=5,value=sumif("D",resp,"H")).number_format="0.0"
    pg.cell(row=r,column=6,value=f"=IF(D{r}=0,0,E{r}/D{r})").number_format="0%"
    for i in range(1,7):
        pg.cell(row=r,column=i).border=BORDER; pg.cell(row=r,column=i).alignment=CEN if i not in (2,3) else LEFT
    r+=1

# tabla por epica
r+=1
pg.cell(row=r,column=1,value="POR ÉPICA").font=F(11,True,NAVY); r+=1
for i,h in enumerate(["Épica","","","Puntos","Pts ✓","%"],1):
    c=pg.cell(row=r,column=i,value=h); c.fill=fill(NAVY); c.font=F(9.5,True,WHITE); c.alignment=CEN; c.border=BORDER
r+=1
epics=["Backend","Screener","Detalle","Infra","Datos","Jobs","QA"]
for ep in epics:
    pg.cell(row=r,column=1,value=ep).font=F(9.5,True,NAVY)
    pg.cell(row=r,column=4,value=sumif("C",ep,"F")).font=F(9.5,True,NAVY)
    pg.cell(row=r,column=5,value=sumif("C",ep,"H")).number_format="0.0"
    pg.cell(row=r,column=6,value=f"=IF(D{r}=0,0,E{r}/D{r})").number_format="0%"
    for i in range(1,7):
        pg.cell(row=r,column=i).border=BORDER; pg.cell(row=r,column=i).alignment=CEN if i!=1 else LEFT
    r+=1
pg.freeze_panes="A3"

# quitar hoja default
if "Sheet" in wb.sheetnames: del wb["Sheet"]

out=os.path.join(os.path.dirname(os.path.abspath(__file__)),"Backlog_Catalaxia_Sprints.xlsx")
wb.save(out)
print("SAVED:",out)
print("hojas:",wb.sheetnames)
