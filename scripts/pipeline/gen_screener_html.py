# -*- coding: utf-8 -*-
"""
Genera la cara del producto: docs/producto/screener.html (autocontenido, datos embebidos).
Universo completo: byma_only (CNV) + ADR + 499 US (SEC). Reproducible: re-correr tras run_pipeline.
"""
import sqlite3, json, os, datetime as dt
con=sqlite3.connect('data/screener.db'); con.row_factory=sqlite3.Row; cur=con.cursor()
rows=[dict(r) for r in cur.execute("select * from screener_gold order by roe desc")]
periodos=sorted({r['periodo_cierre'] for r in rows if r['periodo_cierre']})
from collections import Counter
niv=Counter(r['nivel_certificacion'] for r in rows)
grp=Counter(r['grupo'] for r in rows)
con.close()
# tiers para el masthead (honestos)
cert=niv['CERTIFICADO']+niv['CERTIFICADO-SEC']       # identidades + ancla de mercado
tri=niv['triangulado-SEC']                            # 2 reguladores (SEC+CNV)
parcial=niv['SEC-ok']+niv['interno-ok']               # presente, validación parcial (marcado)

payload={'rows':rows,'total':len(rows),'cert':cert,'tri':tri,'parcial':parcial,
         'n_ar':grp['byma_only'],'n_adr':grp['adr'],'n_us':grp['sp500'],
         'periodo_min':periodos[0] if periodos else '','periodo_max':periodos[-1] if periodos else '',
         'generado':dt.date.today().isoformat()}

TPL=r"""<style>
:root{
  --paper:#f6f7f9; --surface:#ffffff; --surface-2:#eef1f4; --line:#dde2e8;
  --ink:#0d1117; --ink-2:#3d4653; --ink-3:#6b7686;
  --accent:#0a8f63;
  --cert:#0a8f63; --cert-bg:#e2f3ec; --tri:#0e7fa6; --tri-bg:#dceff7;
  --partial:#a9700a; --partial-bg:#f7eeda; --muted:#9aa4b2; --flag:#b23b3b;
  --shadow:0 1px 2px rgba(13,17,23,.05),0 4px 16px rgba(13,17,23,.05);
  --mono:ui-monospace,"Cascadia Code","SF Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,sans-serif;
}
@media (prefers-color-scheme:dark){:root{
  --paper:#0b0e13; --surface:#141a22; --surface-2:#1b232d; --line:#28323f;
  --ink:#eaeef4; --ink-2:#aab4c2; --ink-3:#7c8797; --accent:#2fd39a;
  --cert:#2fd39a; --cert-bg:#0f2a20; --tri:#3fc0e6; --tri-bg:#0d2530;
  --partial:#e0ad4e; --partial-bg:#2a2110; --muted:#5c6675; --flag:#f0776b;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 22px rgba(0,0,0,.35);
}}
:root[data-theme="light"]{
  --paper:#f6f7f9; --surface:#ffffff; --surface-2:#eef1f4; --line:#dde2e8;
  --ink:#0d1117; --ink-2:#3d4653; --ink-3:#6b7686; --accent:#0a8f63;
  --cert:#0a8f63; --cert-bg:#e2f3ec; --tri:#0e7fa6; --tri-bg:#dceff7;
  --partial:#a9700a; --partial-bg:#f7eeda; --muted:#9aa4b2; --flag:#b23b3b;
  --shadow:0 1px 2px rgba(13,17,23,.05),0 4px 16px rgba(13,17,23,.05);
}
:root[data-theme="dark"]{
  --paper:#0b0e13; --surface:#141a22; --surface-2:#1b232d; --line:#28323f;
  --ink:#eaeef4; --ink-2:#aab4c2; --ink-3:#7c8797; --accent:#2fd39a;
  --cert:#2fd39a; --cert-bg:#0f2a20; --tri:#3fc0e6; --tri-bg:#0d2530;
  --partial:#e0ad4e; --partial-bg:#2a2110; --muted:#5c6675; --flag:#f0776b;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 22px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1220px;margin:0 auto;padding:0 22px}
.eyebrow{font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
header.mast{padding:52px 0 30px;border-bottom:1px solid var(--line)}
.mast h1{font-size:clamp(30px,5vw,46px);line-height:1.02;letter-spacing:-.025em;margin:.32em 0 .18em;
  font-weight:800;text-wrap:balance;max-width:16ch}
.mast .lede{font-size:18px;color:var(--ink-2);max-width:56ch;margin:0}
.mast .accentword{color:var(--accent)}
.stats{display:flex;flex-wrap:wrap;gap:14px;margin-top:30px}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 18px;
  box-shadow:var(--shadow);min-width:112px}
.stat .num{font-family:var(--mono);font-size:27px;font-weight:600;letter-spacing:-.02em;
  font-variant-numeric:tabular-nums;line-height:1}
.stat .lbl{font-size:12px;color:var(--ink-3);margin-top:6px;max-width:20ch}
.stat.c1 .num{color:var(--cert)} .stat.c2 .num{color:var(--tri)}
.controls{position:sticky;top:0;z-index:20;background:var(--paper);
  padding:14px 0 12px;border-bottom:1px solid var(--line);margin-bottom:2px}
.controls .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.search{flex:1;min-width:200px;position:relative}
.search input{width:100%;padding:10px 12px 10px 34px;border:1px solid var(--line);border-radius:9px;
  background:var(--surface);color:var(--ink);font-family:var(--sans);font-size:14px}
.search input:focus{outline:2px solid var(--accent);outline-offset:-1px;border-color:transparent}
.search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--ink-3)}
.chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{font-size:12.5px;padding:7px 12px;border-radius:99px;border:1px solid var(--line);
  background:var(--surface);color:var(--ink-2);cursor:pointer;font-weight:500;white-space:nowrap;
  transition:background .12s,color .12s,border-color .12s}
.chip:hover{border-color:var(--accent)}
.chip[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.chip .c{color:var(--muted);font-variant-numeric:tabular-nums}
.chip[aria-pressed="true"] .c{color:var(--paper);opacity:.7}
select.sortsel{padding:9px 11px;border:1px solid var(--line);border-radius:9px;background:var(--surface);
  color:var(--ink);font-family:var(--sans);font-size:13.5px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;background:var(--surface)}
.segbtn{padding:9px 13px;border:0;background:transparent;color:var(--ink-2);font-family:var(--sans);
  font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap;transition:background .12s,color .12s}
.segbtn+ .segbtn{border-left:1px solid var(--line)}
.segbtn[aria-selected="true"]{background:var(--accent);color:#fff}
.winnote{font-size:12.5px;color:var(--ink-3);margin-top:9px;display:flex;align-items:center;gap:7px}
.winnote b{color:var(--ink-2)}
.grouprow{margin-top:11px}
.grouprow .chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.tablecard{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;
  box-shadow:var(--shadow);margin:16px 0 10px}
.scroll{overflow-x:auto;max-height:74vh}
table{border-collapse:collapse;width:100%;min-width:900px}
thead th{position:sticky;top:0;background:var(--surface-2);z-index:5;font-size:11px;letter-spacing:.05em;
  text-transform:uppercase;color:var(--ink-3);font-weight:600;text-align:right;padding:11px 12px;
  border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap;user-select:none}
thead th.txt{text-align:left}
thead th .ar{opacity:0;font-size:9px;margin-left:3px}
thead th[data-active] .ar{opacity:1}
tbody td{padding:10px 12px;text-align:right;border-bottom:1px solid var(--line);
  font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:13.5px;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
tbody tr[data-tk]{cursor:pointer;transition:background .1s}
tbody tr[data-tk]:hover{background:var(--surface-2)}
td.co{text-align:left;font-family:var(--sans)}
.tk{font-weight:700;letter-spacing:.01em}
.co .nm{color:var(--ink-3);font-size:12px;display:block;margin-top:1px;max-width:28ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sec{text-align:left;font-family:var(--sans);font-size:11.5px;color:var(--ink-2)}
.sectag{display:inline-block;padding:2px 8px;border-radius:6px;background:var(--surface-2);border:1px solid var(--line);max-width:15ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle}
.pill{display:inline-flex;align-items:center;gap:5px;font-family:var(--sans);font-size:11px;font-weight:600;
  padding:3px 9px 3px 8px;border-radius:99px;text-align:left;white-space:nowrap}
.pill.cert{background:var(--cert-bg);color:var(--cert)}
.pill.tri{background:var(--tri-bg);color:var(--tri)}
.pill.partial{background:var(--partial-bg);color:var(--partial)}
.pill .dot{width:6px;height:6px;border-radius:50%;background:currentColor;flex:none}
.pos{color:var(--ink)} .strong{font-weight:600}
.na{color:var(--muted);cursor:help;text-decoration:underline dotted var(--muted);text-underline-offset:3px}
tr.detail td{background:var(--surface-2);cursor:default;padding:0}
.dpanel{padding:16px 18px;display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px 26px}
.dpanel h4{margin:0 0 6px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.dpanel .kv{font-family:var(--mono);font-size:12.5px;color:var(--ink-2)}
.dpanel .kv b{color:var(--ink);font-weight:600}
footer{border-top:1px solid var(--line);padding:24px 0 44px;color:var(--ink-3);font-size:13px;margin-top:22px}
footer .m{max-width:74ch}
footer b{color:var(--ink-2)}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px;font-size:12px;color:var(--ink-2);align-items:center}
.legend span.li{display:inline-flex;align-items:center;gap:6px}
.count{font-size:12.5px;color:var(--ink-3);padding:8px 0 0 2px}
@media (max-width:640px){.mast{padding:34px 0 22px}.stat{flex:1;min-width:44%}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap">
  <header class="mast">
    <div class="eyebrow">Catalaxia · Screener multi-mercado con datos certificados</div>
    <h1>Fundamentals que podés <span class="accentword">probar</span>.</h1>
    <p class="lede"><b id="ledeN"></b> empresas de Argentina y EE.UU. Cada ratio se computa desde el último ejercicio
      con <b>certificación auditable</b> — identidades contables, dos fuentes independientes y ancla
      de mercado. Donde un dato no se puede validar, se marca. Nada se inventa.</p>
    <div class="stats" id="stats"></div>
  </header>

  <div class="controls">
    <div class="row">
      <label class="search">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="q" type="search" placeholder="Buscar ticker, empresa o sector…" aria-label="Buscar">
      </label>
      <div class="seg" id="winseg" role="tablist" aria-label="Ventana temporal">
        <button class="segbtn" data-win="anual" aria-selected="true">Anual · certificado</button>
        <button class="segbtn" data-win="ttm" aria-selected="false">TTM · comparable</button>
      </div>
      <select class="sortsel" id="sortsel" aria-label="Ordenar por">
        <option value="roe">ROE ▾</option>
        <option value="per">PER ▴</option>
        <option value="p_book">P/B ▴</option>
        <option value="margen_neto">Margen neto ▾</option>
        <option value="deuda_ebitda">Deuda/EBITDA ▴</option>
        <option value="ticker">Ticker A→Z</option>
      </select>
    </div>
    <div class="chips grouprow" id="groupchips"></div>
    <div class="winnote" id="winnote"></div>
    <div class="count" id="count"></div>
  </div>

  <div class="tablecard"><div class="scroll">
    <table>
      <thead><tr id="head"></tr></thead>
      <tbody id="body"></tbody>
    </table>
  </div></div>

  <footer>
    <div class="legend">
      <span class="li"><span class="pill cert"><span class="dot"></span>Certificado</span> identidades + ancla de mercado</span>
      <span class="li"><span class="pill tri"><span class="dot"></span>Triangulado</span> 2 reguladores (SEC + CNV)</span>
      <span class="li"><span class="pill partial"><span class="dot"></span>Parcial</span> presente, validación parcial (marcado)</span>
      <span class="li"><span class="na">—</span> dato no cross-validado (no se muestra)</span>
    </div>
    <p class="m" id="foot"></p>
  </footer>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const rows=D.rows;
const COLS=[
 {k:'ticker',t:'Empresa',txt:true},{k:'sector',t:'Sector',sec:true},
 {k:'nivel_certificacion',t:'Sello',pill:true},
 {k:'roe',t:'ROE',pct:true,strong:true},{k:'margen_neto',t:'Mg neto',pct:true},
 {k:'deuda_ebitda',t:'Deuda/EBITDA',mult:true},{k:'per',t:'PER',mult:true},
 {k:'p_book',t:'P/B',mult:true},{k:'p_sales',t:'P/S',mult:true},{k:'ev_ebitda',t:'EV/EBITDA',mult:true},
];
const SECN={RealEstate_Agro:'Real estate/Agro',Infra_Utilities:'Infra/Utilities',Telecom_Media:'Telecom/Media',
  Financiero:'Financiero',Materiales:'Materiales',Energia:'Energía',Consumo:'Consumo',Otros:'Otros'};
const GRP={byma_only:{n:'Argentina',cur:'AR$'},adr:{n:'ADR',cur:'US$'},sp500:{n:'EE.UU.',cur:'US$'}};
const PILL={'CERTIFICADO':['cert','Certificado'],'CERTIFICADO-SEC':['cert','Cert. SEC'],
  'triangulado-SEC':['tri','Triangulado'],'SEC-ok':['partial','SEC'],'interno-ok':['partial','Interno']};
const RATNAME={per:'PER',p_book:'P/B',p_sales:'P/S',ev_ebitda:'EV/EBITDA',roe:'ROE',roa:'ROA',
  deuda_ebitda:'Deuda/EBITDA',margen_neto:'Margen neto',margen_bruto:'Margen bruto',
  margen_operativo:'Margen operativo',margen_ebitda:'Margen EBITDA'};
let state={q:'',grp:new Set(),sort:'roe',open:null,win:'anual'};
document.getElementById('ledeN').textContent=D.total;
const RCOLS=['per','p_book','p_sales','roe','roa','margen_neto','margen_bruto','margen_operativo','margen_ebitda','deuda_ebitda','ev_ebitda'];
// valor en la ventana activa: TTM usa *_ttm si la empresa tiene ventana TTM; si no (US, o TTM roto), cae al anual
const hasTTM=r=>!!r.ttm_cierre;
function val(r,k){
  if(!RCOLS.includes(k)) return r[k];
  return (state.win==='ttm'&&hasTTM(r))? r[k+'_ttm'] : r[k];
}
function noconf(r){ return (state.win==='ttm'&&hasTTM(r))? (r.ttm_no_confiables||'') : (r.ratios_no_confiables||''); }
function cierre(r){ return (state.win==='ttm'&&hasTTM(r))? r.ttm_cierre : r.periodo_cierre; }

document.getElementById('stats').innerHTML=[
 ['c0',D.total,'Empresas cubiertas'],
 ['c1',D.cert,'Certificadas (identidades + ancla)'],
 ['c2',D.tri,'Trianguladas (SEC + CNV)'],
 ['c0',D.parcial,'Validación parcial (marcadas)'],
 ['c0','0','Inventadas'],
].map(([c,n,l])=>`<div class="stat ${c}"><div class="num">${n}</div><div class="lbl">${l}</div></div>`).join('');

document.getElementById('groupchips').innerHTML=['byma_only','adr','sp500'].map(g=>
  `<button class="chip" data-grp="${g}" aria-pressed="false">${GRP[g].n} <span class="c">${rows.filter(r=>r.grupo==g).length}</span></button>`).join('');

document.getElementById('head').innerHTML=COLS.map(c=>
  `<th class="${c.txt||c.sec||c.pill?'txt':''}" data-k="${c.k}">${c.t}<span class="ar">▼</span></th>`).join('');

const fmtPct=v=>v==null?null:(v*100).toFixed(1)+'%';
const fmtMult=v=>v==null?null:v.toFixed(v>=100?0:(v>=10?1:2))+'×';
function cell(r,c){
  if(c.txt) return `<td class="co"><span class="tk">${r.ticker}</span><span class="nm">${r.nombre}</span></td>`;
  if(c.sec){const s=SECN[r.sector]||r.sector||'—';return `<td class="sec"><span class="sectag" title="${s}">${s}</span></td>`;}
  if(c.pill){const[cl,lb]=PILL[r.nivel_certificacion]||['partial',r.nivel_certificacion];
    return `<td class="sec"><span class="pill ${cl}"><span class="dot"></span>${lb}</span></td>`;}
  const v=val(r,c.k),s=c.pct?fmtPct(v):fmtMult(v);
  if(s==null){
    const flagged=noconf(r).split(',').includes(c.k);
    const ttmroto=state.win==='ttm'&&hasTTM(r)&&flagged;
    const why=ttmroto?'trimestre reciente con error de escala — usá la vista Anual (certificada)'
      :flagged?(['per','p_book','p_sales','ev_ebitda'].includes(c.k)&&!r.mcap_confiable
        ?'market cap no cross-validado entre dos fuentes':'valor fuera de rango sano')
      :(c.k==='per'?'ganancias del período ≤ 0 (sin PER)':'sin dato en el estado');
    return `<td><span class="na" title="${why}">—</span></td>`;}
  return `<td class="${c.strong?'strong pos':'pos'}">${s}</td>`;
}
function detailRow(r){
  const cur=GRP[r.grupo].cur, nc=noconf(r).split(',').filter(Boolean);
  const checks=r.checks_ok!=null?`<b>${r.checks_ok}/${r.checks_aplicables}</b> cruces OK`:'—';
  const mcaptxt=r.market_cap?(cur+' '+(r.market_cap/1e9).toFixed(1)+'B'):'—';
  const prectxt=r.precio?(cur+' '+r.precio.toLocaleString('es-AR',{maximumFractionDigits:2})):'—';
  const winlbl=state.win==='ttm'&&hasTTM(r)?'TTM (comparativo, no certificado)':'Anual (certificado)';
  return `<tr class="detail"><td colspan="${COLS.length}"><div class="dpanel">
    <div><h4>Certificación</h4><div class="kv"><b>${(PILL[r.nivel_certificacion]||['','?'])[1]}</b> · ${checks}</div></div>
    <div><h4>Ventana · cierre</h4><div class="kv"><b>${cierre(r)||'—'}</b> · ${winlbl}</div></div>
    <div><h4>${GRP[r.grupo].n} · Precio · Market cap</h4><div class="kv">${prectxt} · ${mcaptxt} ${r.mcap_confiable?'✓ 2 fuentes':'· 1 fuente'} · ${r.es_financiera?'financiera':'no financiera'}</div></div>
    ${nc.length?`<div><h4>Ratios no mostrados</h4><div class="kv">${nc.map(x=>RATNAME[x]||x).join(', ')}<br><span style="color:var(--muted)">no cross-validados — flag &gt; fabricar</span></div></div>`:''}
  </div></td></tr>`;
}
function apply(){
  let f=rows.filter(r=>{
    if(state.grp.size&&!state.grp.has(r.grupo)) return false;
    if(state.q){const q=state.q.toLowerCase();
      if(!(r.ticker.toLowerCase().includes(q)||(r.nombre||'').toLowerCase().includes(q)||(SECN[r.sector]||r.sector||'').toLowerCase().includes(q))) return false;}
    return true;});
  const k=state.sort, asc=['per','p_book','p_sales','deuda_ebitda','ev_ebitda','ticker'].includes(k);
  f.sort((a,b)=>{
    if(k==='ticker') return a.ticker<b.ticker?-1:1;
    const av=val(a,k),bv=val(b,k);
    if(av==null&&bv==null) return 0; if(av==null) return 1; if(bv==null) return -1;
    return asc?av-bv:bv-av;});
  document.getElementById('body').innerHTML=f.map(r=>
    `<tr data-tk="${r.ticker}">${COLS.map(c=>cell(r,c)).join('')}</tr>`+(state.open===r.ticker?detailRow(r):'')).join('');
  document.querySelectorAll('#head th').forEach(th=>{
    th.toggleAttribute('data-active',th.dataset.k===k); th.querySelector('.ar').textContent=asc?'▲':'▼';});
  document.getElementById('count').textContent=`${f.length} de ${rows.length} empresas`;
  document.querySelectorAll('#body tr[data-tk]').forEach(tr=>tr.onclick=()=>{
    state.open=state.open===tr.dataset.tk?null:tr.dataset.tk; apply();});
}
const WINNOTE={
  anual:'Mostrando el <b>último ejercicio anual certificado</b> — el dato cross-validado por la suite.',
  ttm:'Mostrando <b>TTM</b> (últimos 4 trimestres) — <b>comparable 1:1 con investing.com</b>, no certificado. EE.UU. usa su último 10-K en ambas vistas.'};
function setWin(w){state.win=w; document.querySelectorAll('#winseg .segbtn').forEach(b=>b.setAttribute('aria-selected',b.dataset.win===w));
  document.getElementById('winnote').innerHTML='◷ '+WINNOTE[w]; apply();}
document.getElementById('winseg').onclick=e=>{const b=e.target.closest('.segbtn'); if(b) setWin(b.dataset.win);};
document.getElementById('q').oninput=e=>{state.q=e.target.value;apply();};
document.getElementById('sortsel').onchange=e=>{state.sort=e.target.value;apply();};
document.getElementById('groupchips').onclick=e=>{const c=e.target.closest('.chip');if(!c)return;
  const g=c.dataset.grp; state.grp.has(g)?state.grp.delete(g):state.grp.add(g);
  c.setAttribute('aria-pressed',state.grp.has(g)); apply();};
document.querySelectorAll('#head th').forEach(th=>th.onclick=()=>{
  document.getElementById('sortsel').value=th.dataset.k; state.sort=th.dataset.k; apply();});
document.getElementById('foot').innerHTML=
  `Generado el <b>${D.generado}</b> desde <b>screener_gold</b> (pipeline reproducible <b>run_pipeline.py</b>). `+
  `Ejercicios de cierre entre <b>${D.periodo_min}</b> y <b>${D.periodo_max}</b>. `+
  `<b>${D.n_ar}</b> argentinas y ADR desde estados presentados a la <b>CNV</b> (XBRL crudo); `+
  `<b>${D.n_us}</b> de EE.UU. desde <b>SEC EDGAR</b> (10-K). Ratios en la moneda de reporte de cada empresa. `+
  `Los ADR se triangulan CNV↔SEC (dos reguladores).`;
setWin('anual');
</script>
"""
out='docs/producto/screener.html'
os.makedirs(os.path.dirname(out),exist_ok=True)
open(out,'w',encoding='utf-8').write(TPL.replace('__DATA__',json.dumps(payload,ensure_ascii=False)))
print(f'escrito {out} ({payload["total"]} empresas: {payload["n_ar"]} AR + {payload["n_adr"]} ADR + {payload["n_us"]} US)')
