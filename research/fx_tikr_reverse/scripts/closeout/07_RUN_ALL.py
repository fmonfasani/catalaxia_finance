import subprocess, sys
from pathlib import Path

scripts=[
"00_DECISION_CONFIG.py",
"01_LOCATE_INPUTS.py",
"02_TIKR_PROVENANCE_AUDIT.py",
"03_COMPARE_TIKR.py",
"04_ROBUSTNESS.py",
"05_VALIDATE.py",
"06_CERTIFY_GATE.py",
]

for s in scripts:
    print("\n"+"="*70)
    print(s)
    print("="*70)
    r=subprocess.run([sys.executable,str(Path(__file__).parent/s)])
    if r.returncode != 0:
        print(f"STOP at {s}: exit {r.returncode}")
        sys.exit(r.returncode)

print("\nENGINEERING CLOSEOUT COMPLETE")
