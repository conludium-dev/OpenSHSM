"""Read actual operands at the next guarded subtraction without changing guest state."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/observe_fp_initializer.py')
body = parent.read_text().replace('mass-fp32-playrecord-boot', 'mass-bias-alias-initializer-boot').replace(
    'mass-fp-initializer-observer', 'mass-general-subtract-observer').replace(
    'audit_fp32_playrecord_boot.py', 'audit_bias_alias_initializer_boot.py').replace(
    '0x8000c2f4', '0x800d8dc4').replace('pc=8000c2f4', 'pc=800d8dc4').replace(
    'context.fpr[1]', 'context.fpr[2]').replace('context.ps1[1]', 'context.ps1[2]').replace(
    'FP_INITIALIZER_OPERANDS', 'GENERAL_SUBTRACT_OPERANDS').replace('FP_INITIALIZER_', 'GENERAL_SUBTRACT_')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
