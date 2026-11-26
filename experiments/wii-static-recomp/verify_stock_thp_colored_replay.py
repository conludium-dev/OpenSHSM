"""Decode one owned INTRO packet in the captured native fixture; not full original movie lifecycle."""
from pathlib import Path
import ast
import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
parser = argparse.ArgumentParser()
parser.add_argument('--movie', choices=('INTRO', 'HM1PLY', 'LOOP'), default='INTRO')
parser.add_argument('--frame', type=int, default=60)
parser.add_argument('--baseline-build', choices=('headless-movie-timing', 'headless-constant-fp'), default='headless-movie-timing')
parser.add_argument('--candidate-build', choices=('headless-constant-fp', 'headless-psq-scale'), default='headless-constant-fp')
parser.add_argument('--name')
args = parser.parse_args()
assert args.frame >= 0
directory = 'colored-replay' if (args.movie, args.frame) == ('INTRO', 60) else f'{args.movie.lower()}-frame{args.frame}-replay'
if args.name:
    assert args.name.replace('-', '').isalnum()
    directory = args.name
output = root / 'headless-thp-snapshot' / directory
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
proof_path = root / 'headless-thp-snapshot/replay/verification.json'
proof = json.loads(proof_path.read_text())
assert proof['result'] == 'COMPLETE_FRAME_REPLAY_LIVE_BYTES_IDENTICAL2' and sha(snapshot) == proof['snapshotSha256']
game = Path('work/private-game/disc/DATA/files/MOVIES', args.movie).resolve()
data = game.read_bytes()
word = lambda offset: int.from_bytes(data[offset:offset + 4], 'big')
assert data[:4] == b'THP\0' and (word(0x44), word(0x48)) == (640, 480)
offset, size = word(0x28), word(0x18)
frame = args.frame
assert word(0x14) > frame
for i in range(frame):
    assert offset + size <= len(data)
    following = word(offset)
    offset += size
    size = following
length = word(offset + 8)
assert length <= size - 16 and offset + size <= len(data)
packet = data[offset + 16:offset + 16 + length]
assert packet[:2] == b'\xff\xd8' and 2 <= len(packet) <= 65536
packet_path = output / f'{args.movie.lower()}-frame{frame}.packet'
packet_path.write_bytes(packet)
ffmpeg = Path('work/research/video-tools/macos-arm64/package/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1').resolve()
reference_command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(game),
    '-vf', f'select=eq(n\\,{frame})', '-frames:v', '1', '-an', '-pix_fmt', 'yuvj420p', '-f', 'rawvideo', 'pipe:1']
reference = subprocess.run(reference_command, capture_output=True, check=True, timeout=60).stdout
assert len(reference) == 460800
tree = ast.parse((public / 'compare_stock_thp.py').read_text())
helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('untile', 'metrics')]
assert len(helpers) == 2
scope = {}
exec(compile(ast.Module(body=helpers, type_ignores=[]), 'existing_thp_comparison_helpers', 'exec'), scope)
original = public / 'stock_thp_frame_replay.cpp'
text = original.read_text()
assert text.count('if (argc != 3)') == 1
text = '#include <algorithm>\n#include <iterator>\n' + text.replace('if (argc != 3)', 'if (argc != 4)')
marker = '        const auto caller = ctx.lr;'
assert text.count(marker) == 1
text = text.replace(marker, '''        std::ifstream packet_file(argv[3], std::ios::binary);
        const std::vector<uint8_t> packet{std::istreambuf_iterator<char>(packet_file), std::istreambuf_iterator<char>()};
        if (packet.size() < 2 || packet.size() > 65536 || packet[0] != 0xFF || packet[1] != 0xD8) {
            return 14;
        }
        auto begin = ctx.mmu.mem2.begin() + 0x02000000;
        auto end = ctx.mmu.mem2.begin() + 0x03D00000;
        auto available = std::search_n(begin, end, packet.size() + 31, uint8_t(0));
        if (available == end) {
            return 14;
        }
        const uint32_t offset = (uint32_t(available - ctx.mmu.mem2.begin()) + 31) & ~31u;
        auto* target = ctx.mmu.mem2.data() + offset;
        std::copy(packet.begin(), packet.end(), target);
        ctx.gpr[3] = 0x90000000 + offset;
        std::cout << "THP_FIXTURE_INPUT " << std::hex << ctx.gpr[3] << std::dec << '\\n';
''' + marker)
source, obj = output / 'probe.cpp', output / 'probe.cpp.o'
source.write_text(text)
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
executables = {}
for name in (args.baseline_build, args.candidate_build):
    build_path = root / name / 'build.json'
    build = json.loads(build_path.read_text())
    for path, expected in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(Path(path)) == expected
    command = list(build['linkCommand'])
    archive = next(Path(arg) for arg in command if Path(arg).name == 'libnwiiruntime.a')
    assert sha(archive) == build['archiveSha256']
    command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    exe = output / (name + '-replay')
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
    executables[name] = {'path': str(exe), 'sha256': sha(exe), 'buildSha256': sha(build_path)}
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
rows, values = [], []
for iteration in range(5):
    order = list(executables) if iteration % 2 == 0 else list(reversed(executables))
    for name in order:
        raw = output / f'{name}-{iteration}.yuv'
        result = subprocess.run([executables[name]['path'], str(snapshot), str(raw), str(packet_path)],
            env=env, capture_output=True, text=True, timeout=30)
        log = output / f'{name}-{iteration}.log'
        log.write_text(result.stdout + result.stderr)
        assert result.returncode == 0, (name, result.returncode, result.stdout, result.stderr)
        match = re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', result.stdout)
        assert match
        values.append(raw.read_bytes())
        rows.append({'variant': name, 'iteration': iteration, 'nanoseconds': int(match[1]),
            'outputSha256': sha(raw), 'logSha256': sha(log)})
assert all(value == values[0] for value in values) and len(values[0]) == 460800
planes, position = {}, 0
for name, width, height in [('Y', 640, 480), ('U', 320, 240), ('V', 320, 240)]:
    count = width * height
    actual = scope['untile'](values[0][position:position + count], width, height)
    planes[name] = scope['metrics'](actual, reference[position:position + count], width)
    position += count
medians = {name: statistics.median(row['nanoseconds'] for row in rows if row['variant'] == name) for name in executables}
report = {'result': 'COLORED_COMPLETE_FRAME_NATIVE_BYTES_IDENTICAL10', 'movie': args.movie, 'executables': executables,
    'gameSha256': sha(game), 'frame': frame, 'packetSha256': sha(packet_path), 'snapshotSha256': sha(snapshot),
    'referenceSha256': hashlib.sha256(reference).hexdigest(), 'ffmpegSha256': sha(ffmpeg), 'referenceCommand': reference_command,
    'probeSourceSha256': sha(source), 'originalReplaySourceSha256': sha(original), 'whiteFrameProofSha256': sha(proof_path),
    'comparisonHelpersSha256': sha(public / 'compare_stock_thp.py'), 'verifierSha256': sha(Path(__file__).resolve()),
    'rows': rows, 'medianNs': medians, 'referencePlaneMetrics': planes,
    'limits': ['Same captured native RAM/registers, new owned640x480moviepacket in verified-zero aligned RAM within92000000..93D00000.',
        'Explicit FP-active/EE-disabled fixture; not original INTRO caller/boot/device/IRQ lifecycle or Wii hardware oracle.',
        'Complete native output invariant across10alternating replays, not byte-identical FFmpeg or GPU/rendered FPS acceptance.']}
(output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], json.dumps(medians))
print(json.dumps({name: {key: value[key] for key in ('meanAbsoluteError', 'maxAbsoluteError', 'actualRange')} for name, value in planes.items()}, indent=2))
