"""Retain rounding-boundary pairs while exercising the exact new register form."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_single_arithmetic_targeted.py')
outer = parent.read_text().replace('dolphin-single-arithmetic-targeted','dolphin-multiply-register-targeted').replace(
    'run_single_arithmetic_targeted.ps1','run_multiply_register_targeted.ps1')
marker = "exec(compile(outer,str(parent),'exec'),{**globals(),'__file__':__file__})"
assert outer.count(marker) == 1
changes = '''body = body.replace('0x800a8f30','0x800d7570').replace('0x800a8f34','0x800d7574').replace('ec000072','ec010032')
body = body.replace('2 if operation == 0 else 0','2 if operation == 0 else 1').replace(
    'dform(50,1,4,16 + operation * 512 + pair * 16)','dform(50,1 if operation == 0 else 0,4,16 + operation * 512 + pair * 16)')
'''
injection = "outer = outer.replace(\"exec(compile(body,str(parent),'exec'),{'__file__':__file__})\", " + repr(changes) + " + \"exec(compile(body,str(parent),'exec'),{'__file__':__file__})\")\n"
outer = outer.replace(marker,injection + marker)
exec(compile(outer,str(parent),'exec'),{'__file__':__file__})
