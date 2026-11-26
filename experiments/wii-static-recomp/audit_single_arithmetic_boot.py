"""Audit exact three-operation integration and fresh constructor continuation."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/audit_fp_registration_boot.py')
body = parent.read_text().replace("output = root / 'mass-fp-registration-boot'", "output = root / 'mass-single-arithmetic-boot'").replace(
    "base = root / 'mass-playrecord-dec-boot'", "base = root / 'mass-bias-register-boot'").replace(
    'verify_fp_registration_native.py','verify_single_arithmetic_native.py').replace(
    'build_fp_registration_boot.py','build_single_arithmetic_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.For)
    and isinstance(node.target,ast.Tuple) and any(isinstance(target,ast.Name) and target.id == 'row' for target in node.target.elts))
body = body.replace(ast.get_source_segment(body,node),'''import re
for verifier in ('verify_single_arithmetic_targeted.py','verify_single_arithmetic_contract.py','verify_fsubs_second.py'):
    subprocess.run(['python3',str(experiment / verifier)],check=True)
for row,old in zip(build['records'],prior['records']):
    assert row['file'] == old['file']
    expected = Path(old['source']).read_text()
    if row['file'] == 'output_20.cpp':
        pattern = re.compile(r'(    // 0x(800A8F20|800A8F30): (EC220824|EC000072)\\n)(.*?)(?=    \\+\\+ctx\\.inst_count;\\nloc_)',re.S)
        assert len(pattern.findall(expected)) == 2
        def arithmetic(match):
            assert 'experiment_ni_guard' in match[4] and ('fdivs' in match[4] or 'fmuls' in match[4])
            address,opcode = int(match[2],16),int(match[3],16)
            return match[1] + f'    if (std::getenv("SHSM_SINGLE_ARITHMETIC_DISABLED")) {{ nwii::runtime::experiment_ni_guard(ctx, 0x{opcode:08x}, 0x{address:08x}); }}\\n    nwii::runtime::experiment_single_arithmetic(ctx, 0x{opcode:08x});\\n'
        expected = pattern.sub(arithmetic,expected)
        before = '    nwii::runtime::experiment_ni_guard(ctx, 0xec421828, 0x800a8f2c);\\n    ctx.fpr[2] = (float)(ctx.fpr[2] - ctx.fpr[3]); // fsubs'
        assert expected.count(before) == 1
        expected = '#include "single_arithmetic_adapter.h"\\n' + expected.replace(before,'    nwii::runtime::experiment_fsubs_integer_bias(ctx, 0xec421828);')
        assert row['object'] != old['object']
    else:
        assert row['object'] == old['object'] and row['source'] == old['source']
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
assert (output / 'single_arithmetic_adapter.h').read_bytes() == (experiment / 'single_arithmetic_adapter.h').read_bytes()
''')
start,end = body.index('wrapper = '),body.index("for name in ('mass_boot.cpp'")
body = body[:start] + "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()\n" + body[end:]
body = body.replace('SHSM_FP_REGISTRATION_DISABLED','SHSM_SINGLE_ARITHMETIC_DISABLED').replace(
    "assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']", "assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['disabled']").replace(
    'pc=80015234 lr=8021e8f4 msr=a032','pc=800a8ed8 lr=8021e8f4 msr=a032').replace(
    'address=8001526c opcode=ec000828','address=800a8f20 opcode=ec220824')
body = body.replace('boundary = next(line',"assert 'BOOT_BOUNDARY pc=800bb24c lr=800bb24c msr=a032' in logs['live']\nassert 'address=800bb268 opcode=ec000828' in logs['live']\nboundary = next(line")
body = body.replace('registration-boot-audit.json','single-arithmetic-boot-audit.json').replace(
    'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED','ORIGINAL_SINGLE_ARITHMETIC2304_SECOND_SUB128_NATIVE_BOOT_CONTINUED').replace(
    'One arithmetic body and read-only return observation;124 objects retained.','Two arithmetic bodies and captured second bias subtraction;124 objects retained, no full constructor behavioral oracle.').replace(
    'Same128 original function cases, global records/destructor-chain ordering/lanes/status/return.','Original raw2048 plus targeted256 result/lanes/FPSCR comparisons; second subtraction128/UBSan2304/20 guard contracts.').replace(
    'PASS original constructor/native128/global records/return/one-object delta','PASS single arithmetic2304/second subtraction128/exact three-body one-object delta')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
