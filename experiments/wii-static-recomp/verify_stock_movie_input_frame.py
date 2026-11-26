"""Capture an actual CPUContext snapshot packet, then prove the existing exact complete-frame replay unchanged."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-movie-input'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
restored = (output / 'stock_movie_timing.h').read_text()
for before, after in reversed(build['headerPatches']):
    assert restored.count(after) == 1
    restored = restored.replace(after, before, 1)
assert restored == (root / 'window-cpu-time/stock_movie_timing.h').read_text()
for unit, change in build['changes'].items():
    assert sha(Path(change['originalPath'])) == change['originalSha256']
    assert (output / f'output_{unit}.cpp').read_bytes() == Path(change['originalPath']).read_bytes()
    assert sha(output / f'output_{unit}.cpp.o') == change['objectSha256']
fixture_original = root / 'window-decoder-o3/frame-probe.cpp'
source = fixture_original.read_text()
marker = '        load(ctx, argv[1]);'
assert source.count(marker) == 1
source = '#include "stock_movie_input.h"\n' + source.replace(marker, marker + '''
        stock_movie_input::Packet captured;
        if (!stock_movie_input::prepare(ctx, captured)) { return 30; }
        const auto original_gpr = ctx.gpr;
        const auto original_mem1 = ctx.mmu.mem1;
        const auto original_mem2 = ctx.mmu.mem2;
        stock_movie_input::observe(ctx, 0x8009C5E0, 0);
        if (original_gpr != ctx.gpr || original_mem1 != ctx.mmu.mem1 || original_mem2 != ctx.mmu.mem2) { return 31; }
''', 1)
temporary = Path(tempfile.mkdtemp(prefix='openshsm-movie-input-frame-', dir='/private/tmp'))
fixture, fixture_obj, exe = temporary / 'frame.cpp', temporary / 'frame.cpp.o', temporary / 'frame'
fixture.write_text(source)
arguments = build['changes']['37']['arguments']
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-I', str(output), '-c', str(fixture), '-o', str(fixture_obj)], capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-2500:]
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(fixture_obj))
command[command.index('-o') + 1] = str(exe)
linked = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-2500:]
prior_path = root / 'movie-packet-metadata/verification.json'
prior = json.loads(prior_path.read_text())
proof = json.loads((root / 'window-decoder-o3/verification.json').read_text())
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
packet = root / 'headless-thp-snapshot/hm1ply-frame15-replay/hm1ply-frame15.packet'
assert sha(snapshot) == proof['snapshotSha256'] == prior['snapshotSha256']
assert sha(packet) == proof['packetSha256']
reference = root / 'window-decoder-o3/baseline-0.yuv'
rows = []
for iteration in range(3):
    raw = output / f'probe-{iteration}.yuv'
    timing = output / f'probe-{iteration}-timing.jsonl'
    assert not timing.exists()
    env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
    env['NWII_MOVIE_TIMING'] = str(timing)
    result = subprocess.run([str(exe), str(snapshot), str(raw), str(packet)], env=env,
        capture_output=True, text=True, timeout=30)
    log = output / f'probe-{iteration}.log'
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-2000:]
    assert raw.read_bytes() == reference.read_bytes()
    assert Path(str(raw) + '.state').read_bytes() == Path(str(reference) + '.state').read_bytes()
    data = Path(str(timing) + '.inputs.bin')
    metadata = Path(str(timing) + '.inputs.jsonl')
    captured_rows = [json.loads(line) for line in metadata.read_text().splitlines()]
    assert sha(data) == prior['packetSha256'] and len(captured_rows) == 1
    assert captured_rows[0]['bytes'] == prior['packetBytes'] and captured_rows[0]['input'] == prior['packetAddress']
    events = [json.loads(line) for line in timing.read_text().splitlines()]
    assert [row['site'] for row in events] == [0x80209D80, 0x8020A044]
    rows.append({'outputSha256': sha(raw), 'stateSha256': sha(Path(str(raw) + '.state')),
        'capturedPacketSha256': sha(data), 'metadataSha256': sha(metadata), 'logSha256': sha(log),
        'wallUs': events[1]['hostUs'] - events[0]['hostUs']})
(output / 'component-verification.json').write_text(json.dumps({
    'result': 'ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3', 'buildSha256': sha(build_path),
    'priorMetadataEvidenceSha256': sha(prior_path), 'fixtureSourceSha256': sha(fixture),
    'fixtureObjectSha256': sha(fixture_obj), 'executablePath': str(exe), 'executableSha256': sha(exe),
    'verifierSha256': sha(Path(__file__)), 'rows': rows,
    'limits': ['Actual native CPUContext loaded from prior entry snapshot; observer capture preserves GPR/full MEM1/MEM2.',
        'Captured original PUBDEV packet exact, then HM1PLY15 replay exact complete YUV/selected final PPC state.',
        'Caller observer explicitly invoked by fixture, not full caller or live scheduler/IRQ verification.',
        'Live128packet/16MiB cap and playback-position identification/FPS/audio/profile/hardware still pending.']}, indent=2) + '\n')
print('ACTUAL_CONTEXT_PACKET_CAPTURE_FRAME_STATE_IDENTICAL3', rows)
