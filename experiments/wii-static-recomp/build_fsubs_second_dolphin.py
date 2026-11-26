"""Capture the second original subtraction after the actual original division."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_fsubs_variant_dolphin.py')
body = parent.read_text().replace('dolphin-fsubs-variant','dolphin-fsubs-second').replace(
    'run_fsubs_variant_dolphin.ps1','run_fsubs_second_dolphin.ps1').replace(
    '0x800a8f18','0x800a8f30').replace('ec401828','ec421828').replace(
    "report['functionBytes'] = 64","report['functionBytes'] = 88").replace('first16','first22').replace(
    'fsubs f2,f0,f3','fsubs f2,f2,f3')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
