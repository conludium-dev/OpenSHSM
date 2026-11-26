"""Reproduce the exact lowering and check fresh execution and unchanged startup data."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/audit_fp_registration_boot.py')
body = parent.read_text().replace("output = root / 'mass-fp-registration-boot'", "output = root / 'mass-bias-alias-initializer-boot'").replace(
    "base = root / 'mass-playrecord-dec-boot'", "base = root / 'mass-multiply-register-boot'").replace(
    'verify_fp_registration_native.py', 'verify_fsubs_alias.py').replace(
    'build_fp_registration_boot.py', 'build_bias_alias_initializer_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.For)
    and isinstance(node.target, ast.Tuple) and any(isinstance(target, ast.Name) and target.id == 'row' for target in node.target.elts))
body = body.replace(ast.get_source_segment(body, node), '''from bias_alias_initializer_lowering import select, lower
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
sites = select(dol,root / 'dtk-output/asm')
assert len(sites) == 1 and sites == build['sites']
assert build['loweringSha256'] == sha(experiment / 'bias_alias_initializer_lowering.py')
changed = []
for row,old in zip(build['records'],prior['records']):
    assert row['file'] == old['file']
    expected,changes = lower(Path(old['source']).read_text(),dol,sites)
    if changes:
        assert len(changes) == 3 and changes == build['changes'][row['file']]
        assert row['object'] != old['object']
        changed.append(row['file'])
    else:
        assert row['object'] == old['object'] and row['source'] == old['source']
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert len(changed) == 1
''')
start, end = body.index("assert (output / 'fp_registration_probe.h')"), body.index("for name in ('mass_boot.cpp'")
body = body[:start] + "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()\n" + body[end:]
body = body.replace('SHSM_FP_REGISTRATION_DISABLED', 'SHSM_BIAS_ALIAS_INITIALIZER_DISABLED').replace(
    "assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']", "assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['disabled']").replace(
    'pc=80015234 lr=8021e8f4 msr=a032', 'pc=800d8dc4 lr=8021e8f4 msr=a032').replace(
    'address=8001526c opcode=ec000828', 'address=800d8df0 opcode=ec211828')
body = body.replace("for log in logs.values():", "assert 'address=800d8df0 opcode=ec211828' in logs['disabled']\nassert 'address=800d8dfc opcode=ec020028' in logs['live']\nfor log in logs.values():")
body = body.replace('registration-boot-audit.json', 'bias-alias-initializer-audit.json').replace(
    'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED', 'ORIGINAL_ALIAS_BIAS128_AND_REUSED_ARITHMETIC_BOOT_CONTINUED').replace(
    'One arithmetic body and read-only return observation;124 objects retained.', 'Three measured operations changed in one object;124 retained, no control-flow or backend changes.').replace(
    'Same128 original function cases, global records/destructor-chain ordering/lanes/status/return.', 'Original bias primitive128 result/lanes/status/operands matched; subsequent exact division and multiplication reuse earlier oracles.').replace(
    'PASS original constructor/native128/global records/return/one-object delta', 'PASS alias-bias128/three-operations/one-object delta')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
