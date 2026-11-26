"""Fresh execution plus exact source delta audit for the original constructor continuation."""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
base = root / 'mass-playrecord-dec-boot'
output = root / 'mass-fp-registration-boot'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3',str(experiment / 'verify_fp_registration_native.py')],check=True)
build = json.loads((output / 'build.json').read_text())
prior = json.loads((base / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_fp_registration_boot.py')
assert build['baseBuildSha256'] == sha(base / 'build.json')
assert build['executableSha256'] == sha(output / 'openshsm-mass-boot')
for path,digest in {**build['sourceHashes'],**build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == len(prior['records']) == 125
for row,old in zip(build['records'],prior['records']):
    assert row['file'] == old['file']
    expected = Path(old['source']).read_text()
    if row['file'] == 'output_2.cpp':
        expected = expected.replace('    nwii::runtime::experiment_ni_guard(ctx, 0xec000828, 0x8001526c);\n    ctx.fpr[0] = (float)(ctx.fpr[0] - ctx.fpr[1]); // fsubs',
            '    if (std::getenv("SHSM_FP_REGISTRATION_DISABLED")) { nwii::runtime::experiment_ni_guard(ctx, 0xec000828, 0x8001526c); }\n    nwii::runtime::experiment_fsubs_integer_bias(ctx, 0xec000828);')
        expected = expected.replace('loc_800152BC: ;','loc_800152BC: ;\n    if (ctx.msr == 0xa032 && nwii::runtime::stmSubmitted == 48) { std::cout << "FP_REGISTRATION_RETURN " << std::hex << ctx.fpscr << " " << nwii::runtime::bat_memory_read32(ctx,0x80529180) << " " << nwii::runtime::bat_memory_read32(ctx,0x80529184) << std::dec << std::endl; }')
        assert row['object'] != old['object']
    else:
        assert row['object'] == old['object'] and row['source'] == old['source']
    assert Path(row['source']).read_text() == expected
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path in base.glob('*.h'):
    assert path.read_bytes() == (output / path.name).read_bytes()
assert (output / 'fp_registration_probe.h').read_bytes() == (experiment / 'fp_registration_probe.h').read_bytes()
wrapper = (base / 'boot-wrapper.cpp').read_text().replace('int main(int argc, char** argv) {',
    '#include "fp_registration_probe.h"\nint main(int argc, char** argv) {\n    if (argc == 2 && std::string(argv[1]) == "--fp-registration-probe") { return experiment_fp_registration_probe(); }')
assert (output / 'boot-wrapper.cpp').read_text() == wrapper
for name in ('mass_boot.cpp','fs_device.cpp','di_device.cpp','es_device.cpp','stm_device.cpp','boot-quarantine.tsv'):
    assert (output / name).read_bytes() == (base / name).read_bytes()
seed = root / 'playrecord-fs-device/pc-owned-playrecord.bin'
seed_hash = sha(seed)
logs = {}
for mode in ('live','disabled'):
    env = {key:value for key,value in os.environ.items() if not key.startswith('SHSM_')}
    env.update(SHSM_PLAYRECORD_LAB_FILE=str(seed),SHSM_ES_TMD_PATH='work/private-game/disc/DATA/tmd.bin',
        SHSM_ES_TICKET_PATH='work/private-game/disc/DATA/ticket.bin',SHSM_ES_LAB_CONSUMPTION='1',
        SHSM_DI_LAB_INQUIRY_PATH=str(root / 'di-inquiry-device/dolphin-lab-inquiry.bin'),
        SHSM_SC_LAB_FILE='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/shared2/sys/SYSCONF',
        SHSM_SC_LAB_PRODUCT='_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt')
    if mode == 'disabled':
        env['SHSM_FP_REGISTRATION_DISABLED'] = '1'
    result = subprocess.run([str(output / 'openshsm-mass-boot'),'work/private-game/disc/DATA/sys/main.dol',
        str(output / 'boot-quarantine.tsv'),str(root / 'sram-native/settings.bin')],
        env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode == 7 and not result.stderr
    logs[mode] = result.stdout
    (output / (mode + '-audit.log')).write_text(result.stdout)
assert 'FP_REGISTRATION_RETURN 4004 44040000 210' in logs['live']
assert 'FP_REGISTRATION_RETURN ' not in logs['disabled']
assert 'BOOT_BOUNDARY pc=80015234 lr=8021e8f4 msr=a032' in logs['disabled']
assert 'address=8001526c opcode=ec000828' not in logs['live']
for log in logs.values():
    assert 'PLAYRECORD_SEEK_RETIRED' in log
    assert 'PLAYRECORD_SEEK_END_STATE  4 1 0 0 0 0 0 4 935e0060' in log
    assert 'BOOT_STM submitted=48 produced=23' in log
tree = ast.parse((experiment / 'audit_playrecord_dec_boot.py').read_text())
prefixes = ast.literal_eval(next(node.iter for node in tree.body if isinstance(node,ast.For)
    and isinstance(node.target,ast.Name) and node.target.id == 'prefix'))
for prefix in prefixes:
    rows = {mode:[line for line in log.splitlines() if line.startswith(prefix)] for mode,log in logs.items()}
    assert rows['live'] and rows['live'] == rows['disabled'],prefix
assert sha(seed) == seed_hash
boundary = next(line for line in logs['live'].splitlines() if line.startswith('BOOT_BOUNDARY '))
(output / 'registration-boot-audit.json').write_text(json.dumps({
    'result':'WHOLE_ORIGINAL_CONSTRUCTOR128_NATIVE_ORACLE_MATCH_AND_BOOT_CONTINUED',
    'auditSha256':sha(Path(__file__)),'buildSha256':sha(output / 'build.json'),
    'liveLogSha256':sha(output / 'live-audit.log'),'disabledLogSha256':sha(output / 'disabled-audit.log'),
    'seedSha256':seed_hash,'nextBoundary':boundary,
    'limits':['One arithmetic body and read-only return observation;124 objects retained.',
        'Same128 original function cases, global records/destructor-chain ordering/lanes/status/return.',
        'Not first screen/full game/physical Wii proof; other FP families and DEC exception delivery remain guarded.']},indent=2) + '\n')
print('PASS original constructor/native128/global records/return/one-object delta/fresh boot/prior data-STM-seed; ' + boundary)
