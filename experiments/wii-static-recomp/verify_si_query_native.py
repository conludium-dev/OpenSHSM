"""Compare whole compiled SI query and negative cases with original observations."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'si-query-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_si_query_dolphin.py')], check=True)
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
assert build['returnCode'] == 0
assert build['builderSha256'] == sha(experiment / 'build_si_query_native.py')
assert build['backendSha256'] == sha(experiment / 'si_idle_backend.h')
assert build['queryBackendSha256'] == sha(experiment / 'si_query_backend.h')
assert build['frontendSha256'] == sha(experiment / 'si_query_frontend.h')
assert build['baseExecutionSha256'] == sha(private / 'exi-getid-native/execution.json')
for path, digest in build['sourceHashes'].items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125
for record in build['records']:
    assert sha(Path(record['source'])) == record['sourceSha256'] and sha(Path(record['object'])) == record['objectSha256']
    if 'changes' in record:
        source_input = Path(record['inputSource'])
        assert record['inputSourceSha256'] == sha(source_input)
        original_lines = source_input.read_text().splitlines(True)
        lines = list(original_lines)
        for change in record['changes']:
            marker = f"    // 0x{change['instruction']:08X}: {change['opcode']:08X}\n"
            matches = [index for index, line in enumerate(original_lines[:-1]) if line == marker and original_lines[index + 1] == change['before']]
            assert matches
            for index in matches:
                lines[index + 1] = change['after']
        assert Path(record['source']).read_text() == ''.join(lines)
body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')
assert (output / 'si-query-host.cpp').read_text() == '#include "si_query_frontend.h"\n' + body + '\n' + (experiment / 'si_query_host.cpp').read_text()
oracle_path = private / 'dolphin-si-query-callback/comparison.json'
assert build['oracleSha256'] == sha(oracle_path)
oracle = json.loads(oracle_path.read_text())
expected = [[row['index'], *row['observations'], row['typeAfterCallback']] for row in oracle['reports'][1]['values']]
exe = output / 'si-query-probe'
assert build['executableSha256'] == sha(exe)

def run(mode):
    result = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', mode], capture_output=True, text=True, timeout=30)
    values = [[int(value) for value in line.split()[1:]] for line in result.stdout.splitlines() if line.startswith('SI_QUERY_CASE ')]
    return result, values

positive, actual = run('normal')
assert positive.returncode == 0 and actual == expected
assert positive.stdout + positive.stderr == (output / 'native.log').read_text()
lost, lost_values = run('lost')
assert lost.returncode == 20 and not lost_values and 'SI_QUERY_LOST_COMPLETION polls=100001' in lost.stdout
wrong, wrong_values = run('wrong')
mutated = [list(row) for row in expected]
for row in mutated:
    row[4] = 0x01020300
    row[9] = 0x010203a5
assert wrong.returncode == 0 and wrong_values == mutated
assert sum(left != right for left, right in zip(wrong_values, expected)) == 16
guards, guard_values = run('guards')
assert guards.returncode == 0 and not guard_values and 'SI_QUERY_GUARDS 8' in guards.stdout
invalid, invalid_values = run('invalid')
assert invalid.returncode == 2 and not invalid_values
ghidra_path = private / 'dolphin-si-query-callback/ghidra/verification.json'
ghidra = json.loads(ghidra_path.read_text())
assert ghidra['runnerSha256'] == sha(experiment / 'verify_si_query_ghidra.py')
assert ghidra['scriptSha256'] == sha(experiment / 'ExportFormatSpan.java')
for row in ghidra['records']:
    assert row['discoveredBodyBytes'] == row['bytes']
    assert row['objectSha256'] == sha(private / 'dtk-output/obj/auto_03_802045CC_text.o')
    assert row['assemblySha256'] == sha(ghidra_path.parent / (row['name'] + '.asm'))
    assert row['decompiledSha256'] == sha(ghidra_path.parent / (row['name'] + '.c'))
(output / 'comparison.json').write_text(json.dumps({'result': 'COMPILED_SI_QUERY16_COMPLETION_CALLBACK_MATCHES_ORIGINAL', 'values': actual,
    'guards': 8, 'wrongResponseDifferences': 16, 'lostCompletionReturnCode': lost.returncode, 'buildSha256': sha(build_path),
    'verifierSha256': sha(Path(__file__)), 'ghidraSha256': sha(ghidra_path), 'oracleSha256': sha(oracle_path),
    'limits': ['Prepared disconnected ports only; synchronous native completion is a PC adaptation, not timing/IRQ delivery proof.',
        'Setup/completion/callback compiled, but wait/completion/callback scheduling supplied by host fixture; SIGetType/SITransfer alarm/interrupt route remain unverified.',
        'No all-register equivalence/physical Wii/attached controller/full SI/game image or boot integration claim.']}, indent=2) + '\n')
print('PASS16 whole compiled SI setup/completion/callback;18observed fields/final type8;lost completion/wrong response16/refusals8')
