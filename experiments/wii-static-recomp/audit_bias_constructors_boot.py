"""Reproduce the complete bulk lowering and verify the actual new startup boundary."""
from pathlib import Path
import ast
from bias_constructor_lowering import select, lower
import subprocess

subprocess.run(['python3','experiments/wii-static-recomp/verify_bias_constructor_selection.py'],check=True)

parent = Path('experiments/wii-static-recomp/audit_fp_registration_boot.py')
body = parent.read_text().replace("output = root / 'mass-fp-registration-boot'", "output = root / 'mass-bias-constructors-boot'").replace(
    "base = root / 'mass-playrecord-dec-boot'", "base = root / 'mass-fp-registration-boot'").replace(
    'verify_fp_registration_native.py','verify_bias_constructors_native.py').replace(
    'build_fp_registration_boot.py','build_bias_constructors_boot.py')
node = next(node for node in ast.parse(body).body if isinstance(node,ast.For)
    and isinstance(node.target,ast.Tuple) and any(isinstance(target,ast.Name) and target.id == 'row' for target in node.target.elts))
body = body.replace(ast.get_source_segment(body,node),'''dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
sites = select(dol,root / 'dtk-output/asm')
assert sites == build['sites'] and len(sites) == 91
assert build['loweringSha256'] == sha(experiment / 'bias_constructor_lowering.py')
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
assert changed == build['changes'] and sum(map(len,changed.values())) == 89
header = __import__('struct').unpack('>64I',dol[:256])
for site in sites:
    path = root / 'dtk-output/asm' / f"auto_fn_{site['function']:08X}_text.s"
    text = path.read_text()
    marker = __import__('re').search(r'# 0x([0-9A-Fa-f]+)\\.\\.0x[0-9A-Fa-f]+ \\| size: 0x4\\n.section .ctors',text)
    assert marker,path
    address = int(marker[1],16)
    section = next(i for i in range(18) if header[18+i] <= address < header[18+i]+header[36+i])
    assert int.from_bytes(dol[header[section]+address-header[18+section]:header[section]+address-header[18+section]+4],'big') == site['function']
''')
start,end = body.index('wrapper = '),body.index("for name in ('mass_boot.cpp'")
body = body[:start] + "assert (output / 'boot-wrapper.cpp').read_bytes() == (base / 'boot-wrapper.cpp').read_bytes()\n" + body[end:]
body = body.replace('SHSM_FP_REGISTRATION_DISABLED','SHSM_BIAS_CONSTRUCTORS_DISABLED').replace(
    "assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']", "assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['disabled']").replace(
    'pc=80015234 lr=8021e8f4 msr=a032','pc=80017480 lr=8021e8f4 msr=a032').replace(
    'address=8001526c opcode=ec000828','address=800174a8 opcode=ec000828')
body = body.replace("boundary = next(line", "assert 'BOOT_BOUNDARY pc=801f4ff8 lr=80087de4 msr=a032' in logs['live']\nassert 'address=801f5028 opcode=fc010040' in logs['live']\nboundary = next(line")
body = body.replace('registration-boot-audit.json','bias-constructors-audit.json').replace(
    'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED','BULK89_BYTE_DATAFLOW_CHECKED_BIAS_SITES_BOOT_CONTINUED').replace(
    'One arithmetic body and read-only return observation;124 objects retained.','89 newly lowered arithmetic bodies; all other PPC source bytes and headers unchanged.').replace(
    'PASS original constructor/native128/global records/return/one-object delta','PASS bulk89 constructors/dataflow-original-byte-ctor checks/native128/global records/return/exact delta')
exec(compile(body,str(parent),'exec'),{'__file__':__file__,'select':select,'lower':lower})
