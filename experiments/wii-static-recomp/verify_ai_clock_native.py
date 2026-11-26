"""Check compiled original clock commands/ABI/waits under the bounded PC profile."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'verify_si_query_native.py'
body = parent.read_text().replace('si-query-native', 'ai-clock-native').replace('si-query-probe', 'ai-clock-probe').replace('si-query-host', 'ai-clock-host')
body = body.replace('verify_si_query_dolphin.py', 'verify_ai_clock_dolphin.py').replace('dolphin-si-query-callback/comparison.json', 'dolphin-ai-clock/comparison.json')
body = body.replace('build_si_query_native.py', 'build_ai_clock_native.py').replace('si_idle_backend.h', 'ai_clock_profile.h').replace('si_query_backend.h', 'ai_clock_profile.h')
body = body.replace('si_query_frontend.h', 'ai_clock_profile.h').replace('si_query_host.cpp', 'ai_clock_host.cpp')
host_line = "body = (experiment / 'exi_getid_host.cpp').read_text().replace('int main(int argc, char** argv)', 'int unused_getid_main(int argc, char** argv)')"
assert body.count(host_line) == 1
body = body.replace(host_line, host_line + "\nbody = body.replace('context.inst_count > 100000', 'context.inst_count > 1000000')")
before = "expected = [[row['index'], *row['observations'], row['typeAfterCallback']] for row in oracle['reports'][1]['values']]"
after = '''expected = []
for row in oracle['reports'][0]['values']:
    final = row['final']
    values = [row['index'], row['mode'], *final[7:12]]
    for phase in row['phases']:
        address = 0xcd800180 if phase[3] == 0x80212af8 else 0xcd8001cc if phase[3] in (0x80212b6c, 0x80212b94) else 0xcd8001d0
        values.extend([address, phase[0], phase[1]])
    expected.append(values)
assert build['hostInputSha256'] == sha(experiment / 'ai_clock_host.cpp')
assert build['baseBuilderSha256'] == sha(experiment / 'build_si_query_native.py')'''
assert body.count(before) == 1
body = body.replace(before, after)
exact = "assert positive.stdout + positive.stderr == (output / 'native.log').read_text()"
assert body.count(exact) == 1
body = body.replace(exact, '''assert positive.stderr == ''
def validate_clock_trace(stdout):
    lines = stdout.splitlines()
    assert len(lines) == 16 and all(line.startswith('AI_CLOCK_CASE ') for line in lines)
    command_rows = [[int(value) for value in line.split(' AI_CLOCK_TIMES')[0].split()[1:]] for line in lines]
    assert command_rows == expected
    for line in lines:
        timestamps, total = line.split('AI_CLOCK_TIMES ')[1].split(' ticks=')
        timestamps = [int(value) for value in timestamps.split()]
        assert len(timestamps) == 7 and timestamps == sorted(timestamps) and int(total) >= 194400
        assert all(right - left >= minimum for left, right, minimum in zip(timestamps[1:], timestamps[2:], (6075, 6075, 60750, 60750, 60750)))
validate_clock_trace(positive.stdout)
validate_clock_trace((output / 'native.log').read_text())''')
before = "values = [[int(value) for value in line.split()[1:]] for line in result.stdout.splitlines() if line.startswith('SI_QUERY_CASE ')]"
after = "values = [[int(value) for value in line.split(' AI_CLOCK_TIMES')[0].split()[1:]] for line in result.stdout.splitlines() if line.startswith('AI_CLOCK_CASE ')]"
assert body.count(before) == 1
body = body.replace(before, after)
start = body.index("lost, lost_values = run('lost')")
end = body.index('invalid, invalid_values', start)
body = body[:start] + '''stalled, stalled_values = run('stalled')
assert stalled.returncode == 20 and not stalled_values and 'GetID instruction budget exceeded phase=2' in stalled.stdout
waits = []
for line in positive.stdout.splitlines():
    if not line.startswith('AI_CLOCK_CASE '): continue
    timing = [int(value) for value in line.split('AI_CLOCK_TIMES ')[1].split(' ticks=')[0].split()]
    assert len(timing) == 7
    deltas = [right - left for left, right in zip(timing[1:], timing[2:])]
    assert all(delta >= minimum for delta, minimum in zip(deltas, (6075, 6075, 60750, 60750, 60750)))
    waits.append(deltas)
assert len(waits) == 16
guards, guard_values = run('guards')
assert guards.returncode == 0 and not guard_values and 'AI_CLOCK_GUARDS 8' in guards.stdout
''' + body[end:]
body = body.replace("private / 'dolphin-si-query-callback/ghidra/verification.json'", "private / 'dolphin-ai-clock/ghidra/verification.json'")
body = body.replace('verify_si_query_ghidra.py', 'verify_ai_clock_ghidra.py')
body = body.replace("'wrongResponseDifferences': 16, 'lostCompletionReturnCode': lost.returncode", "'waitDeltas': waits, 'stalledReturnCode': stalled.returncode")
namespace = {'__file__': __file__}
exec(compile(body, str(parent), 'exec'), namespace)
output = Path('work/private-game/static-recomp/ai-clock-native')
path = output / 'comparison.json'
report = json.loads(path.read_text())
report['result'] = 'COMPILED_AI_CLOCK16_ORIGINAL_COMMANDS_ABI_WAITS_PC_STUB_PROFILE_MATCH'
report['limits'] = ['Explicit PC reproduction of Dolphin constant-zero/no-op clock registers, not physical Wii PLL emulation or audible output.',
    'Original PPC branches/waits retained; live monotonic existing timebase,5lower-bound wait checks per call, stopped clock fails.',
    'Private clock-probe instruction budget1M replaces GetID100K because the timed SDK loops exceeded the unrelated GetID limit; global boot budgets unchanged.',
    'Prepared bus243MHz/MSR32/HID0/r2-r13; no cycle-exact/all-register/full boot/first-frame/menu acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS16 compiled original clock commands/ABI/5waits; stalled clock fails/8unsupported accesses refuse')
