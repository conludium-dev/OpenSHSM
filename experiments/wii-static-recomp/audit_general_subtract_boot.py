"""Audit the exact instruction delta and fresh startup with prior data contracts intact."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/audit_fp_registration_boot.py')
body = parent.read_text().replace("output = root / 'mass-fp-registration-boot'", "output = root / 'mass-general-subtract-boot'").replace(
    "base = root / 'mass-playrecord-dec-boot'", "base = root / 'mass-bias-alias-initializer-boot'").replace(
    'verify_fp_registration_native.py', 'verify_general_subtract_native.py').replace(
    'build_fp_registration_boot.py', 'build_general_subtract_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.For)
    and isinstance(node.target, ast.Tuple) and any(isinstance(target, ast.Name) and target.id == 'row' for target in node.target.elts))
body = body.replace(ast.get_source_segment(body, node), '''from general_subtract_lowering import lower
for verifier in ('verify_general_subtract_targeted.py','verify_general_subtract_contract.py'):
    subprocess.run(['python3',str(experiment / verifier)],check=True)
assert (output / 'general_subtract_adapter.h').read_bytes() == (experiment / 'general_subtract_adapter.h').read_bytes()
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
changed = []
for row,old in zip(build['records'],prior['records']):
    assert row['file'] == old['file']
    expected,changes = lower(Path(old['source']).read_text(),dol)
    again,second = lower(expected,dol)
    assert again == expected and not second
    if changes:
        assert changes == [{'address':0x800d8dfc,'opcode':0xec020028}] and row['object'] != old['object']
        changed.append(row['file'])
    else:
        assert row['object'] == old['object'] and row['source'] == old['source']
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert changed == ['output_26.cpp']
''')
start, end = body.index("assert (output / 'fp_registration_probe.h')"), body.index("for name in ('mass_boot.cpp'")
body = body[:start] + "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()\n" + body[end:]
body = body.replace('SHSM_FP_REGISTRATION_DISABLED', 'SHSM_GENERAL_SUBTRACT_DISABLED').replace(
    "assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']", "assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['disabled']").replace(
    'pc=80015234 lr=8021e8f4 msr=a032', 'pc=800d8dc4 lr=8021e8f4 msr=a032').replace(
    'address=8001526c opcode=ec000828', 'address=800d8dfc opcode=ec020028')
body = body.replace('registration-boot-audit.json', 'general-subtract-boot-audit.json').replace(
    'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED', 'ORIGINAL_GENERAL_SUBTRACT5120_RUNS_NATIVE_BOOT_CONTINUED').replace(
    'One arithmetic body and read-only return observation;124 objects retained.', 'One exact subtraction body changed;124 objects retained, no wrapper/backend change.').replace(
    'Same128 original function cases, global records/destructor-chain ordering/lanes/status/return.', 'Raw1024 and expanded4096 original runs/result/paired-lanes/FPSCR/preserved operand;12 refusals andUBSan5120.').replace(
    'PASS original constructor/native128/global records/return/one-object delta', 'PASS general-subtract5120/one-object delta')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
