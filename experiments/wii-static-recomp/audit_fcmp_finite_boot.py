"""Audit the exact comparison body delta and freshly execute the existing startup module."""
from pathlib import Path
import ast

parent = Path('experiments/wii-static-recomp/audit_fp_registration_boot.py')
body = parent.read_text().replace("output = root / 'mass-fp-registration-boot'", "output = root / 'mass-fcmp-finite-boot'").replace(
    "base = root / 'mass-playrecord-dec-boot'", "base = root / 'mass-bias-constructors-boot'").replace(
    'verify_fp_registration_native.py','verify_fcmp_jit_finite.py').replace(
    'build_fp_registration_boot.py','build_fcmp_finite_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.For)
    and isinstance(node.target,ast.Tuple) and any(isinstance(target,ast.Name) and target.id == 'row' for target in node.target.elts))
body = body.replace(ast.get_source_segment(body,node),'''import re
for row,old in zip(build['records'],prior['records']):
    assert row['file'] == old['file']
    expected = Path(old['source']).read_text()
    if row['file'] == 'output_60.cpp':
        pattern = re.compile(r'(    // 0x801F5028: FC010040\\n)(.*?)(?=    \\+\\+ctx\\.inst_count;\\nloc_)',re.S)
        matched = pattern.search(expected)
        assert matched and 'experiment_ni_guard' in matched[2] and 'ctx.cr[0].so = un;' in matched[2]
        after = '    if (std::getenv("SHSM_FCMP_FINITE_DISABLED")) { nwii::runtime::experiment_ni_guard(ctx, 0xfc010040, 0x801f5028); }\\n    nwii::runtime::experiment_fcmp_finite(ctx, 0xfc010040);\\n'
        expected = '#include "fcmp_finite_adapter.h"\\n' + pattern.sub(lambda match: match[1] + after,expected)
        assert row['object'] != old['object']
    else:
        assert row['object'] == old['object'] and row['source'] == old['source']
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for name in ('fcmp_finite_adapter.h','fcmp_ordered_adapter.h'):
    assert (output / name).read_bytes() == (experiment / name).read_bytes()
''')
start,end = body.index('wrapper = '),body.index("for name in ('mass_boot.cpp'")
body = body[:start] + "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()\n" + body[end:]
body = body.replace('SHSM_FP_REGISTRATION_DISABLED','SHSM_FCMP_FINITE_DISABLED').replace(
    "assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']", "assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['disabled']").replace(
    'pc=80015234 lr=8021e8f4 msr=a032','pc=801f4ff8 lr=80087de4 msr=a032').replace(
    'address=8001526c opcode=ec000828','address=801f5028 opcode=fc010040')
body = body.replace('registration-boot-audit.json','fcmp-finite-boot-audit.json').replace(
    'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED','VERIFIED576_JIT_COMPARE_NATIVE_BOOT_CONTINUED').replace(
    'One arithmetic body and read-only return observation;124 objects retained.','One compare body changed;124 objects retained. No-NaN domain verified against original JIT576 cases.').replace(
    'Same128 original function cases, global records/destructor-chain ordering/lanes/status/return.','Original scalar compare only; NaN and other opcodes remain guarded, JIT IRQ/cache/whole function behavior not claimed.').replace(
    'PASS original constructor/native128/global records/return/one-object delta','PASS exact compare/JIT576/one-object delta')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
