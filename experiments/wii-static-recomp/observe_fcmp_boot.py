"""Read actual comparison operands/status, retaining all existing PPC objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/observe_fp_initializer.py')
body = parent.read_text().replace('mass-fp32-playrecord-boot','mass-bias-constructors-boot').replace(
    'mass-fp-initializer-observer','mass-fcmp-observer').replace(
    'audit_fp32_playrecord_boot.py','audit_bias_constructors_boot.py').replace(
    '0x8000c2f4','0x801f4ff8').replace('0x8021e8f4','0x80087de4').replace(
    'pc=8000c2f4 lr=8021e8f4','pc=801f4ff8 lr=80087de4')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
