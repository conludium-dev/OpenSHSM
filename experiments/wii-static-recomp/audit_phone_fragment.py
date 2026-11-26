"""Audit current build, real frames and provenance; do not widen acceptance to the whole phone."""
from pathlib import Path
import hashlib
import json
import subprocess

private = Path('work/private-game/static-recomp')
generated = private / 'nwii-current'
subprocess.run(['python3', 'experiments/wii-static-recomp/audit_result.py'], check=True)
build = json.loads((private / 'phone-fragment.json').read_text())
frames = json.loads((private / 'phone-fragment-frames.json').read_text())
dependencies = json.loads((private / 'phone-dependencies.json').read_text())
exe_hash = hashlib.sha256((generated / 'openshsm-runtime-recomp-phone.exe').read_bytes()).hexdigest()
cpp_hash = hashlib.sha256((generated / 'selected.cpp').read_bytes()).hexdigest()
wrapper_hash = hashlib.sha256(Path('experiments/wii-static-recomp/runtime_phone.cpp').read_bytes()).hexdigest()
for report in (build, frames):
    assert report['result'] == 'PASS' and report['executableSha256'] == exe_hash
    assert report['generatedSha256'] == cpp_hash and report['wrapperSha256'] == wrapper_hash
assert build['bridgeSha256'] == hashlib.sha256(Path('experiments/wii-static-recomp/probe_bridge.cpp').read_bytes()).hexdigest()
assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in build['nativeSourcesSha256'].items())
assert len(build['records']) == 3 and all(record['exitCode'] == 0 for record in build['records'])
assert 'SHSM_RECOMP_SUMMARY calls=0 exit=0' in build['records'][1]['stdout']
assert 'SHSM_RECOMP_SUMMARY calls=2 exit=0' in build['records'][2]['stdout']
assert 'SHSM_RECOMP_UI action=MobileSettingsVibrateLeft prior=1 result=0 abi=1 callbacks=3' in build['records'][2]['stdout']
assert 'SHSM_RECOMP_UI action=MobileSettingsVibrateRight prior=0 result=1 abi=1 callbacks=3' in build['records'][2]['stdout']
assert len(frames['records']) == 7 and frames['invalidInputs'] == 3
for record in frames['records']:
    assert record['exactNativeFrameMatch'] and len(record['runs']) == 2
    for tag in ('native', 'ppc'):
        path = private / ('phone-fragment-' + record['fixture'] + '-' + tag + '.ppm')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['frameSha256']
assert dependencies['dolSha256'] == hashlib.sha256(Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()).hexdigest()
assert len(dependencies['roots']) == 4 and len(dependencies['directCallees']) == 5
discrepancies = [record['address'] for record in dependencies['roots'] + dependencies['directCallees']
                 if not record['boundaryAgreement'] or not record['instructionCountMatchesBoundary']]
assert discrepancies == ['0x800f3e30', '0x800ed3c8'], discrepancies
switch = dependencies['switchDetectionCheck']
assert switch['entries'] == 31 and switch['correctExtendedOpcode'] == 528
assert switch['upstreamComparedValue'] == 32 and switch['correctSpr'] == 9 and switch['upstreamComparedSpr'] == 288
assert not switch['upstreamBctrDetectionMatches']
assert switch['analyzerSourceSha256'] == hashlib.sha256(Path(switch['analyzerSource']).read_bytes()).hexdigest()
report = {'result': 'PASS', 'scope': 'Opt-in original vibrate callback connected to existing native PhoneUI input/state/render path.',
          'executableSha256': exe_hash, 'generatedSha256': cpp_hash, 'pairedRenderCases': 7,
          'invalidInputs': 3, 'independentPpcOracleCases': 536, 'releaseUnchanged': True,
          'pendingAnalyzerDiscrepancies': discrepancies,
          'switchDetectionIssueVerified': True,
          'limits': frames['limits'], 'next': 'Resolve tail-branch/switch-table analysis; verify ringtone/volume consumer contracts before translating them.'}
(private / 'phone-fragment-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:connected vibrate input/state/render experiment; tone/audio/save/controller scope remains open')
