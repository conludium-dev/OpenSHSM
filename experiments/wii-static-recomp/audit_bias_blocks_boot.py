"""Audit the conservative post-call rule and fresh continuation to a register variant."""
from pathlib import Path
import ast
from bias_block_lowering import select, lower
import subprocess

subprocess.run(['python3','experiments/wii-static-recomp/verify_bias_block_selection.py'],check=True)
parent = Path('experiments/wii-static-recomp/audit_fp_registration_boot.py')
body = parent.read_text().replace("output = root / 'mass-fp-registration-boot'", "output = root / 'mass-bias-blocks-boot'").replace(
    "base = root / 'mass-playrecord-dec-boot'", "base = root / 'mass-single-arithmetic-boot'").replace(
    'verify_fp_registration_native.py','verify_fsubs_variant.py').replace(
    'build_fp_registration_boot.py','build_bias_blocks_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.For)
    and isinstance(node.target,ast.Tuple) and any(isinstance(target,ast.Name) and target.id == 'row' for target in node.target.elts))
body = body.replace(ast.get_source_segment(body,node),'''dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
sites = select(dol,root / 'dtk-output/asm')
assert sites == build['sites'] and len(sites) == 92
assert build['loweringSha256'] == sha(experiment / 'bias_block_lowering.py')
changed = {}
for row,old in zip(build['records'],prior['records']):
    assert row['file'] == old['file']
    expected,changes = lower(Path(old['source']).read_text(),dol,sites)
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if changes:
        changed[row['file']] = changes
        assert row['object'] != old['object'] and Path(row['object']).parent == output
    else:
        assert row['object'] == old['object'] and row['source'] == old['source']
assert changed == build['changes'] and sum(map(len,changed.values())) == 1
assert set(changed) == {'output_23.cpp'}
assert changed['output_23.cpp'][0]['address'] == 0x800bb268
assert changed['output_23.cpp'][0]['boundary'] == 'after-call'
''')
start,end = body.index('wrapper = '),body.index("for name in ('mass_boot.cpp'")
body = body[:start] + "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()\n" + body[end:]
body = body.replace('SHSM_FP_REGISTRATION_DISABLED','SHSM_BIAS_BLOCKS_DISABLED').replace(
    "assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']", "assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['disabled']").replace(
    'pc=80015234 lr=8021e8f4 msr=a032','pc=800bb24c lr=800bb24c msr=a032').replace(
    'address=8001526c opcode=ec000828','address=800bb268 opcode=ec000828')
body = body.replace('boundary = next(line',"assert 'BOOT_BOUNDARY pc=800d7510 lr=8021e8f4 msr=a032' in logs['live']\nassert 'address=800d7568 opcode=ec421828' in logs['live']\nboundary = next(line")
body = body.replace('registration-boot-audit.json','bias-blocks-boot-audit.json').replace(
    'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED','BYTE_DATAFLOW_POST_CALL_BIAS_BLOCK_NATIVE_BOOT_CONTINUED').replace(
    'One arithmetic body and read-only return observation;124 objects retained.','One post-call arithmetic body changed;124 objects retained, original calls/control flow unchanged.').replace(
    'Same128 original function cases, global records/destructor-chain ordering/lanes/status/return.','Existing measured numeric family reused; static block inference/runtime operand-profile guards, not full constructor proof.').replace(
    'PASS original constructor/native128/global records/return/one-object delta','PASS post-call block/reset8contracts/original128/exact one-object delta')
exec(compile(body,str(parent),'exec'),{'__file__':__file__,'select':select,'lower':lower})
