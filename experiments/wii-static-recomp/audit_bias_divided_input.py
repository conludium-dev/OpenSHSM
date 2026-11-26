"""Verify the read-only observation at the second conversion with all PPC objects retained."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/audit_constructor_budget.py')
body = parent.read_text().replace('mass-divide-initializer-boot', 'mass-bias-gpr-boot').replace(
    'mass-constructor-budget-observer', 'mass-bias-divided-input-observer').replace(
    "observation['builderSha256'] == sha(experiment / 'observe_constructor_budget.py')",
    "observation['builderSha256'] == sha(experiment / 'observe_bias_divided_input.py')").replace(
    'address=8017ad30 opcode=ec201028', 'address=8017ad4c opcode=ec001028').replace(
    "operands.split()[1] == '4330000080000210'", "operands.split()[1] == '4330000080000058'").replace(
    'PASS_CALL_BUDGET40000_SAME125_PRIOR_DATA', 'PASS_READONLY_SECOND_BIAS_SAME125_PRIOR_DATA')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
