"""Audit exact register-variant lowering and actual progression to division."""
from pathlib import Path
import ast
from bias_register_variant_lowering import select, lower

parent = Path('experiments/wii-static-recomp/audit_fp_registration_boot.py')
body = parent.read_text().replace("output = root / 'mass-fp-registration-boot'", "output = root / 'mass-bias-register-boot'").replace(
    "base = root / 'mass-playrecord-dec-boot'", "base = root / 'mass-fcmp-finite-boot'").replace(
    'verify_fp_registration_native.py','verify_fsubs_variant.py').replace(
    'build_fp_registration_boot.py','build_bias_register_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.For)
    and isinstance(node.target,ast.Tuple) and any(isinstance(target,ast.Name) and target.id == 'row' for target in node.target.elts))
body = body.replace(ast.get_source_segment(body,node),'''dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
sites = [site for site in select(dol,root / 'dtk-output/asm') if site['opcode'] == 0xec401828]
assert sites == build['sites'] and len(sites) == 1
assert build['loweringSha256'] == sha(experiment / 'bias_register_variant_lowering.py')
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
assert set(changed) == {'output_20.cpp'}
''')
start,end = body.index('wrapper = '),body.index("for name in ('mass_boot.cpp'")
body = body[:start] + "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()\n" + body[end:]
body = body.replace('SHSM_FP_REGISTRATION_DISABLED','SHSM_BIAS_VARIANTS_DISABLED').replace(
    "assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']", "assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['disabled']").replace(
    'pc=80015234 lr=8021e8f4 msr=a032','pc=800a8ed8 lr=8021e8f4 msr=a032').replace(
    'address=8001526c opcode=ec000828','address=800a8f14 opcode=ec401828')
body = body.replace('boundary = next(line',"assert 'address=800a8f20 opcode=ec220824' in logs['live']\nboundary = next(line")
body = body.replace('registration-boot-audit.json','bias-register-boot-audit.json').replace(
    'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED','SOURCE_REG_VARIANT128_NATIVE_BOOT_REACHES_FDIVS').replace(
    'One arithmetic body and read-only return observation;124 objects retained.','One register-variant arithmetic body changed;124 objects retained; verified primitive, not whole constructor.').replace(
    'Same128 original function cases, global records/destructor-chain ordering/lanes/status/return.','Original prefix128 register-variant result/lanes/status/operand preservation; division/multiplication not admitted.').replace(
    'PASS original constructor/native128/global records/return/one-object delta','PASS register variant/original128/exact one-object delta')
exec(compile(body,str(parent),'exec'),{'__file__':__file__,'select':select,'lower':lower})
