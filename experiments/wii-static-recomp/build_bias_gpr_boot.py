"""Reuse measured bias arithmetic after conservative GPR-producer invalidation."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_bias_constructors_boot.py')
body = parent.read_text().replace('bias_constructor_lowering', 'bias_gpr_producer_lowering').replace(
    'mass-fp-registration-boot', 'mass-divide-initializer-boot').replace(
    'mass-bias-constructors-boot', 'mass-bias-gpr-boot').replace(
    'audit_fp_registration_boot.py', 'audit_divide_initializer_boot.py').replace('0x80017480', '0x8017ace8').replace(
    'SHSM_BIAS_CONSTRUCTORS_DISABLED', 'SHSM_BIAS_GPR_PRODUCERS_DISABLED')
body = body.replace("('audit_divide_initializer_boot.py',)",
    "('audit_divide_initializer_boot.py','audit_constructor_budget.py','verify_fsubs_gpr.py','verify_bias_gpr_selection.py')")
body = body.replace("fs_source = runtime / 'src/hle/devices/fs_device.cpp'", "replace(output / 'mass_boot.cpp', 'if (++calls > 20000)', 'if (++calls > 40000)')\nfs_source = runtime / 'src/hle/devices/fs_device.cpp'")
body = body.replace('Only constructor prefixes whose original byte/data flow yields measured signed-int4330 operands.',
    'Measured register form selected after invalidating known GPR-only destinations; existing FP operand guards retained.').replace(
    '91 static matches do not mean91 whole-function behavioral oracles or completed startup.',
    '96 static sites, one new lowering; not96 whole-function oracles. Diagnostic call limit40000 only.')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
