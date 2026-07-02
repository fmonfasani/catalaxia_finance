"""Run IR discovery for all 56 BYMA companies"""
import sys, warnings
sys.path.insert(0, r'scripts/tickets/cnv/scripts/cnv_ir')
warnings.filterwarnings("ignore")

from discovery import descubrir_eeff
from catalogo_ir import CATALOGO

print(f"{'Ticker':<8}{'EEFF URLs':<10}{'Best URL':<65}")
print("-" * 83)
ok = 0
for tk in sorted(CATALOGO):
    pdfs = descubrir_eeff(tk, CATALOGO)
    if pdfs:
        ok += 1
        print(f"{tk:<8}{len(pdfs):<5}{pdfs[0][:65]}")
    else:
        print(f"{tk:<8}0")
print(f"\nOK: {ok}/{len(CATALOGO)}")
