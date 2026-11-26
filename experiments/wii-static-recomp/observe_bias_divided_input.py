"""Observe the actual next bias operand without changing PPC objects or numeric state."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/observe_constructor_budget.py')
body = parent.read_text().replace('mass-divide-initializer-boot', 'mass-bias-gpr-boot').replace(
    'mass-constructor-budget-observer', 'mass-bias-divided-input-observer').replace(
    'audit_divide_initializer_boot.py', 'audit_bias_gpr_boot.py')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
