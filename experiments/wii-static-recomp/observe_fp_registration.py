"""Read the second constructor's actual guarded bias operands without changing PPC objects."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/observe_fp_initializer.py')
body = parent.read_text().replace('mass-fp32-playrecord-boot','mass-playrecord-dec-boot').replace(
    'mass-fp-initializer-observer','mass-fp-registration-observer').replace(
    'audit_fp32_playrecord_boot.py','audit_playrecord_dec_boot.py').replace(
    '0x8000c2f4','0x80015234').replace('pc=8000c2f4','pc=80015234').replace(
    '0x8052915c','0x80529184').replace('0x80529158','0x80529180')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
