#!/usr/bin/env python3
"""
Script: Generar screener final (Excel + reportes HTML)

Consolida todos los datos y genera reportes:
- screener_final.xlsx (tabla consolidada Excel)
- screener_summary.txt (resumen ejecutivo)
- screener_ranking_*.html (rankings por métrica)

Entrada: precios_completos.csv + financieros_edgar.csv + ratios.csv
Salida: screener_final.xlsx + reportes HTML

Uso:
  python 08_generar_screener.py
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/screener.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# PASO 1: CARGAR DATOS
# ============================================================================

logger.info("Cargando datos de ratios...")

ratios_df = pd.read_csv('data/ratios.csv')

logger.info(f"Total acciones cargadas: {len(ratios_df)}")
logger.info(f"CEDEARs: {len(ratios_df[ratios_df['tipo']=='CEDEAR'])}")
logger.info(f"ADRs: {len(ratios_df[ratios_df['tipo']=='ADR'])}")

# ============================================================================
# PASO 2: GENERAR EXCEL CON MÚLTIPLES TABS
# ============================================================================

logger.info("Generando screener_final.xlsx...")

excel_path = 'screener_final.xlsx'

with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
    # Tab 1: Resumen General
    logger.info("  - Tab: Resumen General")
    ratios_df.to_excel(writer, sheet_name='Resumen General', index=False)

    # Tab 2: Ranking P/E (menor = más barato)
    logger.info("  - Tab: Ranking P/E")
    pe_ranking = ratios_df[ratios_df['pe'].notna()].sort_values('pe').head(50)[
        ['ticker', 'empresa', 'tipo', 'precio', 'pe', 'p_book', 'deuda_equity']
    ]
    pe_ranking.to_excel(writer, sheet_name='Ranking P/E', index=False)

    # Tab 3: Ranking ROE (mayor = más rentable)
    logger.info("  - Tab: Ranking ROE")
    roe_ranking = ratios_df[ratios_df['roe'].notna()].sort_values('roe', ascending=False).head(50)[
        ['ticker', 'empresa', 'tipo', 'roe', 'margen_neto', 'deuda_equity']
    ]
    roe_ranking.to_excel(writer, sheet_name='Ranking ROE', index=False)

    # Tab 4: Ranking Margen Neto
    logger.info("  - Tab: Ranking Margen")
    margen_ranking = ratios_df[ratios_df['margen_neto'].notna()].sort_values('margen_neto', ascending=False).head(50)[
        ['ticker', 'empresa', 'tipo', 'margen_neto', 'revenue', 'net_income']
    ]
    margen_ranking.to_excel(writer, sheet_name='Ranking Margen', index=False)

    # Tab 5: Ranking Deuda/Equity (menor = menos apalancado)
    logger.info("  - Tab: Ranking Deuda/Equity")
    deuda_ranking = ratios_df[ratios_df['deuda_equity'].notna()].sort_values('deuda_equity').head(50)[
        ['ticker', 'empresa', 'tipo', 'deuda_equity', 'liabilities', 'equity']
    ]
    deuda_ranking.to_excel(writer, sheet_name='Ranking Deuda/Equity', index=False)

    # Tab 6: Ranking FCF Yield
    logger.info("  - Tab: Ranking FCF Yield")
    fcf_ranking = ratios_df[ratios_df['fcf_yield'].notna()].sort_values('fcf_yield', ascending=False).head(50)[
        ['ticker', 'empresa', 'tipo', 'fcf_yield', 'fcf', 'market_cap']
    ]
    fcf_ranking.to_excel(writer, sheet_name='Ranking FCF Yield', index=False)

    # Tab 7: Por Sector (CEDEARs)
    logger.info("  - Tab: Por Sector")
    cedears = ratios_df[ratios_df['tipo']=='CEDEAR']
    sector_summary = cedears.groupby('sector').agg({
        'ticker': 'count',
        'precio': 'mean',
        'pe': 'mean',
        'roe': 'mean',
        'margen_neto': 'mean'
    }).round(2)
    sector_summary.columns = ['Cantidad', 'Precio Promedio', 'P/E Promedio', 'ROE Promedio', 'Margen Promedio']
    sector_summary.to_excel(writer, sheet_name='Por Sector')

logger.info(f"✓ Guardado: {excel_path}")

# ============================================================================
# PASO 3: GENERAR RESUMEN EJECUTIVO
# ============================================================================

logger.info("Generando resumen ejecutivo...")

summary_path = 'screener_summary.txt'

with open(summary_path, 'w', encoding='utf-8') as f:
    f.write("="*80 + "\n")
    f.write("SCREENER FINANCIERO: 218+ ACCIONES (CEDEARs + ADRs)\n")
    f.write("="*80 + "\n")
    f.write(f"\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Total acciones: {len(ratios_df)}\n")
    f.write(f"CEDEARs: {len(ratios_df[ratios_df['tipo']=='CEDEAR'])}\n")
    f.write(f"ADRs: {len(ratios_df[ratios_df['tipo']=='ADR'])}\n")

    f.write("\n" + "="*80 + "\n")
    f.write("MÉTRICAS DE COBERTURA\n")
    f.write("="*80 + "\n")
    f.write(f"P/E: {ratios_df['pe'].notna().sum()}/{len(ratios_df)} ({100*ratios_df['pe'].notna().sum()/len(ratios_df):.1f}%)\n")
    f.write(f"ROE: {ratios_df['roe'].notna().sum()}/{len(ratios_df)} ({100*ratios_df['roe'].notna().sum()/len(ratios_df):.1f}%)\n")
    f.write(f"Margen Neto: {ratios_df['margen_neto'].notna().sum()}/{len(ratios_df)} ({100*ratios_df['margen_neto'].notna().sum()/len(ratios_df):.1f}%)\n")
    f.write(f"Deuda/Equity: {ratios_df['deuda_equity'].notna().sum()}/{len(ratios_df)} ({100*ratios_df['deuda_equity'].notna().sum()/len(ratios_df):.1f}%)\n")
    f.write(f"FCF: {ratios_df['fcf'].notna().sum()}/{len(ratios_df)} ({100*ratios_df['fcf'].notna().sum()/len(ratios_df):.1f}%)\n")

    f.write("\n" + "="*80 + "\n")
    f.write("ESTADÍSTICAS POR MÉTRICA\n")
    f.write("="*80 + "\n")

    f.write("\nP/E (Price/Earnings):\n")
    pe_stats = ratios_df['pe'].describe()
    f.write(f"  Min: {pe_stats['min']:.2f} | Max: {pe_stats['max']:.2f} | Mean: {pe_stats['mean']:.2f}\n")

    f.write("\nROE (Return on Equity):\n")
    roe_stats = ratios_df['roe'].describe()
    f.write(f"  Min: {roe_stats['min']:.4f} | Max: {roe_stats['max']:.4f} | Mean: {roe_stats['mean']:.4f}\n")

    f.write("\nMargen Neto:\n")
    margen_stats = ratios_df['margen_neto'].describe()
    f.write(f"  Min: {margen_stats['min']:.4f} | Max: {margen_stats['max']:.4f} | Mean: {margen_stats['mean']:.4f}\n")

    f.write("\n" + "="*80 + "\n")
    f.write("TOP 10 ACCIONES BARATAS (Menor P/E)\n")
    f.write("="*80 + "\n")
    top_cheap = ratios_df[ratios_df['pe'].notna()].nsmallest(10, 'pe')[['ticker', 'empresa', 'precio', 'pe']]
    for idx, row in top_cheap.iterrows():
        f.write(f"{row['ticker']:6s} | {row['empresa']:30s} | P/E: {row['pe']:>7.2f}\n")

    f.write("\n" + "="*80 + "\n")
    f.write("TOP 10 ACCIONES RENTABLES (Mayor ROE)\n")
    f.write("="*80 + "\n")
    top_roe = ratios_df[ratios_df['roe'].notna()].nlargest(10, 'roe')[['ticker', 'empresa', 'roe']]
    for idx, row in top_roe.iterrows():
        roe_pct = row['roe'] * 100 if row['roe'] else 0
        f.write(f"{row['ticker']:6s} | {row['empresa']:30s} | ROE: {roe_pct:>6.1f}%\n")

    f.write("\n" + "="*80 + "\n")
    f.write("ARCHIVOS GENERADOS\n")
    f.write("="*80 + "\n")
    f.write(f"screener_final.xlsx - Tabla consolidada con 7 tabs\n")
    f.write(f"screener_summary.txt - Este resumen\n")
    f.write(f"screener_ranking_*.html - Rankings por métrica (HTML)\n")

logger.info(f"✓ Guardado: {summary_path}")

# ============================================================================
# PASO 4: GENERAR RANKINGS HTML
# ============================================================================

logger.info("Generando reportes HTML...")

def generate_html_ranking(title, data, filename):
    """Generar tabla HTML sorteable"""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        tr:hover {{ background-color: #ddd; }}
        h1 {{ color: #333; }}
    </style>
    <script>
        function sortTable(n) {{
            var table = document.getElementById("dataTable");
            var rows = table.getElementsByTagName("tr");
            var switching = true;
            var shouldSwitch, i, x, y;
            var dir = "asc";

            while (switching) {{
                switching = false;
                for (i = 1; i < (rows.length - 1); i++) {{
                    shouldSwitch = false;
                    x = rows[i].getElementsByTagName("td")[n];
                    y = rows[i + 1].getElementsByTagName("td")[n];

                    var xVal = isNaN(parseFloat(x.innerHTML)) ? x.innerHTML : parseFloat(x.innerHTML);
                    var yVal = isNaN(parseFloat(y.innerHTML)) ? y.innerHTML : parseFloat(y.innerHTML);

                    if (dir == "asc") {{
                        if (xVal > yVal) {{
                            shouldSwitch = true;
                            break;
                        }}
                    }} else if (dir == "desc") {{
                        if (xVal < yVal) {{
                            shouldSwitch = true;
                            break;
                        }}
                    }}
                }}
                if (shouldSwitch) {{
                    rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                    switching = true;
                    dir = dir == "asc" ? "desc" : "asc";
                }}
            }}
        }}
    </script>
</head>
<body>
    <h1>{title}</h1>
    <table id="dataTable">
"""

    # Header
    html += "<tr>"
    for col in data.columns:
        html += f"<th onclick=\"sortTable({list(data.columns).index(col)})\">{col}</th>"
    html += "</tr>"

    # Data rows
    for idx, row in data.iterrows():
        html += "<tr>"
        for val in row:
            if isinstance(val, float):
                html += f"<td>{val:.4f}</td>"
            else:
                html += f"<td>{val}</td>"
        html += "</tr>"

    html += """
    </table>
    <p><em>Click en los headers para ordenar</em></p>
</body>
</html>
"""

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info(f"  ✓ {filename}")

# Generar rankings
pe_data = ratios_df[ratios_df['pe'].notna()].sort_values('pe').head(50)[['ticker', 'empresa', 'sector', 'precio', 'pe']].round(2)
generate_html_ranking("Screener Financiero - Ranking P/E", pe_data, "screener_ranking_pe.html")

roe_data = ratios_df[ratios_df['roe'].notna()].sort_values('roe', ascending=False).head(50)[['ticker', 'empresa', 'sector', 'roe', 'margen_neto']].round(4)
generate_html_ranking("Screener Financiero - Ranking ROE", roe_data, "screener_ranking_roe.html")

margen_data = ratios_df[ratios_df['margen_neto'].notna()].sort_values('margen_neto', ascending=False).head(50)[['ticker', 'empresa', 'sector', 'margen_neto']].round(4)
generate_html_ranking("Screener Financiero - Ranking Margen Neto", margen_data, "screener_ranking_margen.html")

# ============================================================================
# PASO 5: RESUMEN
# ============================================================================

logger.info("\n" + "="*70)
logger.info("SCREENER FINAL GENERADO")
logger.info("="*70)
logger.info(f"Excel: screener_final.xlsx (7 tabs)")
logger.info(f"Resumen: screener_summary.txt")
logger.info(f"Rankings HTML:")
logger.info(f"  - screener_ranking_pe.html")
logger.info(f"  - screener_ranking_roe.html")
logger.info(f"  - screener_ranking_margen.html")
logger.info("="*70 + "\n")

print("\n✓ FASE 5 COMPLETADA: Screener final generado")
print(f"  - Excel: screener_final.xlsx")
print(f"  - Resumen: screener_summary.txt")
print(f"  - Rankings: 3 archivos HTML")
print(f"  - Total: {len(ratios_df)} acciones analizadas")
