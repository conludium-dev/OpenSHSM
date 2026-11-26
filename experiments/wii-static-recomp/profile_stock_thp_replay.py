"""Repeat the verified complete VHS fixture for bounded native sampling, not game FPS."""
from pathlib import Path
import hashlib
import argparse
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
parent = root / 'headless-thp-snapshot/hm1ply-frame15-replay'
parser = argparse.ArgumentParser()
parser.add_argument('--iterations', type=int, default=200)
parser.add_argument('--name', default='decoder-profile')
args = parser.parse_args()
assert 1 <= args.iterations <= 800 and args.name.replace('-', '').isalnum()
output = root / 'headless-thp-snapshot' / args.name
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
proof_path = parent / 'verification.json'
proof = json.loads(proof_path.read_text())
assert proof['result'] == 'COLORED_COMPLETE_FRAME_NATIVE_BYTES_IDENTICAL10'
original = parent / 'probe.cpp'
assert sha(original) == proof['probeSourceSha256']
text = original.read_text()
marker = '        load(ctx, argv[1]);'
assert text.count(marker) == 1
text = text.replace(marker, f'        std::vector<uint8_t> reference;\n        for (unsigned iteration = 0; iteration < {args.iterations}; ++iteration) {{\n' + marker)
marker = '        std::ofstream output(argv[2], std::ios::binary);'
assert text.count(marker) == 1
text = text.replace(marker, '''        std::vector<uint8_t> pixels;
        for (const auto& [address, size] : {std::pair{y, 307200u}, std::pair{u, 76800u}, std::pair{v, 76800u}}) {
            auto* pointer = ctx.mmu.get_ptr(address);
            pixels.insert(pixels.end(), pointer, pointer + size);
        }
        if (iteration == 0) { reference = pixels; }
        if (pixels != reference) { return 15; }
''' + marker)
marker = '        std::cout << "COMPLETE_FRAME_REPLAY_RETURN0 ns=" << ns << \'\\n\';'
assert text.count(marker) == 1
text = text.replace(marker, marker + '\n        }')
source, obj = output / 'profile.cpp', output / 'profile.cpp.o'
source.write_text(text)
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
build_path = root / 'headless-constant-fp/build.json'
build = json.loads(build_path.read_text())
for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
command = list(build['linkCommand'])
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'decoder-profile'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
packet = parent / 'hm1ply-frame15.packet'
assert sha(snapshot) == proof['snapshotSha256'] and sha(packet) == proof['packetSha256']
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
raw, log = output / 'last-frame.yuv', output / 'run.log'
with log.open('w') as stream:
    process = subprocess.Popen([str(exe), str(snapshot), str(raw), str(packet)], env=env, stdout=stream, stderr=stream)
    print('Decoder profile PID', process.pid, flush=True)
    timed_out = False
    try:
        code = process.wait(timeout=120)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.terminate()
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            code = process.wait(timeout=5)
assert process.poll() is not None
report = {'pid': process.pid, 'terminalReturncode': code, 'deadlineReached': timed_out,
    'iterations': args.iterations,
    'sourceSha256': sha(source), 'executableSha256': sha(exe), 'buildSha256': sha(build_path),
    'fixtureProofSha256': sha(proof_path), 'snapshotSha256': sha(snapshot), 'packetSha256': sha(packet),
    'recipeSha256': sha(Path(__file__).resolve()), 'logSha256': sha(log),
    'limits': ['Identical finite640x480native decodes, snapshot reload/file I/O also in process.',
        'Per-iteration complete pixels compared, no game FPS/GPU/live IRQ or original Wii timing proof.']}
if code == 0:
    expected = next(row['outputSha256'] for row in proof['rows'] if row['variant'] == 'headless-constant-fp')
    assert sha(raw) == expected and log.read_text().count('COMPLETE_FRAME_REPLAY_RETURN0') == args.iterations
    report['outputSha256'] = sha(raw)
(output / 'run.json').write_text(json.dumps(report, indent=2) + '\n')
assert code == 0, (code, timed_out)
print('REPEATED_COMPLETE_FRAME_PASS', args.iterations)
