"""Continue the existing module through the three measured operations of the next initializer."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_bias_constructors_boot.py')
body = parent.read_text().replace('bias_constructor_lowering', 'bias_alias_initializer_lowering').replace(
    'mass-fp-registration-boot', 'mass-multiply-register-boot').replace(
    'mass-bias-constructors-boot', 'mass-bias-alias-initializer-boot').replace(
    'audit_fp_registration_boot.py', 'audit_multiply_register_boot.py').replace(
    'SHSM_BIAS_CONSTRUCTORS_DISABLED', 'SHSM_BIAS_ALIAS_INITIALIZER_DISABLED').replace('0x80017480', '0x800d8dc4')
body = body.replace("('audit_multiply_register_boot.py',)",
    "('audit_multiply_register_boot.py','verify_fsubs_alias.py','verify_single_arithmetic_native.py','verify_single_arithmetic_targeted.py')")
body = body.replace('Only constructor prefixes whose original byte/data flow yields measured signed-int4330 operands.',
    'One byte/dataflow-checked initializer bias conversion plus two exact previously measured arithmetic words.')
body = body.replace('91 static matches do not mean91 whole-function behavioral oracles or completed startup.',
    'Three arithmetic instruction replacements, not whole-constructor or first-screen proof.')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
