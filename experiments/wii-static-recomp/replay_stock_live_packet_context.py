"""Control timebase frequency and EE in the existing no-device fixture; do not suppress live interrupts."""
from pathlib import Path
import hashlib
import json
import os
import re
import statistics
import struct
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'live-packet-replay'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
prior_path = output / 'verification.json'
prior = json.loads(prior_path.read_text())
wall_path = output / 'wall-verification.json'
wall = json.loads(wall_path.read_text())
assert wall['priorReplaySha256'] == sha(prior_path)
build_path = root / 'window-movie-input/build.json'
build = json.loads(build_path.read_text())
assert sha(build_path) == prior['buildSha256']
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
component_path = root / 'window-movie-input/component-verification.json'
component = json.loads(component_path.read_text())
assert sha(component_path) == prior['componentSha256']
original_fixture = Path(component['executablePath']).parent / 'frame.cpp'
assert sha(original_fixture) == component['fixtureSourceSha256']
text = original_fixture.read_text()
before = '        ctx.msr = (ctx.msr | 0x2000u) & ~0x8000u;'
assert text.count(before) == 1
after = '''        ctx.tb_freq = 60750000;
        ctx.msr = (ctx.msr | 0x2000u) & ~0x8000u;
        if (std::getenv("SHSM_REPLAY_EE1")) { ctx.msr |= 0x8000u; }'''
text = text.replace(before, after, 1)
temporary = Path(tempfile.mkdtemp(prefix='openshsm-packet-context-', dir='/private/tmp'))
source, obj, exe = temporary / 'frame.cpp', temporary / 'frame.cpp.o', temporary / 'frame'
source.write_text(text)
flags = build['changes']['37']['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
    '-I', str(root / 'window-movie-input'), '-c', str(source), '-o', str(obj)],
    capture_output=True, text=True, timeout=60)
assert result.returncode == 0, result.stderr[-2500:]
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert result.returncode == 0, result.stderr[-2500:]
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
assert sha(snapshot) == prior['snapshotSha256']
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_WALLTB'] = '1'
rows = []
for iteration in range(3):
    cases = prior['cases'] if iteration % 2 == 0 else list(reversed(prior['cases']))
    modes = (0, 1) if iteration % 2 == 0 else (1, 0)
    for case in cases:
        packet = Path(case['packetPath'])
        assert sha(packet) == case['selectedLiveRecord']['capture']['packetSha256']
        reference = output / f'{case["movie"].lower()}-0.yuv'
        original_state = Path(str(reference) + '.state').read_bytes()
        msr_offset = 32 * 4 + 8 * 4 + 32 * 8 + 32 * 8 + 8 * 4 + 4 * 4
        original_msr = struct.unpack_from('<I', original_state, msr_offset)[0]
        assert original_msr & 0x2000 and not original_msr & 0x8000
        for mode in modes:
            raw = output / f'{case["movie"].lower()}-clock6075-ee{mode}-{iteration}.yuv'
            assert not raw.exists()
            selected_env = dict(env)
            if mode:
                selected_env['SHSM_REPLAY_EE1'] = '1'
            run = subprocess.run([str(exe), str(snapshot), str(raw), str(packet)], env=selected_env,
                capture_output=True, text=True, timeout=30)
            log = raw.with_suffix('.log')
            log.write_text(run.stdout + run.stderr)
            assert run.returncode == 0, run.stderr[-2500:]
            match = re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', run.stdout)
            assert match and raw.read_bytes() == reference.read_bytes()
            state_path = Path(str(raw) + '.state')
            state = bytearray(state_path.read_bytes())
            msr = struct.unpack_from('<I', state, msr_offset)[0]
            assert bool(msr & 0x8000) == bool(mode)
            struct.pack_into('<I', state, msr_offset, msr & ~0x8000)
            assert state == original_state
            rows.append({'movie': case['movie'], 'ee': mode, 'iteration': iteration,
                'decoderNs': int(match[1]), 'outputSha256': sha(raw), 'rawStateSha256': sha(state_path),
                'normalizedStateSha256': hashlib.sha256(state).hexdigest(), 'logSha256': sha(log)})
summary = []
for case in prior['cases']:
    summary.append({'movie': case['movie'], 'frame': case['selectedLiveRecord']['moduloPositionMatches'][0]['frame'],
        'wall6075EE0MedianUs': statistics.median(row['decoderNs'] / 1000 for row in rows if row['movie'] == case['movie'] and row['ee'] == 0),
        'wall6075EE1MedianUs': statistics.median(row['decoderNs'] / 1000 for row in rows if row['movie'] == case['movie'] and row['ee'] == 1),
        'liveWallUs': case['selectedLiveRecord']['wallUs']})
(output / 'context-verification.json').write_text(json.dumps({
    'result': 'PACKET_WALL6075_EE_MODES_YUV_STATE_EQUAL18', 'buildSha256': sha(build_path),
    'priorReplaySha256': sha(prior_path), 'wallReplaySha256': sha(wall_path),
    'originalFixtureSha256': sha(original_fixture), 'sourceSha256': sha(source), 'objectSha256': sha(obj),
    'executablePath': str(exe), 'executableSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
    'fixturePatch': [before, after], 'msrOffset': msr_offset, 'timebaseFrequency': 60750000,
    'rows': rows, 'summary': summary,
    'limits': ['Live clock mode/frequency and EEbit controlled in isolated existing decoder fixture, not live game changes.',
        'Exact packet/full YUV/selected PPC state equal after only explicitly requested EEbit normalization.',
        'No active GUI/device IRQ producers or live pending callback state; EE1 alone is not real interrupt delivery.',
        'Earlier PUBDEV snapshot/relocated input/device state still differ; residual not scheduler-exclusive CPU proof.',
        'No visual/audio/profile/save/controller/hardware/live FPS acceptance or promotion.']}, indent=2) + '\n')
print('PACKET_WALL6075_EE_MODES_YUV_STATE_EQUAL18')
print(json.dumps(summary, indent=2))
