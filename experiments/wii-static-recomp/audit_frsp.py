"""Check whole-module FRSP routing and bounded instruction evidence; retain NI gate."""
from pathlib import Path
import hashlib
import json
import subprocess
import struct
from frsp_lowering import lower

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-frsp')
base = Path('work/private-game/static-recomp/mass-spd')
measurement = Path('work/private-game/static-recomp/dolphin-frsp-flags')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_frsp_flags.py')], check=True)
proof = json.loads((measurement / 'comparison.json').read_text())
metadata = json.loads((base / 'lowering.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert lowering['sites'] == 1407 and len(lowering['records']) == len(metadata['records']) == 125
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
for key, filename in [('adapterSha256', 'frsp_adapter.h'), ('conversionSha256', 'ni_conversion.h'),
                      ('lowererSha256', 'frsp_lowering.py'), ('scriptSha256', 'build_frsp.py'),
                      ('baseBuilderSha256', 'build_branch.py')]:
    assert lowering[key] == sha(experiment / filename)
assert lowering['seedHeaderSha256'] == sha(output / 'loader-bat-seed.h') == sha(base / 'loader-bat-seed.h')
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
statements = {}
addresses = set()
for old, record in zip(metadata['records'], lowering['records']):
    source = Path(old['directory']) / old['file']
    assert sha(source) == old['sourceSha256'] and old['file'] == record['file']
    expected, changes = lower(source.read_text(), original)
    target = Path(record['directory']) / record['file']
    assert target.read_text() == expected and record['changes'] == changes
    assert sha(target) == record['sourceSha256'] and sha(Path(str(target) + '.o')) == record['objectSha256']
    for change in changes:
        statements[int(change['opcode'], 16)] = change['after']
        addresses.add(int(change['address'], 16))

header = struct.unpack('>64I', original[:256])
original_addresses = set()
for section in range(7):
    for offset in range(0, header[36 + section], 4):
        opcode = struct.unpack_from('>I', original, header[section] + offset)[0]
        if opcode >> 26 == 63 and ((opcode >> 1) & 1023) == 12:
            original_addresses.add(header[18 + section] + offset)
assert len(original_addresses) == 1173 and len(addresses) == 1166 and addresses <= original_addresses

probe_source = (experiment / 'frsp_probe.cpp').read_text()
dispatch = 'switch (opcode) {\n' + ''.join(
    f'case {opcode}u: {{\n{statement.replace("ctx,", "context,")}break; }}\n'
    for opcode, statement in sorted(statements.items())) + '\ndefault: return 11;\n}'
probe_source = probe_source.replace('nwii::runtime::experiment_frsp(context, opcode);', dispatch)
probe = output / 'lowered-frsp-probe.cpp'
probe.write_text(probe_source)
exe_probe = output / 'lowered-frsp-probe'
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
build = subprocess.run(['clang++', '-std=c++20', '-O2', '-I', str(experiment),
                        '-I', str(upstream / 'nWiiRuntime/include'), str(probe), '-o', str(exe_probe)],
                       capture_output=True, text=True, timeout=30)
(output / 'lowered-probe-build.log').write_text(build.stdout + build.stderr)
assert build.returncode == 0, build.stderr
inputs, expected = [], []
for opcode in sorted(statements):
    for observation in proof['observations']:
        inputs.append(f"{observation['inputBits']} {observation['fpscrBefore']} {opcode}\n")
        expected.append([observation['ps0'], observation['ps1'], observation['fpscrAfter'], 0xaaaaaaaa, 1])
execution = subprocess.run([str(exe_probe)], input=''.join(inputs), capture_output=True, text=True, timeout=30)
assert execution.returncode == 0, execution.stderr
assert [list(map(int, line.split())) for line in execution.stdout.splitlines()] == expected

boot = json.loads((output / 'boot.json').read_text())
exe = output / 'openshsm-mass-boot'
policy = Path('work/private-game/static-recomp/mass-bat/boot-quarantine.tsv')
assert boot['executableSha256'] == sha(exe) and boot['wrapperSha256'] == sha(output / 'boot-wrapper.cpp')
assert boot['loweringSha256'] == sha(output / 'lowering.json') and boot['policySha256'] == sha(policy)
prefix = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol',
                         'work/private-game/static-recomp/mass-l2/boot-quarantine.tsv'],
                        capture_output=True, text=True, timeout=30)
baseline = Path('work/private-game/static-recomp/mass-timebase/boot.json')
assert prefix.returncode == 7 and prefix.stdout == json.loads(baseline.read_text())['stdout']
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
(output / 'live-replay.log').write_text(replay.stdout + replay.stderr)
assert replay.returncode == 7 and 'BOOT_BOUNDARY pc=80210830 lr=802113e8 msr=2030' in replay.stdout
assert 'BOOT_CACHE hid0=c200' in replay.stdout
report = {'result': 'FRSP_MODULE_ROUTING_AND_BOUNDED_STATUS_VERIFIED_NI_GATE_RETAINED',
          'sites': 1407, 'uniqueAddresses': 1166, 'originalTextCandidates': 1173,
          'untranslatedAddresses': [hex(address) for address in sorted(original_addresses - addresses)],
          'originalObservations': 256, 'refusalRollbackCases': 8,
          'operandClasses': len(statements), 'loweredSnippetCases': len(expected),
          'loweringSha256': sha(output / 'lowering.json'), 'comparisonSha256': sha(measurement / 'comparison.json'),
          'executableSha256': sha(exe), 'bootSha256': sha(output / 'boot.json'),
          'probeSourceSha256': sha(probe), 'verifierSha256': sha(Path(__file__)),
          'preTimebaseBaselineSha256': sha(baseline),
          'limits': ['256 original-address Dolphin instruction observations; not physical Wii/full function execution.',
                     'Other register operands checked by exact generated snippets using the same numerical oracle.',
                     'RN0 finite/infinity non-record FRSP only; NaN/other rounding/enabled exceptions refuse.',
                     'NI gate unchanged; other FP/paired/FMA, full post-clock endpoint and original menu remain unverified.']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS FRSP1407sites/1166addresses/125objects/256original observations/{len(expected)}lowered snippets; seven text candidates absent, NI gate retained')
