"""Compare original SPD function to the full native module, retaining endpoint limits."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess
from spd_lowering import lower

experiment = Path('experiments/wii-static-recomp')
measurement = Path('work/private-game/static-recomp/dolphin-spd-probe')
output = Path('work/private-game/static-recomp/mass-spd')
base = Path('work/private-game/static-recomp/mass-bat')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((measurement / 'generation.json').read_text())
capture_path = measurement / 'fpr-init-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['records'] == len(generation['records']) == 8 and capture['accurateCache'] == 'True'
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(measurement / 'fpr-init.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_spd_dolphin.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_spd_dolphin.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert sha(original_path) == generation['originalSha256']
assert (measurement / 'fpr-init.dol').read_bytes()[256:len(original)] == original[256:]
data = base64.b64decode(capture['data'])
assert len(data) == 8 * 736
inputs, expected = [], []
for record in generation['records']:
    index = record['index']
    row = data[index * 736:(index + 1) * 736]
    assert row[:16] == b'OSHSM_PPC_DLP001' and struct.unpack_from('>II', row, 16) == (0xc001cafe, index)
    gpr = list(struct.unpack_from('>32I', row, 32))
    cr, lr, ctr, xer, hid2, hid0, msr = struct.unpack_from('>7I', row, 160)
    expected_gpr = record['initialGpr'].copy()
    expected_gpr[0], expected_gpr[3] = record['expectedLr'], record['priorHid0'] | 0x200
    assert gpr == expected_gpr
    assert [cr, lr, ctr, xer, hid2, hid0, msr] == [record['cr'], record['expectedLr'], record['ctr'], record['xer'], 0xa0000000, record['priorHid0'] | 0x200, 0x2030]
    inputs.append([record['priorHid0'], record['cr'], record['xer'], record['ctr'], record['expectedLr'], *record['initialGpr']])
    expected.append([*gpr, cr, lr, ctr, xer, msr, hid0])
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 7 and lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'spd_adapter.h'), ('probeSha256', 'spd_probe.h'), ('lowererSha256', 'spd_lowering.py'),
                      ('scriptSha256', 'build_spd.py'), ('baseBuilderSha256', 'build_branch.py')]:
    assert lowering[key] == sha(experiment / filename)
assert lowering['seedHeaderSha256'] == sha(output / 'loader-bat-seed.h') == sha(base / 'loader-bat-seed.h')
metadata = json.loads((base / 'lowering.json').read_text())
assert len(lowering['records']) == len(metadata['records']) == 125
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected_source, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected_source and changes == record['changes']
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json')
result = subprocess.run([str(exe), '--spd-check'], input=''.join(' '.join(map(str, row)) + '\n' for row in inputs), capture_output=True, text=True, timeout=30)
(output / 'original-comparison.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, (result.returncode, result.stderr)
rows = result.stdout.splitlines()
assert rows[-1] == 'SPD_GUARDS 4'
assert [list(map(int, row.split())) for row in rows[:-1]] == expected
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'work/private-game/static-recomp/mass-l2/boot-quarantine.tsv'],
                        capture_output=True, text=True, timeout=30)
(output / 'pre-timebase.log').write_text(prefix.stdout + prefix.stderr)
baseline_path = Path('work/private-game/static-recomp/mass-timebase/boot.json')
assert prefix.returncode == 7 and prefix.stdout == json.loads(baseline_path.read_text())['stdout']
report = {'result': 'ORIGINAL_SPD_FUNCTION_FULL_MODULE_DOLPHIN_MATCH', 'cases': 8, 'refusalRollbackCases': 4,
          'loweringSha256': sha(output / 'lowering.json'), 'captureSha256': sha(capture_path),
          'generationSha256': sha(measurement / 'generation.json'), 'executableSha256': sha(exe),
          'preTimebaseBaselineSha256': sha(baseline_path), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Original40-byte function and getter/setter instructions unchanged in Dolphin; synthetic MSR/cache/register fixture.',
                     'Native stores SPD as reference register state and delegates existing ICE/ICFI/DCE guards; physical speculation/timing not modeled.',
                     'CPU/GPR/CR/LR/CTR/XER/MSR/HID0 match eight observations; four native refusal rollback cases.',
                     'Pre-timebase trace/state retained; complete new live endpoint, calendar/clock epoch/menu/game remain unverified.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS original SPD40-bytefunction/fullmodule8observations/4guards; speculative hardware timing and full live endpoint unverified')
