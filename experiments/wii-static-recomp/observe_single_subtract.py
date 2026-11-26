"""Read the next actual subtraction operands, without altering PPC objects or FP state."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/observe_fp_initializer.py')
body = parent.read_text().replace('mass-fp32-playrecord-boot','mass-single-arithmetic-boot').replace(
    'mass-fp-initializer-observer','mass-single-subtract-observer').replace(
    'audit_fp32_playrecord_boot.py','audit_single_arithmetic_boot.py').replace(
    '0x8000c2f4','0x800bb24c').replace('0x8021e8f4','0x800bb24c').replace(
    'pc=8000c2f4 lr=8021e8f4','pc=800bb24c lr=800bb24c')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
