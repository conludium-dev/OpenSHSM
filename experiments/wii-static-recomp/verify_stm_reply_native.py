"""Verify current CPU reply/wakeup against original states and both cache views."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

root = Path('work/private-game/static-recomp')
output = root / 'stm-reply-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'attempt.json').read_text())
assert build['returnCode'] == 0
assert build['builderSha256'] == sha(Path('experiments/wii-static-recomp/build_stm_reply_native.py'))
assert build['parentBuilderSha256'] == sha(Path('experiments/wii-static-recomp/build_stm_irq_native_attempt.py'))
assert build['baseBuildSha256'] == sha(root / 'mass-flush-packet-boot/build.json')
assert build['profileProofSha256'] == sha(root / 'stm-open-native/comparison.json')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
prior = json.loads((root / 'mass-flush-packet-boot/build.json').read_text())
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
assert len(build['records']) == len(prior['records']) == 125 and len(build['transforms']) == 4
for row, old in zip(build['records'], prior['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    if row['file'] != 'output_67.cpp':
        assert row == old
    else:
        source = Path(old['source']).read_text()
        for before, after in build['transforms']:
            assert source.count(before) == 1
            address, opcode = [int(value, 16) for value in before.splitlines()[0].strip().removeprefix('// 0x').split(': ')]
            section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
            assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
            source = source.replace(before, after)
        assert source == Path(row['source']).read_text()
oracle_path = root / 'dolphin-stm-irq-cache/comparison.json'
oracle = json.loads(oracle_path.read_text())
def validate(log):
    cases = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_REPLY_CASE ')]
    physical = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_REPLY_PHYSICAL ')]
    cached = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_REPLY_CACHED ')]
    assert len(cases) == len(physical) == len(cached) == 16
    for case, raw, local, original in zip(cases, physical, cached, oracle['observations']):
        index, state = original['index'], original['states']
        expected = [index, state[13], 0x807f0000, *state[22:26], state[2], state[3], state[4], 2, 1,
            state[5], state[6], state[7], state[8], state[9], state[11], state[12], *state[26:31]]
        assert list(map(int, case)) == expected
        assert raw == [str(index), original['physicalPacketHex']]
        assert local == [str(index), original['cachedPacketHex']]
exe = output / 'stm-irq-attempt'
assert sha(exe) == build['executableSha256']
validate((output / 'native.log').read_text())
fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert fresh.returncode == 0 and not fresh.stderr
validate(fresh.stdout)
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout.splitlines()[-1] == 'STM_REPLY_GUARDS 12' and not guards.stderr
for marker in ('STM_REPLY_CASE 0 ', 'STM_REPLY_PHYSICAL 0 ', 'STM_REPLY_CACHED 0 '):
    lines = fresh.stdout.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(marker))
    values = lines[index].split()
    if marker.startswith('STM_REPLY_CASE'):
        values[-2] = str(int(values[-2]) ^ 1)
    else:
        values[-1] = values[-1][:-1] + ('1' if values[-1][-1] != '1' else '0')
    lines[index] = ' '.join(values)
    try:
        validate('\n'.join(lines))
    except AssertionError:
        pass
    else:
        raise AssertionError('CPU/physical/cache mutation accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'CURRENT_NATIVE_CPU_STM16_ACK_REPLY_WAKE_READY_RFI_BOTH_CACHE_VIEWS_ORIGINAL_MATCH',
    'verifierSha256': sha(Path(__file__)), 'attemptSha256': sha(output / 'attempt.json'), 'oracleSha256': sha(oracle_path),
    'guards': 12, 'comparisonMutants': 3, 'limits': build['limits']}, indent=2) + '\n')
print('PASS current16 CPU ACK/reply/realOPEN/WakeupThread/rfi/cache+physical-original match;12guards/fresh/3mutants')
