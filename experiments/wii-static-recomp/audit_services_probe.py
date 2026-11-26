"""Verify service probe provenance and test scope without claiming complete audio integration."""
from pathlib import Path
import hashlib
import json
import subprocess

private = Path('work/private-game/static-recomp')
output = private / 'phone-services'
experiment = Path('experiments/wii-static-recomp')
build = json.loads((output / 'build.json').read_text())
execution = json.loads((output / 'execution.json').read_text())
windows = json.loads((output / 'windows.json').read_text())
ghidra = json.loads((output / 'ghidra.json').read_text())
cpp_hash = hashlib.sha256((output / 'selected.cpp').read_bytes()).hexdigest()
for report in (build, execution, windows):
    assert report['result'] == 'PASS' and report['generatedSha256'] == cpp_hash
for key, path in [('patchedAnalyzerSha256', output / 'analyzer-profile.cpp'),
                  ('profileSha256', output / 'analyzer-profile.tsv'), ('driverSha256', experiment / 'nwii_services_driver.cpp'),
                  ('hostSourceSha256', experiment / 'services_host.cpp'), ('profileHeaderSha256', experiment / 'analyzer_profile.h'),
                  ('buildScriptSha256', experiment / 'build_services_probe.py')]:
    assert build[key] == hashlib.sha256(path.read_bytes()).hexdigest(), key
assert build['upstreamAnalyzerSha256'] == hashlib.sha256(Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiAnalyzer/src/analyzer.cpp').read_bytes()).hexdigest()
assert execution['nativeHostSha256'] == build['nativeHostSha256'] == hashlib.sha256((output / 'services-host').read_bytes()).hexdigest()
assert execution['nativeSnapshotsSha256'] == hashlib.sha256((output / 'native-snapshots.txt').read_bytes()).hexdigest()
assert windows['executableSha256'] == hashlib.sha256((output / 'services-host-windows.exe').read_bytes()).hexdigest()
assert windows['originalOracleSha256'] == hashlib.sha256((output / 'execution.json').read_bytes()).hexdigest()
assert (output / 'windows-snapshots.txt').read_text().splitlines() == (output / 'native-snapshots.txt').read_text().splitlines()
assert execution['cases'] == windows['cases'] == len(execution['records']) == 744
assert execution['selectedIrInstructions'] == 477 and execution['uniqueJumpTargets'] == 18
assert execution['allUniqueJumpTargetsExecuted']
counts = {scope: sum(record['scope'] == scope for record in execution['records'])
          for scope in ('selectedFunctionReturn', 'externalConsumerBoundary')}
assert sum(counts.values()) == 744 and all(counts.values())
assert ghidra['result'] == 'PASS' and ghidra['instructions'] == 365
assert ghidra['objectSha256'] == hashlib.sha256((private / 'dtk-output/obj/auto_03_800E6590_text.o').read_bytes()).hexdigest()
assert ghidra['scriptSha256'] == hashlib.sha256((experiment / 'ExportServicesCheck.java').read_bytes()).hexdigest()
for name, digest in ghidra['outputsSha256'].items():
    assert digest == hashlib.sha256((output / name).read_bytes()).hexdigest()
assert 'inferredBodyBytes=104' in (output / 'ghidra-services.txt').read_text(), 'Reassess Ghidra CFG scope'


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


diffs = []
for function, tag in [('fn_800ED314', 'play-gate'), ('fn_800ED3C8', 'stop')]:
    result = subprocess.run(['_scratch/tmp/wii-static-recomp-tools/objdiff-cli', 'diff', '-1',
                             str(private / 'dtk-output/obj/auto_03_800E6590_text.o'), '-2',
                             str(output / (function + '-reference.o')), function, '-o',
                             str(output / ('objdiff-' + tag + '.json')), '--format', 'json-pretty'],
                             capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    diff = json.loads((output / ('objdiff-' + tag + '.json')).read_text())
    matches = [record for record in objects(diff) if record.get('name') == function and 'match_percent' in record]
    assert len(matches) == 2 and all(record['match_percent'] == 100 for record in matches), function
    diffs.append({'function': function, 'ppcReferenceMatch': 100})
subprocess.run(['python3', str(experiment / 'audit_phone_fragment.py')], check=True)
report = {'result': 'PASS', 'scope': 'Scoped analyzer correction and compiled service control-flow verification.',
          'casesPerArchitecture': 744, 'selectedInstructions': 477, 'uniqueSwitchTargetsExecuted': 18,
          'executionScopes': counts, 'ppcReferenceDiffs': diffs,
          'ghidraSequentialDisassemblyInstructions': 365, 'ghidraStopServiceInferredBodyBytes': 104,
          'generatedSha256': cpp_hash, 'releaseUnchanged': True, 'limits': execution['limits'],
          'next': 'Translate/verify ED8C8 play receiver and374F4 volume consumer including paired singles; resolve original object/vtable contracts before expanding live PhoneUI.'}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:service analyzer/ARM64/Windows/PPC/dtk/objdiff/static Ghidra checks; external audio consumers remain open', counts)
