"""Compare actual compiled sleep/idle/wakeup with the own-Wii execution oracle."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
output = root / 'stm-sleep-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'attempt.json').read_text())
assert build['returnCode'] == 0
assert build['builderSha256'] == sha(experiment / 'build_stm_sleep_native_attempt.py')
assert build['parentBuilderSha256'] == sha(experiment / 'build_stm_irq_native_attempt.py')
assert build['sleepHostParentSha256'] == sha(experiment / 'stm_reply_host.cpp')
prior = json.loads((root / 'mass-flush-packet-boot/build.json').read_text())
assert build['baseBuildSha256'] == sha(root / 'mass-flush-packet-boot/build.json')
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
assert len(build['records']) == 125 and len(build['transforms']) == 4
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
layout = struct.unpack('>64I', dol[:256])
for address, opcode in ((0x8021a8d8, 0x4bffcc29), (0x80217508, 0x7c800124), (0x8021750c, 0x54638ffe)):
    section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
for row, old in zip(build['records'], prior['records']):
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
    source = Path(old['source']).read_text()
    if row['file'] == 'output_67.cpp':
        for before, after in build['transforms']:
            assert source.count(before) == 1
            address, opcode = [int(value, 16) for value in before.splitlines()[0].strip().removeprefix('// 0x').split(': ')]
            section = next(i for i in range(7) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
            assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
            source = source.replace(before, after)
    assert source == Path(row['source']).read_text()
    if row['file'] not in build['recompiledProfileObjects']:
        assert row == old
oracle_path = root / 'dolphin-stm-sleep/comparison.json'
assert build['sleepOracleSha256'] == sha(oracle_path)
oracle = json.loads(oracle_path.read_text())

def validate(log):
    cases = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_SLEEP_CASE ')]
    physical = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_REPLY_PHYSICAL ')]
    cached = [line.split()[1:] for line in log.splitlines() if line.startswith('STM_REPLY_CACHED ')]
    assert len(cases) == len(physical) == len(cached) == 16
    for case, raw, local, original in zip(cases, physical, cached, oracle['observations']):
        index, state = original['index'], original['states']
        values = list(map(int, case))
        expected = [index, state[13], 0x807f0000, *state[36:40], state[2], state[3], state[4], 2, 1,
            state[5], state[6], state[7], state[8], state[9], state[11], state[12],
            *state[26:31], state[20], state[21], *state[22:25], values[29], state[32], *state[33:36]]
        assert values == expected, (index, values, expected)
        assert values[29] == 0x8021750c
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
for marker in ('STM_SLEEP_CASE 0 ', 'STM_REPLY_PHYSICAL 0 ', 'STM_REPLY_CACHED 0 '):
    lines = fresh.stdout.splitlines()
    i = next(i for i, line in enumerate(lines) if line.startswith(marker))
    values = lines[i].split()
    if marker.startswith('STM_SLEEP_CASE'):
        values[-1] = str(int(values[-1]) ^ 1)
    else:
        values[-1] = values[-1][:-1] + ('1' if values[-1][-1] != '1' else '0')
    lines[i] = ' '.join(values)
    try:
        validate('\n'.join(lines))
    except AssertionError:
        pass
    else:
        raise AssertionError('Sleep/context/cache mutation accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'CURRENT_NATIVE_REAL_SLEEP16_IDLE_IRQ_WAKE_SELECT_RETURN_ORIGINAL_MATCH',
    'verifierSha256': sha(Path(__file__)), 'attemptSha256': sha(output / 'attempt.json'), 'oracleSha256': sha(oracle_path),
    'logSha256': sha(output / 'native.log'),
    'guards': 12, 'comparisonMutants': 3, 'limits': build['limits'] + [
        'Idle IRQ arrives inside OSEnableInterrupts at8021750C (caller8021A8D8, LR8021A8DC), not original sample8021A8E0; native event ticks are not Wii cycle timing.',
        'Native return sentinel replaces the harness caller address; ABI and thread saved context remain compared.']}, indent=2) + '\n')
print('PASS16 compiled original sleep/idle IRQ/wakeup/select/return vs Wii; both64-byte views;12guards/3mutants')
