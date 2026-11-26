"""Retest the original whole-function oracle and operand guards on the bulk-lowered module."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fp_registration_native.py')
body = parent.read_text()
marker = "exec(compile(body,str(parent),'exec'),{'__file__':__file__})"
assert body.count(marker) == 1
body = body.replace(marker,"body = body.replace('mass-fp-registration-boot','mass-bias-constructors-boot').replace('build_fp_registration_boot.py','build_bias_constructors_boot.py')\n" + marker)
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
