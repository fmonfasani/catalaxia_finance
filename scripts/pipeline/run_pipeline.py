# -*- coding: utf-8 -*-
"""
PIPELINE CONSOLIDADO — reconstruye TODO el universo validado en un solo comando.
   python scripts/pipeline/run_pipeline.py

Orden (cada paso reproducible, idempotente):
  1. f1_identidad          — dim_entity/dim_instrument (identidad canónica)
  2. fix_mapeo             — GAMI/BOLT/PATA a su ticker real
  3. f2_reextract_batch    — CNV consolidado byma_only (incluye DGCE)
  4. f2_adr                — CNV consolidado ADR (append)
  5. fix_escala_anchor     — corrige escala anclada en EPS (solo donde es seguro)
  6. fix_single_doc        — CVH/EDSH: balance de un solo documento (minoritario)
  7. fix_manual            — precios BOLT/PATA + CVH PN total 2024-12
  8. f3b_from_reextract    — fact_financials (de-acumulado, RECPAM, identidades)
  9. f4_ratios             — fact_ratios (PER/ROE/márgenes)
 10. fix_escala_mcap       — market cap derivado (precio×NI/EPS)
 11. gate_autoreporte      — cruce ROE vs auto-reporte
 12. validar_suite         — certificación por empresa (~13 cruces) + screener_nivel
 13. f5_screener           — screener_gold byma_only: ratios (período certificado) + sello
 14. f6_sec                — integra 499 US + ADR desde SEC EDGAR (append a screener_gold)

Requiere: eeff_html descargado (fetch con fetch_dgce.py para faltantes) y facts/screener cargados.
"""
import subprocess, sys, os, time
HERE=os.path.dirname(__file__)
PASOS=['f1_identidad','fix_mapeo','f2_reextract_batch','f2_adr','fix_escala_anchor',
       'fix_single_doc','fix_manual','f3b_from_reextract','f4_ratios','fix_escala_mcap',
       'gate_autoreporte','validar_suite','f5_screener','f6_sec']
def run(mod, mostrar=False):
    t=time.time()
    r=subprocess.run([sys.executable, os.path.join(HERE,mod+'.py')],
                     capture_output=not mostrar, text=True, env={**os.environ,'PYTHONIOENCODING':'utf-8'})
    ok='OK' if r.returncode==0 else 'ERROR'
    print(f'  [{ok}] {mod:<22} ({time.time()-t:.0f}s)')
    if r.returncode!=0:
        print(r.stderr[-500:] if r.stderr else ''); sys.exit(1)
    return r.stdout

if __name__=='__main__':
    print('=== PIPELINE CATALAXIA — reconstrucción completa ===')
    for p in PASOS[:-1]:
        run(p)
    print('\n=== VALIDACIÓN FINAL ===')
    out=run('validar_suite', mostrar=False)
    print('\n'.join(l for l in out.splitlines() if any(k in l for k in
          ['CERTIFICADO','alto','interno-ok','REVISAR','SUITE'])))
    print('\n=== SCREENER (producto) ===')
    print(run('f5_screener', mostrar=False))
    print(run('f6_sec', mostrar=False))
