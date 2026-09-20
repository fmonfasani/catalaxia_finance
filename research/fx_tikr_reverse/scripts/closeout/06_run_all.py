"""
06_run_all.py
Orquestador del ciclo DEFINIR -> IMPLEMENTAR -> VERIFICAR.
"""
import subprocess, sys
from pathlib import Path

steps=[
    "01_contract.py",
    "02_build_quarterly_panel.py",
    "03_tikr_quarterly_stats.py",
    "04_backtest.py",
    "05_acceptance_gate.py",
]
for s in steps:
    print(f"\n===== {s} =====")
    r=subprocess.run([sys.executable, str(Path(__file__).parent/s)])
    if r.returncode not in (0,):
        print(f"STOP: {s} returned {r.returncode}")
        sys.exit(r.returncode)
print("\nDONE: evidence pipeline completed.")
