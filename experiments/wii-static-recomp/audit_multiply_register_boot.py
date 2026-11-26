"""Audit reproduced dispatch, exact original body delta, and fresh startup execution."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/audit_fp_registration_boot.py')
body = parent.read_text().replace("output = root / 'mass-fp-registration-boot'", "output = root / 'mass-multiply-register-boot'").replace(
    "base = root / 'mass-playrecord-dec-boot'", "base = root / 'mass-bias-block-registers-boot'").replace(
    'verify_fp_registration_native.py','verify_multiply_register.py').replace(
    'build_fp_registration_boot.py','build_multiply_register_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.For)
    and isinstance(node.target,ast.Tuple) and any(isinstance(target,ast.Name) and target.id == 'row' for target in node.target.elts))
body = body.replace(ast.get_source_segment(body,node),'''import re
for verifier in ('verify_multiply_register_targeted.py','verify_multiply_register_contract.py'):
    subprocess.run(['python3',str(experiment / verifier)],check=True)
component = root / 'multiply-register-component'
assert (output / 'multiply_register_adapter.h').read_bytes() == (component / 'multiply_register_adapter.h').read_bytes()
assert (output / 'single_arithmetic_adapter.h').read_bytes() == (experiment / 'single_arithmetic_adapter.h').read_bytes()
for row,old in zip(build['records'],prior['records']):
    assert row['file'] == old['file']
    expected = Path(old['source']).read_text()
    if row['file'] == 'output_26.cpp':
        pattern = re.compile(r'(    // 0x800D7570: EC010032\\n)(.*?)(?=    \\+\\+ctx\\.inst_count;\\nloc_)',re.S)
        assert len(pattern.findall(expected)) == 1
        matched = pattern.search(expected)
        assert 'experiment_ni_guard' in matched[2] and 'fmuls' in matched[2]
        after = '    if (std::getenv("SHSM_MULTIPLY_REGISTER_DISABLED")) { nwii::runtime::experiment_ni_guard(ctx, 0xec010032, 0x800d7570); }\\n    nwii::runtime::experiment_multiply_register(ctx, 0xec010032);\\n'
        expected = '#include "multiply_register_adapter.h"\\n' + pattern.sub(lambda match: match[1] + after,expected)
        assert row['object'] != old['object']
    else:
        assert row['object'] == old['object'] and row['source'] == old['source']
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
''')
start,end = body.index('wrapper = '),body.index("for name in ('mass_boot.cpp'")
body = body[:start] + "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()\n" + body[end:]
body = body.replace('SHSM_FP_REGISTRATION_DISABLED','SHSM_MULTIPLY_REGISTER_DISABLED').replace(
    "assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']", "assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['disabled']").replace(
    'pc=80015234 lr=8021e8f4 msr=a032','pc=800d7510 lr=8021e8f4 msr=a032').replace(
    'address=8001526c opcode=ec000828','address=800d7570 opcode=ec010032')
body = body.replace('registration-boot-audit.json','multiply-register-boot-audit.json').replace(
    'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED','EXACT_REGISTER_FMULS1152_AND_DIV_CONTROL1152_NATIVE_BOOT_CONTINUED').replace(
    'One arithmetic body and read-only return observation;124 objects retained.','One exact fmuls body changed;124 objects retained, no guest register remapping.').replace(
    'Same128 original function cases, global records/destructor-chain ordering/lanes/status/return.','1152 new original multiply cases plus1152 original division controls/result-lanes-status match;12 atomic refusals andUBSan2304.').replace(
    'PASS original constructor/native128/global records/return/one-object delta','PASS multiply-register1152/div-control1152/exact one-object delta')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
