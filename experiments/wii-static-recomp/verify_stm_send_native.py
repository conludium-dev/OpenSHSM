"""Compare whole current-object sender with original allocation/submission/sleep/free."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'stm-send-cycle'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'attempt.json').read_text())
assert build['returnCode'] == 0
assert build['builderSha256'] == sha(experiment / 'build_stm_send_cycle.py')
assert build['baseAttemptSha256'] == sha(root / 'stm-sleep-native/attempt.json')
assert build['logSha256'] == sha(output / 'native.log')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
base = json.loads((root / 'stm-sleep-native/attempt.json').read_text())
assert len(build['records']) == len(base['records']) == 125
for row, old in zip(build['records'], base['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] == 'output_67.cpp':
        assert Path(row['source']).read_bytes() == Path(old['source']).read_bytes()
    else:
        assert row == old
oracle_path = root / 'dolphin-stm-send/comparison.json'
oracle = json.loads(oracle_path.read_text())

def validate(log):
    cases = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_SEND_CASE ')]
    heaps = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_SEND_HEAP ')]
    physical = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_REPLY_PHYSICAL ')]
    cached = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_REPLY_CACHED ')]
    assert len(cases) == len(heaps) == len(physical) == len(cached) == 16
    for case, heap, raw, local, original in zip(cases, heaps, physical, cached, oracle['observations']):
        index, state = original['index'], original['states']
        expected = [index, state[13], 0x807f0000, *state[36:40], state[2], state[3], state[4], 2, 1, 2,
            original['replyResult'] & 0xffffffff, 1, state[5], state[6], state[7], state[8], state[9],
            state[11], state[12], *state[26:31], state[20], state[21], *state[22:25], 0x8021750c, state[32], *state[33:36]]
        assert list(map(int, case)) == expected, (index, case, expected)
        assert list(map(int, heap)) == [index, *original['heap'][3:]]
        assert raw == [str(index), original['physicalPacketHex']]
        assert local == [str(index), original['cachedPacketHex']]

exe = output / 'stm-send-cycle'
assert sha(exe) == build['executableSha256']
validate((output / 'native.log').read_text())
fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert fresh.returncode == 0 and not fresh.stderr
validate(fresh.stdout)
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout.splitlines()[-1] == 'STM_REPLY_GUARDS 12' and not guards.stderr
for marker in ('STM_SEND_CASE 0 ', 'STM_SEND_HEAP 0 ', 'STM_REPLY_PHYSICAL 0 ', 'STM_REPLY_CACHED 0 '):
    lines = fresh.stdout.splitlines()
    i = next(i for i, line in enumerate(lines) if line.startswith(marker))
    values = lines[i].split()
    if marker.startswith(('STM_SEND_CASE', 'STM_SEND_HEAP')):
        values[-1] = str(int(values[-1]) ^ 1)
    else:
        values[-1] = values[-1][:-1] + ('1' if values[-1][-1] != '1' else '0')
    lines[i] = ' '.join(values)
    try:
        validate('\n'.join(lines))
    except AssertionError:
        pass
    else:
        raise AssertionError('Sender/context/heap/cache mutant accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'CURRENT_NATIVE_SEND16_ALLOCATE_FLUSH_SUBMIT_SLEEP_IRQ_RETURN_FREE_ORIGINAL_MATCH',
    'verifierSha256': sha(Path(__file__)), 'attemptSha256': sha(output / 'attempt.json'), 'oracleSha256': sha(oracle_path),
    'guards': 12, 'comparisonMutants': 4, 'limits': build['limits'] + [
        'Native IRQ delivered in OSEnableInterrupts8021750C vs original8021A8E0; event timing is not Wii cycle-equivalence.',
        'Native807F0000 return sentinel replaces harness caller; ABI/saved thread/free-heap/queue endpoints compared.']}, indent=2) + '\n')
print('PASS16 native whole sender/allocate/flush/X1/sleep/IRQ/result/free vs original;12guards/4mutants')
