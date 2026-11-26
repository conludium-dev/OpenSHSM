"""Capture the exact new fmuls register form and the retained original division control."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_single_arithmetic_dolphin.py')
body = parent.read_text().replace('dolphin-single-arithmetic','dolphin-multiply-register').replace(
    'run_single_arithmetic_dolphin.ps1','run_multiply_register_dolphin.ps1').replace(
    '0x800a8f30','0x800d7570').replace('0x800a8f34','0x800d7574').replace('ec000072','ec010032')
body = body.replace('2 if operation == 0 else 0','2 if operation == 0 else 1').replace(
    'dform(50,1,4,(pair % 16) * 8)','dform(50,1 if operation == 0 else 0,4,(pair % 16) * 8)')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
