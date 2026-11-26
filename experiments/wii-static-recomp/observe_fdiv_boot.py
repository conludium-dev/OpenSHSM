"""Read actual division operands after genuine source integer conversion."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/observe_fp_initializer.py')
body = parent.read_text().replace('mass-fp32-playrecord-boot','mass-bias-register-boot').replace(
    'mass-fp-initializer-observer','mass-fdiv-observer').replace(
    'audit_fp32_playrecord_boot.py','audit_bias_register_boot.py').replace(
    '0x8000c2f4','0x800a8ed8').replace('pc=8000c2f4','pc=800a8ed8').replace(
    'context.fpr[0]','context.fpr[2]').replace('context.ps1[0]','context.ps1[2]')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
