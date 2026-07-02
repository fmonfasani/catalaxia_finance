"""Full cross-reference: ADR companies with both EDGAR and CNV data"""
import sqlite3
from collections import defaultdict

db = sqlite3.connect('data/screener.db')

# Best ADR candidates with both EDGAR data and CNV NetIncome
candidates = ['BBAR', 'CEPU', 'CRESY', 'LOMA', 'SUPV', 'TEO']

print("=== ADRs WITH EDGAR + CNV DATA ===")
for tk in candidates:
    cik = db.execute("SELECT cik FROM empresas WHERE ticker_ppal=? AND grupo='adr_arg'", (tk,)).fetchone()[0]
    edgar_ni = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND tag='ProfitLoss' AND taxonomia NOT LIKE 'yfinance'", (cik,)).fetchone()[0]
    edgar_div = db.execute("SELECT COUNT(*) FROM facts WHERE cik=? AND tag='DividendsPaidOrdinaryShares'", (cik,)).fetchone()[0]
    cnv_ni = db.execute("SELECT COUNT(*) FROM cnv_estados WHERE ticker=? AND concepto='NetIncome'", (tk,)).fetchone()[0]
    print(f"  {tk:<6} CIK={cik:<15} EDGAR_NI={edgar_ni} EDGAR_Div={edgar_div} CNV_NI={cnv_ni}")

# Pick BBAR (has 2 CNV NetIncome entries) and CRESY
for TICKER in ['BBAR', 'CRESY']:
    print(f"\n{'='*80}")
    print(f"ADR: {TICKER}")
    print('='*80)
    
    CIK = db.execute("SELECT cik FROM empresas WHERE ticker_ppal=? AND grupo='adr_arg'", (TICKER,)).fetchone()[0]
    
    # EDGAR IFRS data
    cur = db.execute("""
        SELECT tag, period_end, val FROM facts
        WHERE cik=? AND tag IN ('ProfitLoss', 'ProfitLossAttributableToOwnersOfParent', 
                                'DividendsPaidOrdinaryShares', 'DividendsPaidClassifiedAsFinancingActivities',
                                'RevenueAndOperatingIncome')
        ORDER BY period_end, tag
    """, (CIK,))
    edgar = defaultdict(dict)
    for r in cur:
        edgar[r[1]][r[0]] = r[2]
    
    print(f"\nEDGAR IFRS ({len(edgar)} periods):")
    print(f"{'Period':<15} {'Revenue':>22} {'ProfitLoss':>22} {'DivPaid':>22} {'Payout':>12}")
    for pe in sorted(edgar):
        d = edgar[pe]
        ni = d.get('ProfitLoss', d.get('ProfitLossAttributableToOwnersOfParent'))
        rev = d.get('RevenueAndOperatingIncome', '-')
        div = d.get('DividendsPaidOrdinaryShares', d.get('DividendsPaidClassifiedAsFinancingActivities', '-'))
        if ni:
            pay = f"{div/ni*100:>11.1f}%" if isinstance(div, float) and ni != 0 else 'N/A'
            rev_s = f"{rev:>22,.0f}" if isinstance(rev, float) else '-'
            print(f"{pe:<15} {rev_s:>22} {ni:>22,.0f} {div:>22,.0f} {pay:>12}" if isinstance(div, float) else f"{pe:<15} {rev_s:>22} {ni:>22,.0f} {'N/A':>22} {'N/A':>12}")
    
    # CNV data
    cur = db.execute("""
        SELECT concepto, period_end, valor FROM cnv_estados
        WHERE ticker=? AND concepto IN ('NetIncome', 'Revenue', 'EPS_basico')
        ORDER BY period_end, concepto
    """, (TICKER,))
    cnv = defaultdict(dict)
    for r in cur:
        cnv[r[1]][r[0]] = r[2]
    
    print(f"\nCNV AIF2 ({len(cnv)} periods):")
    print(f"{'Period':<15} {'Revenue':>22} {'NetIncome':>22} {'EPS':>12}")
    for pe in sorted(cnv):
        d = cnv[pe]
        ni = d.get('NetIncome', '-')
        rev = d.get('Revenue', '-')
        eps = d.get('EPS_basico', '-')
        ni_s = f"{ni:>22,.0f}" if isinstance(ni, float) else str(ni)
        rev_s = f"{rev:>22,.0f}" if isinstance(rev, float) else str(rev)
        eps_s = f"{eps:>12,.2f}" if isinstance(eps, float) else str(eps)
        print(f"{pe:<15} {rev_s:>22} {ni_s:>22} {eps_s:>12}")
    
    # CROSS-REFERENCE
    print(f"\nCROSS-REFERENCE: EDGAR_Div / CNV_NI")
    print(f"{'CNV_Period':<15} {'EDGAR_Period':<15} {'Div_EDGAR':>22} {'NI_CNV':>22} {'Payout':>12}")
    
    for pe_cnv in sorted(cnv):
        d_cnv = cnv[pe_cnv]
        cnv_ni = d_cnv.get('NetIncome')
        if not cnv_ni:
            continue
        
        # Find matching EDGAR period (same year, prefer June/Dec)
        pe_edgar = None
        for pe_e in sorted(edgar):
            if pe_e[:4] == pe_cnv[:4]:
                pe_edgar = pe_e
        
        if pe_edgar:
            d_edgar = edgar[pe_edgar]
            div = d_edgar.get('DividendsPaidOrdinaryShares', d_edgar.get('DividendsPaidClassifiedAsFinancingActivities'))
            if isinstance(div, float):
                payout = div / cnv_ni * 100
                print(f"{pe_cnv:<15} {pe_edgar:<15} {div:>22,.0f} {cnv_ni:>22,.0f} {payout:>11.1f}%")

db.close()
