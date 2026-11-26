"""Replay the retained whole-function comparison without rebuilding artifacts."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'si-xy-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_xy_dolphin.py')], check=True)
proof_path = output / 'comparison.json'
proof = json.loads(proof_path.read_text())
assert proof['builderSha256'] == sha(experiment / 'build_si_xy_native.py')
assert proof['frontendSha256'] == sha(experiment / 'si_xy_frontend.h')
assert proof['backendSha256'] == sha(experiment / 'si_xy_backend.h')
assert proof['baseExecutionSha256'] == sha(private / 'exi-getid-native/execution.json')
assert proof['oracleSha256'] == sha(private / 'dolphin-si-xy/comparison.json')
for path, digest in proof['sourceHashes'].items():
    assert sha(Path(path)) == digest
metadata = json.loads((private / 'exi-getid-native/execution.json').read_text())
assert len(metadata['records']) == 125
for row in metadata['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
source = Path(proof['sourceInput'])
assert proof['sourceInputSha256'] == sha(source)
assert source.read_text().count(proof['before']) == 1
assert (output / 'output_63.cpp').read_text() == source.read_text().replace(proof['before'], proof['after'])
assert proof['sourceSha256'] == sha(output / 'output_63.cpp') and proof['objectSha256'] == sha(output / 'output_63.cpp.o')
host_body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
assert (output / 'si-xy-host.cpp').read_text() == '#include "si_xy_frontend.h"\n' + host_body + '\n' + (experiment / 'si_xy_host.cpp').read_text()
exe = output / 'si-xy-probe'
assert proof['executableSha256'] == sha(exe)
replay = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert replay.returncode == 0 and replay.stdout + replay.stderr == (output / 'native.log').read_text()
actual = [[int(value) for value in line.split()[1:]] for line in replay.stdout.splitlines() if line.startswith('SI_XY_CASE ')]
oracle = json.loads((private / 'dolphin-si-xy/comparison.json').read_text())
expected = [[row['index'], row['returnValue'], row['pollRaw'], row['mirrorAfter'], row['msr']] for row in oracle['values']]
assert actual == proof['values'] == expected
assert proof['guards'] == 5 and 'SI_XY_GUARDS 5' in replay.stdout
(output / 'verification.json').write_text(json.dumps({'result': 'SI_XY_NATIVE16_EXACT_REPLAY_SOURCE_OBJECT_VERIFIED',
    'proofSha256': sha(proof_path), 'verifierSha256': sha(Path(__file__)), 'limits': proof['limits']}, indent=2) + '\n')
print('PASS whole SISetXY16/guards5 retained binary exact replay and source/object provenance; boot integration pending')
