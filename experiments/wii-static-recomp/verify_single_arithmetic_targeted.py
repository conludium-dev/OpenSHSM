"""Reuse raw original capture/native checks for additional nontrivial numeric pairs."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_single_arithmetic_capture.py')
body = parent.read_text().replace('dolphin-single-arithmetic','dolphin-single-arithmetic-targeted').replace(
    'build_single_arithmetic_dolphin.py','build_single_arithmetic_targeted.py').replace(
    'run_single_arithmetic_dolphin.ps1','run_single_arithmetic_targeted.ps1').replace('2048','256').replace('14336','1792')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
parent = Path('experiments/wii-static-recomp/verify_single_arithmetic_native.py')
body = parent.read_text().replace('dolphin-single-arithmetic','dolphin-single-arithmetic-targeted').replace(
    "subprocess.run(['python3',str(experiment / 'verify_single_arithmetic_capture.py')],check=True)", '').replace('2048','256')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
