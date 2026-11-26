"""Retain the baseline JIT capture and enable FPRF tracking in a separate fixture."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_fcmp_jit_dolphin.py')
body = parent.read_text().replace('dolphin-fcmp-jit','dolphin-fcmp-jit-fprf').replace(
    'run_fcmp_jit_dolphin.ps1','run_fcmp_jit_fprf.ps1')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
