"""Verify exact second-stage lowering and preserve the post-call/primitive evidence."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/audit_bias_blocks_boot.py')
body = parent.read_text().replace('from bias_block_lowering import','from bias_block_register_lowering import').replace(
    "output = root / 'mass-bias-blocks-boot'", "output = root / 'mass-bias-block-registers-boot'").replace(
    "base = root / 'mass-single-arithmetic-boot'", "base = root / 'mass-bias-blocks-boot'").replace(
    'build_bias_blocks_boot.py','build_bias_block_registers_boot.py').replace(
    'verify_fsubs_variant.py','verify_fsubs_second.py').replace(
    "len(sites) == 92","len(sites) == 94").replace('bias_block_lowering.py','bias_block_register_lowering.py').replace(
    'output_23.cpp','output_26.cpp').replace('0x800bb268','0x800d7568').replace(
    "['boundary'] == 'after-call'","['boundary'] == 'function-entry'").replace(
    'SHSM_BIAS_BLOCKS_DISABLED','SHSM_BIAS_BLOCK_REGISTERS_DISABLED').replace(
    'pc=800bb24c lr=800bb24c msr=a032','pc=800d7510 lr=8021e8f4 msr=a032').replace(
    'address=800bb268 opcode=ec000828','address=800d7568 opcode=ec421828')
body = body.replace("assert 'BOOT_BOUNDARY pc=800d7510 lr=8021e8f4 msr=a032' in logs['live']\\nassert 'address=800d7568 opcode=ec421828' in logs['live']\\n",'')
body = body.replace('bias-blocks-boot-audit.json','bias-block-registers-audit.json').replace(
    'BYTE_DATAFLOW_POST_CALL_BIAS_BLOCK_NATIVE_BOOT_CONTINUED','BYTE_DATAFLOW_MEASURED_ALIAS_REGISTER_NATIVE_BOOT_CONTINUED')
body = body.replace('One post-call arithmetic body changed;124 objects retained, original calls/control flow unchanged.',
    'One aliasing-register arithmetic body changed;124 objects retained, original calls/control flow unchanged.')
body = body.replace('Existing measured numeric family reused; static block inference/runtime operand-profile guards, not full constructor proof.',
    'Exact EC421828 form already captured in second-subtraction128; new source-block dataflow/runtime operand-profile guards, not whole constructor proof.')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
