"""Compare exact register routing at the targeted rounding boundaries."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_multiply_register.py')
body = parent.read_text().replace('dolphin-multiply-register','dolphin-multiply-register-targeted').replace(
    'build_multiply_register_dolphin.py','build_multiply_register_targeted.py').replace(
    'run_multiply_register_dolphin.ps1','run_multiply_register_targeted.ps1').replace('2048','256').replace('14336','1792')
# Counts occur in the underlying verifier templates, so specialize them before execution.
marker = "exec(compile(body,str(parent),'exec'),{'__file__':__file__})"
body = body.replace(marker,"body = body.replace('2048','256').replace('14336','1792')\n" + marker)
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
