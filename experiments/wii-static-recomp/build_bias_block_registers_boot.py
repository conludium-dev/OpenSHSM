"""Reuse the measured aliasing opcode after conservative source-block analysis."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_bias_constructors_boot.py')
body = parent.read_text().replace('bias_constructor_lowering','bias_block_register_lowering').replace(
    'mass-fp-registration-boot','mass-bias-blocks-boot').replace(
    'mass-bias-constructors-boot','mass-bias-block-registers-boot').replace(
    'audit_fp_registration_boot.py','audit_bias_blocks_boot.py').replace(
    'SHSM_BIAS_CONSTRUCTORS_DISABLED','SHSM_BIAS_BLOCK_REGISTERS_DISABLED').replace('0x80017480','0x800d7510')
body = body.replace("('audit_bias_blocks_boot.py',)","('audit_bias_blocks_boot.py','verify_fsubs_second.py')")
body = body.replace('Only constructor prefixes whose original byte/data flow yields measured signed-int4330 operands.',
    'Fresh source-block dataflow for measured register opcodes; runtime operand/profile guards unchanged.')
body = body.replace('91 static matches do not mean91 whole-function behavioral oracles or completed startup.',
    '94 static admitted-family sites; one newly lowered aliasing opcode, not94 whole-function proofs.')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
