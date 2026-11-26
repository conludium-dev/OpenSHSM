"""Replay captured whole native blocks; explicitly not original hardware or IRQ oracle."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'idct-block-replay'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
exe = output / 'idct-replay'
assert sha(exe) == build['executableSha256']
assert sha(Path('experiments/wii-static-recomp/stock_idct_replay.cpp')) == build['sourceSha256']
assert sha(root / 'window-fp-context/build.json') == build['baseBuildSha256']
assert sha(root / 'window-quantization/include/runtime/cpu_context.h') == build['cpuHeaderSha256']
assert all(sha(Path(path)) == expected for path, expected in build['linkInputs'].items())
dol = Path('work/private-game/disc/DATA/sys/main.dol').resolve()
assert sha(dol) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
records = []
fixtures = sorted(root.glob(f'window-idct-fixtures-{args.tag}-thp-block*.txt'))
assert fixtures, 'No captured blocks; missing coverage is not a replay pass'
for fixture in fixtures:
    rows = fixture.read_text().splitlines()
    assert len(rows) == 13 and int(rows[5]) == 7
    registers = list(map(int, rows[1].split()))
    ranges = []
    memory = {}
    for line in rows[6:]:
        address, data = line.split()
        address, data = int(address), bytes.fromhex(data)
        ranges.append({'address': address, 'bytes': len(data)})
        for offset, byte in enumerate(data):
            location = address + offset
            assert location not in memory or memory[location] == byte, 'Inconsistent overlapping fixture'
            memory[location] = byte
    coefficients = bytes(memory[registers[3] + index] for index in range(128))
    dc_expectation = None
    if not any(coefficients[2:]):
        slot = registers[13] - 15904
        table = int.from_bytes(bytes(memory[slot + i] for i in range(4)), 'big')
        dc = struct.unpack('>h', coefficients[:2])[0]
        q0 = struct.unpack('>f', bytes(memory[table + i] for i in range(4)))[0]
        pixel = int(max(0, min(255, 128 + dc * q0 / 8)))
        dc_expectation = {'dc': dc, 'quantizer': q0, 'uniformBytes': bytes([pixel, pixel]).hex(),
            'limits': 'Independent DC-only inverse-DCT formula, not original Wii execution.'}
    before0, before1 = map(float.fromhex, rows[4].split())
    observed_bytes = bytes(int(max(0, min(255, value / 8))) for value in (before0, before1)).hex()
    attempts = []
    for attempt in range(3):
        result = subprocess.run([str(exe), str(dol), str(fixture)], env=env,
            capture_output=True, text=True, timeout=20)
        (output / (fixture.stem + f'-attempt{attempt}.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        match = re.search(r'IDCT_REPLAY entry=([0-9a-f]+) pc=([0-9a-f]+) caller=([0-9a-f]+) store=([0-9a-f]+) target=([0-9a-f]+) bytes=([0-9a-f]{4})', result.stdout)
        assert match and match[2] == match[3]
        attempts.append(match[6])
    records.append({'fixture': fixture.name, 'fixtureSha256': sha(fixture), 'ranges': ranges,
        'coefficientHex': coefficients.hex(), 'observedValues': [before0, before1],
        'observedBytes': observed_bytes, 'replayBytes': attempts,
        'deterministic': len(set(attempts)) == 1, 'reproducesObservedBytes': all(value == observed_bytes for value in attempts)})
    records[-1]['dcOnlyFormula'] = dc_expectation
    if dc_expectation:
        records[-1]['matchesDcOnlyFormula'] = all(value == dc_expectation['uniformBytes'] for value in attempts)
report = {'result': 'WHOLE_NATIVE_IDCT_CAPTURE_REPLAY', 'records': records,
    'buildSha256': sha(output / 'build.json'), 'limits': build['limits']}
(output / ('replay-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
for row in records:
    print(row['fixture'], 'observed', row['observedBytes'], 'replay', row['replayBytes'], 'deterministic', row['deterministic'])
