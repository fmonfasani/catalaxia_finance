# -*- coding: utf-8 -*-
"""Definiciones compartidas de códigos CNV (sin ejecución — seguro de importar)."""
import re
CODE_MAP={
 '3000100':'revenue','3000200':'cogs','3009999':'gross_profit','3011600':'da',
 '3019999':'operating_income','3021400':'financial_income','3021500':'interest_expense',
 '3021800':'recpam','3029999':'pretax_income','3031100':'income_tax','3049999':'net_income',
 '3099999':'comprehensive_income','3240000':'net_change_cash','3241100':'cfo','3241200':'cfi',
 '3241300':'cff','8000000':'eps_basic','8000001':'eps_diluted','8000003':'ebit','8000004':'ebitda',
 '1122500':'cash','1121999':'receivables','1120100':'inventory','1139999':'assets_current',
 '1110100':'ppe','1119999':'assets_noncurrent','1999999':'assets','2299999':'equity',
 '2322200':'debt_current','2339999':'liabilities_current','2312300':'debt_noncurrent',
 '2399999':'liabilities','2210999':'capital','2211999':'reserves','2212999':'retained_earnings',
 '2211300':'minority_interest',
 '8000009':'cnv_roe','8000010':'cnv_roa','8000014':'cnv_margen_neto'}
NO_FACTOR={'eps_basic','eps_diluted','cnv_roe','cnv_roa','cnv_margen_neto'}
PAIR=re.compile(r'id="Nro"[^>]*>(\d+)</propiedad>\s*<propiedad id="Rubro"[^>]*>[^<]*</propiedad>\s*<propiedad id="Monto"[^>]*>\s*(-?[\d.,]+)')
