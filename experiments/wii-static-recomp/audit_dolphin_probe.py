"""Validate private tool/measurement provenance and preserve previous experiment/release gates."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-probe')
native = Path('work/private-game/static-recomp/mass-fpscr-translated')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
runtime = json.loads((output / 'runtime-provenance.json').read_text())
assert runtime['installerNotExecuted'] and runtime['result'] == 'EXTRACTED_ONLY'
assert runtime['runtimeInstallerSha256'] == sha(Path('_scratch/tmp/dolphin-runtime-tools/vc_redist.x64.exe'))
assert runtime['sevenZipSha256'] == sha(Path('_scratch/tmp/dolphin-runtime-tools/7z-mac.tar.xz'))
assert runtime['scriptSha256'] == sha(experiment / 'prepare_dolphin_runtime.py')
assert runtime['sourceDolphinSha256'] == runtime['labDolphinSha256'] == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
assert runtime['sourceDolphinSha256'] == sha(Path('work/research/dolphin/Dolphin-x64/Dolphin.exe'))
for record in runtime['records']:
    assert record['sha256'] == sha(Path('_scratch/tmp/dolphin-static-recomp-lab') / record['file'])
for mode in ['boot', 'fpr-init']:
    capture = json.loads((output / (mode + '-dolphin.json')).read_text(encoding='utf-8-sig'))
    assert capture['scriptSha256'].lower() == sha(experiment / 'run_dolphin_probe.ps1')
    assert 'GDBPort' not in capture['arguments']
lowering = json.loads((native / 'lowering.json').read_text())
assert lowering['initialMsr'] == 0x30 and len(lowering['changes']) == 4
assert lowering['scriptSha256'] == sha(experiment / 'build_fpscr.py')
assert lowering['adapterSha256'] == sha(experiment / 'fpscr_adapter.h')
assert len(lowering['records']) == 125 and sum(record['modified'] for record in lowering['records']) == 2
for record in lowering['records']:
    path = Path(record['directory']) / record['file']
    assert record['sourceSha256'] == sha(path)
    assert record['objectSha256'] == sha(Path(str(path) + '.o'))
subprocess.run(['python3', str(experiment / 'verify_dolphin_probe.py')], check=True)
subprocess.run(['python3', str(experiment / 'audit_fpscr.py')], check=True)
comparison = json.loads((output / 'comparison.json').read_text())
report = {'result': 'PASS_WITH_SCOPE_LIMITS', 'comparisonSha256': sha(output / 'comparison.json'),
          'runtimeProvenanceSha256': sha(output / 'runtime-provenance.json'), 'scriptSha256': sha(Path(__file__)),
          'originalInitializerCases': 8, 'pairedOriginalCases': 4, 'releaseUnchanged': True,
          'next': 'Implement/verify immutable-code HID0 ICE enable contract against this Dolphin fixture, then continue original cache/OS/IOS boot.',
          'limits': comparison['limits']}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scoped Dolphin/translated-fixture audit; original bytes/private provenance/release gates preserved')
