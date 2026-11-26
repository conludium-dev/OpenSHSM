"""Audit the exact selected source delta, diagnostic budget and fresh runtime continuation."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/audit_bias_blocks_boot.py')
body = parent.read_text()
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign)
    and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
    and node.value.func.attr == 'replace' and node.value.args
    and isinstance(node.value.args[0], ast.Constant) and node.value.args[0].value == 'boundary = next(line')
body = body.replace(ast.get_source_segment(body, node), '')
body = body.replace('bias_block_lowering', 'bias_gpr_producer_lowering').replace(
    'verify_bias_block_selection.py', 'verify_bias_gpr_selection.py').replace(
    'mass-bias-blocks-boot', 'mass-bias-gpr-boot').replace('mass-single-arithmetic-boot', 'mass-divide-initializer-boot').replace(
    'verify_fsubs_variant.py', 'verify_fsubs_gpr.py').replace('build_bias_blocks_boot.py', 'build_bias_gpr_boot.py').replace(
    'len(sites) == 92', 'len(sites) == 96').replace('output_23.cpp', 'output_47.cpp').replace('0x800bb268', '0x8017ad30').replace(
    "['boundary'] == 'after-call'", "['boundary'] == 'function-entry'").replace('SHSM_BIAS_BLOCKS_DISABLED', 'SHSM_BIAS_GPR_PRODUCERS_DISABLED').replace(
    'pc=800bb24c lr=800bb24c msr=a032', 'pc=8017ace8 lr=8021e8f4 msr=a032').replace(
    'address=800bb268 opcode=ec000828', 'address=8017ad30 opcode=ec201028')
marker = "exec(compile(body,str(parent),'exec'),{'__file__':__file__,'select':select,'lower':lower})"
assert body.count(marker) == 1
check = "assert (output / 'mass_boot.cpp').read_text() == (base / 'mass_boot.cpp').read_text().replace('if (++calls > 20000)', 'if (++calls > 40000)')"
injection = f"body = body.replace(\"for name in ('mass_boot.cpp',\", \"for name in (\")\nbody = body.replace(\"for name in ('fs_device.cpp'\", {check!r} + chr(10) + \"for name in ('fs_device.cpp'\")\n"
body = body.replace(marker, injection + marker)
body = body.replace('bias-blocks-boot-audit.json', 'bias-gpr-boot-audit.json').replace(
    'BYTE_DATAFLOW_POST_CALL_BIAS_BLOCK_NATIVE_BOOT_CONTINUED', 'BYTE_DATAFLOW_GPR_INVALIDATION_BIAS_NATIVE_BOOT_CONTINUED').replace(
    'One post-call arithmetic body changed;124 objects retained, original calls/control flow unchanged.', 'One arithmetic body changed;124 objects retained, diagnostic limit40000, original calls/control flow unchanged.').replace(
    'Existing measured numeric family reused; static block inference/runtime operand-profile guards, not full constructor proof.', 'Measured EC201028 original128 matched; known GPR destinations invalidated, old helper/operand-profile guards unchanged.').replace(
    'PASS post-call block/reset8contracts/original128/exact one-object delta', 'PASS GPR selection8/refusals/original128/exact one-object and budget delta')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
