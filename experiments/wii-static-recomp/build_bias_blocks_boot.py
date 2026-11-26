"""Apply the existing measured operation to newly reconstructed straight-line blocks."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_bias_constructors_boot.py')
body = parent.read_text().replace('bias_constructor_lowering','bias_block_lowering').replace(
    'mass-fp-registration-boot','mass-single-arithmetic-boot').replace(
    'mass-bias-constructors-boot','mass-bias-blocks-boot').replace(
    'audit_fp_registration_boot.py','audit_single_arithmetic_boot.py').replace(
    'SHSM_BIAS_CONSTRUCTORS_DISABLED','SHSM_BIAS_BLOCKS_DISABLED').replace('0x80017480','0x800bb1bc')
body = body.replace("('audit_single_arithmetic_boot.py',)","('audit_single_arithmetic_boot.py','verify_bias_block_selection.py')")
body = body.replace('Only constructor prefixes whose original byte/data flow yields measured signed-int4330 operands.',
    'Straight-line blocks with fresh byte/dataflow facts and runtime operand/profile checks; original calls unchanged.')
body = body.replace('91 static matches do not mean91 whole-function behavioral oracles or completed startup.',
    '92 static matches, one newly lowered post-call arithmetic site; not whole-function or completed startup proof.')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
