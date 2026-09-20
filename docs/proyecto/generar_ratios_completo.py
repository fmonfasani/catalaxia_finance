# -*- coding: utf-8 -*-
"""Workbook completo de ratios con TODOS los tags + ratios como FORMULAS VIVAS.
Solapas: Formulas | CEDEARs (sp500) | Only BYMA | ADR.
Cada ratio es una formula de Excel que referencia las columnas de tags de la misma
fila -> el usuario ve de donde sale cada numero y puede hacer doble/triple chequeo.

BYMA: flujos en TTM des-acumulado (Q1=YTD, resto=YTD-YTD_ant; NO usa tipo A/P).
CEDEARs/ADR: EDGAR ya viene en TTM.
"""
import os, sqlite3
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

NAVY="1A2744"; WHITE="FFFFFF"; GRID="D6E2F2"; LB3="F4F8FE"; INK="1A2744"; GRAYL="6B7589"; GREEN_T="1F6B35"; LB="DCEAFF"
def Ft(sz=10,b=False,color="3A4458"): return Font(name="Calibri",size=sz,bold=b,color=color)
def fill(c): return PatternFill("solid",fgColor=c)
S=Side(style="thin",color=GRID); BORDER=Border(left=S,right=S,top=S,bottom=S)
CEN=Alignment(horizontal="center",vertical="center"); LEFT=Alignment(horizontal="left",vertical="center")

DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","..","data","screener.db")
con=sqlite3.connect(DB); cur=con.cursor()

# ---- helpers TTM (byma) ----
def mb(a,b): return (int(b[:4])-int(a[:4]))*12+(int(b[5:7])-int(a[5:7]))
def qn(m,fy): return 4-((fy-m)%12)//3
def ser(cuit,c):
    d={}
    for pe,v in cur.execute("select period_end,valor from cnv_estados_v2 where cuit=? and concepto=? and valor is not null order by period_end",(cuit,c)): d[pe]=v
    return sorted(d.items())
def ttm(cuit,c,fy):
    if not fy: return None
    out,prev=[],None
    for pe,cum in ser(cuit,c):
        q=qn(int(pe[5:7]),fy); v=cum if q==1 else (cum-prev[1] if (prev and mb(prev[0],pe)==3) else None)
        out.append((pe,v)); prev=(pe,cum)
    sa=[(pe,v) for pe,v in out if v is not None]
    if len(sa)<4: return None
    w=sa[-4:]
    if any(mb(w[i][0],w[i+1][0])!=3 for i in range(3)): return None
    return sum(v for _,v in w)
def snap(cuit,c):
    r=cur.execute("select valor from cnv_estados_v2 where cuit=? and concepto=? order by period_end desc limit 1",(cuit,c)).fetchone()
    return r[0] if r else None

# ---- layout de columnas (igual en las 3 solapas de datos) ----
# A ticker | B..O tags | P..AA ratios(formula)
TAGCOLS=["NetIncome TTM","Revenue TTM","GrossProfit TTM","OperatingIncome TTM","EBITDA TTM","FCF TTM",
         "Equity","Assets","Deuda","Cash","MarketCap","Dividendos 12m","EPS","shares"]  # B..O
# formulas de ratio: (nombre, template con {r})
RATIOFORM=[
 ("ROE","=IFERROR(B{r}/H{r},\"\")"),("ROA","=IFERROR(B{r}/I{r},\"\")"),
 ("Margen Neto","=IFERROR(B{r}/C{r},\"\")"),("Margen Op.","=IFERROR(E{r}/C{r},\"\")"),
 ("Margen Bruto","=IFERROR(D{r}/C{r},\"\")"),("Deuda/EBITDA","=IFERROR(J{r}/F{r},\"\")"),
 ("EV/EBITDA","=IFERROR((L{r}+J{r}-K{r})/F{r},\"\")"),("FCF/CE","=IFERROR(G{r}/(J{r}+H{r}),\"\")"),
 ("Payout","=IFERROR(M{r}/B{r},\"\")"),("EPS (calc)","=IFERROR(B{r}/O{r},\"\")"),
 ("PER","=IFERROR(L{r}/B{r},\"\")"),("shares (calc)","=IFERROR(B{r}/N{r},\"\")"),
]
PCT_RATIOS={"ROE","ROA","Margen Neto","Margen Op.","Margen Bruto","FCF/CE","Payout"}

wb=Workbook()

# ============ SOLAPA 1: FORMULAS ============
fs=wb.active; fs.title="Formulas"
for i,w in enumerate([18,40,52],1): fs.column_dimensions[get_column_letter(i)].width=w
fs.cell(1,1,"CÓMO SE CALCULA CADA RATIO — todas las fórmulas").font=Ft(14,True,NAVY)
fs.cell(2,1,"Flujos = TTM (últimos 4 trimestres). Balance = último período. BYMA des-acumula; EDGAR ya viene TTM.").font=Ft(9,False,GRAYL)
for i,h in enumerate(["Ratio","Fórmula(s)","Tags / notas"],1):
    c=fs.cell(4,i,h); c.fill=fill(NAVY); c.font=Ft(10,True,WHITE); c.alignment=CEN; c.border=BORDER
FORM=[
 ("ROE","NetIncome ÷ Equity","Beneficio neto (TTM) sobre patrimonio. Si NI<0 → ROE negativo (pérdida)."),
 ("ROA","NetIncome ÷ Assets","Retorno sobre activos totales."),
 ("Margen Neto","NetIncome ÷ Revenue","Ganancia final por peso vendido."),
 ("Margen Op.","OperatingIncome ÷ Revenue","Ganancia operativa por peso vendido (antes de intereses/RECPAM)."),
 ("Margen Bruto","GrossProfit ÷ Revenue","(Revenue − COGS) ÷ Revenue."),
 ("Deuda/EBITDA","(DebtCurrent + DebtNonCurrent) ÷ EBITDA","Años de EBITDA para pagar la deuda. n/d si EBITDA≤0."),
 ("EV/EBITDA","(MarketCap + Deuda − Cash) ÷ EBITDA","Enterprise Value sobre EBITDA. n/d si EBITDA≤0."),
 ("FCF/CE","(CF_Operativo + CF_Inversion) ÷ (Deuda + Equity)","Free Cash Flow sobre capital empleado."),
 ("Payout","Dividendos(12m) ÷ NetIncome","% de ganancias repartido. n/d si pérdida."),
 ("EPS","NetIncome ÷ shares    |    EPS_basico (directo)","Ganancia por acción. Dos formas equivalentes."),
 ("PER","Precio ÷ EPS    |    MarketCap ÷ NetIncome","Dos formas equivalentes. n/d si NI≤0 (pérdida)."),
 ("shares","NetIncome ÷ EPS_basico    |    MarketCap ÷ Precio","Cantidad de acciones, dos formas."),
]
r=5
for ra,fo,tg in FORM:
    fs.cell(r,1,ra).font=Ft(10,True,INK); fs.cell(r,2,fo).font=Ft(9.5); fs.cell(r,3,tg).font=Ft(9,color=GRAYL)
    for i in range(1,4): fs.cell(r,i).border=BORDER; fs.cell(r,i).alignment=LEFT
    fs.row_dimensions[r].height=30; r+=1
r+=1
for txt in ["TTM = suma de los últimos 4 trimestres standalone (des-acumulados).",
            "Des-acumular (BYMA): standalone(Q) = YTD(Q) − YTD(Q−1); el Q1 (inicio de ejercicio) ya es standalone.",
            "IMPORTANTE: para saber si es Q1 usar el fin de ejercicio (hoja no incluida acá) — NO el campo tipo A/P (no es confiable).",
            "En las solapas de datos: columnas B..O son los TAGS; P..AA son los RATIOS como fórmula viva (clic para ver el cálculo)."]:
    fs.cell(r,1,txt).font=Ft(9,False,GRAYL); r+=1

# ============ helper para armar una solapa de datos ============
def data_sheet(name, rows_data):
    ws=wb.create_sheet(name)
    ws.column_dimensions["A"].width=10
    for i in range(2,16): ws.column_dimensions[get_column_letter(i)].width=15
    for i in range(16,28): ws.column_dimensions[get_column_letter(i)].width=12
    # encabezado: fila 1 grupos, fila 2 columnas
    ws.merge_cells("B1:O1"); ws["B1"]="TAGS (líneas contables — todos los necesarios)"; ws["B1"].fill=fill("2E3A56"); ws["B1"].font=Ft(10,True,WHITE); ws["B1"].alignment=CEN
    ws.merge_cells("P1:AA1"); ws["P1"]="RATIOS (fórmula viva → referencia los tags)"; ws["P1"].fill=fill(GREEN_T); ws["P1"].font=Ft(10,True,WHITE); ws["P1"].alignment=CEN
    ws.cell(2,1,"Ticker").fill=fill(NAVY); ws.cell(2,1).font=Ft(9,True,WHITE); ws.cell(2,1).alignment=CEN; ws.cell(2,1).border=BORDER
    for j,h in enumerate(TAGCOLS,2):
        c=ws.cell(2,j,h); c.fill=fill(NAVY); c.font=Ft(8.5,True,WHITE); c.alignment=CEN; c.border=BORDER
    for j,(h,_) in enumerate(RATIOFORM,16):
        c=ws.cell(2,j,h); c.fill=fill(GREEN_T); c.font=Ft(8.5,True,WHITE); c.alignment=CEN; c.border=BORDER
    ws.freeze_panes="B3"
    r=3
    for tk,vals in rows_data:
        ws.cell(r,1,tk).font=Ft(9,True,INK); ws.cell(r,1).border=BORDER; ws.cell(r,1).alignment=LEFT
        for j,v in enumerate(vals,2):   # B..O tags
            c=ws.cell(r,j, round(v,2) if isinstance(v,(int,float)) else None); c.border=BORDER; c.font=Ft(8.5); c.alignment=Alignment(horizontal="right")
        for j,(h,tmpl) in enumerate(RATIOFORM,16):
            c=ws.cell(r,j, tmpl.format(r=r)); c.border=BORDER; c.font=Ft(9,True,GREEN_T); c.alignment=CEN; c.fill=fill(LB3)
            if h in PCT_RATIOS: c.number_format="0.0%"
            else: c.number_format="0.0"
        r+=1
    return ws

# ============ datos EDGAR (CEDEARs sp500 / ADR) ============
def edgar_rows(grupo):
    out=[]
    q="select ticker,_netincome_ttm,_revenue_ttm,margen_bruto,margen_operativo,_ebitda_ttm,_fcf_ttm,_equity,_assets,_deuda,market_cap,payout,eps_ttm from ratios where grupo=? order by ticker"
    for tk,ni,rev,mb_,mo,eb,fcf,eq,ast,deu,mc,pay,eps in cur.execute(q,(grupo,)):
        gp=(mb_*rev) if (isinstance(mb_,(int,float)) and isinstance(rev,(int,float))) else None
        oi=(mo*rev) if (isinstance(mo,(int,float)) and isinstance(rev,(int,float))) else None
        div=(pay*ni) if (isinstance(pay,(int,float)) and isinstance(ni,(int,float))) else None
        sh=(ni/eps) if (isinstance(ni,(int,float)) and isinstance(eps,(int,float)) and eps) else None
        # B..O: NI,Rev,GP,OI,EBITDA,FCF,Equity,Assets,Deuda,Cash,MarketCap,Div,EPS,shares
        out.append((tk,[ni,rev,gp,oi,eb,fcf,eq,ast,deu,None,mc,div,eps,sh]))
    return out

# ============ datos BYMA (TTM des-acumulado) ============
def byma_rows():
    fc={cu:fy for cu,fy in cur.execute("select cuit,fy_end_month from fiscal_calendar")}
    out=[]
    for cuit,tk,mc in cur.execute("select cuit,ticker,MarketCapUSD from screener where grupo='byma_only' order by ticker").fetchall():
        fy=fc.get(cuit)
        ni=ttm(cuit,"NetIncome",fy); rev=ttm(cuit,"Revenue",fy); gp=ttm(cuit,"GrossProfit",fy)
        oi=ttm(cuit,"OperatingIncome",fy); eb=ttm(cuit,"EBITDA",fy)
        cfo=ttm(cuit,"CF_Operativo",fy); cfi=ttm(cuit,"CF_Inversion",fy)
        fcf=(cfo+cfi) if (isinstance(cfo,(int,float)) and isinstance(cfi,(int,float))) else None
        eq=snap(cuit,"Equity"); ast=snap(cuit,"Assets")
        dc=snap(cuit,"DebtCurrent"); dnc=snap(cuit,"DebtNonCurrent")
        deu=(dc or 0)+(dnc or 0)
        cash=snap(cuit,"Cash")
        eps=ttm(cuit,"EPS_basico",fy)
        sh=(ni/eps) if (isinstance(ni,(int,float)) and isinstance(eps,(int,float)) and eps) else None
        div=cur.execute("select sum(cast(monto_candidato as real)) from cnv_dividendos where cuit=? and fecha_candidata>='2025-06-01'",(cuit,)).fetchone()[0]
        mc=mc if isinstance(mc,(int,float)) else None
        out.append((tk,[ni,rev,gp,oi,eb,fcf,eq,ast,deu,cash,mc,div,eps,sh]))
    return out

data_sheet("CEDEARs", edgar_rows("sp500"))
data_sheet("Only BYMA", byma_rows())
data_sheet("ADR", edgar_rows("adr_arg"))

out=os.path.join(os.path.dirname(os.path.abspath(__file__)),"Ratios_Completo_Catalaxia.xlsx")
wb.save(out)
print("SAVED:",out); print("solapas:",wb.sheetnames)
con.close()
