"""Time verified original function entry/returns in the complete-frame fixture only."""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--build', choices=('headless-constant-fp', 'headless-psq-scale'), default='headless-constant-fp')
args = parser.parse_args()

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / ('headless-thp-snapshot/phase-profile' if args.build == 'headless-constant-fp'
    else 'headless-thp-snapshot/psq-phase-profile')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / args.build / 'build.json'
base = json.loads(parent_path.read_text())
for path, expected in {**base['dependencies'], **base['retainedLinkInputs']}.items():
    assert sha(Path(path)) == expected
guard_parent_path = root / 'headless-constant-fp/build.json'
guard_parent = json.loads(guard_parent_path.read_text())
if args.build == 'headless-psq-scale':
    assert sha(guard_parent_path) == base['baseBuildSha256']
for path, expected in guard_parent['dependencies'].items():
    assert sha(Path(path)) == expected
command = list(base['linkCommand'])
old = next(Path(arg) for arg in command if Path(arg).name == 'output_37.cpp.o')
original = old.with_suffix('')
assert sha(original) == base['sourceSha256']
text = original.read_text()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
entries = [0x80209D80, 0x8020AC70, 0x8020B900, 0x8020AFD0, 0x8020B460]
sites = []
for slot, entry in enumerate(entries):
    start = text.index(f'void func_{entry:08X}(CPUContext& ctx) {{')
    end = text.index('\nvoid func_', start + 1)
    body = text[start:end]
    points = [(entry, int(re.search(rf'// 0x{entry:08X}: ([0-9A-F]{{8}})', body)[1], 16))]
    points += [(int(address, 16), 0x4E800020) for address in re.findall(r'// 0x([0-9A-F]{8}): 4E800020', body)]
    assert len(points) > 1
    for address, opcode in points:
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == opcode
    marker = f'void func_{entry:08X}(CPUContext& ctx) {{'
    body = body.replace(marker, marker + '\n    const auto phase_started = std::chrono::steady_clock::now();', 1)
    for address, opcode in points[1:]:
        marker = f'    // 0x{address:08X}: {opcode:08X}\n'
        assert body.count(marker) == 1
        body = body.replace(marker, marker + f'    phase_record({slot}, phase_started);\n')
    text = text[:start] + body + text[end:]
    sites.extend(points)
helper = '''#include <array>
#include <chrono>
#include <cstdio>
static std::array<uint64_t, 5> phase_counts{}, phase_ns{};
static void phase_record(unsigned slot, std::chrono::steady_clock::time_point started) {
    phase_ns[slot] += std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - started).count();
    ++phase_counts[slot];
}
extern "C" void report_decoder_phases() {
    for (unsigned slot = 0; slot < 5; ++slot) {
        std::printf("THP_PHASE slot=%u count=%llu ns=%llu\\n", slot,
            (unsigned long long)phase_counts[slot], (unsigned long long)phase_ns[slot]);
    }
}
'''
source, obj = output / 'output_37.cpp', output / 'output_37.cpp.o'
source.write_text(helper + text)
record = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'], '-I', str(original.parent),
    '-I', str(root / 'headless-constant-fp'),
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command[command.index(str(old))] = str(obj)
fixture_root = root / 'headless-thp-snapshot/hm1ply-frame15-replay'
proof_path = fixture_root / 'verification.json'
proof = json.loads(proof_path.read_text())
fixture_original = fixture_root / 'probe.cpp'
assert sha(fixture_original) == proof['probeSourceSha256']
fixture_text = fixture_original.read_text()
marker = '        std::cout << "COMPLETE_FRAME_REPLAY_RETURN0 ns=" << ns << \'\\n\';'
assert fixture_text.count(marker) == 1
fixture_text = 'extern "C" void report_decoder_phases();\n' + fixture_text.replace(marker, marker + '\n        report_decoder_phases();')
fixture_source, fixture_obj = output / 'probe.cpp', output / 'probe.cpp.o'
fixture_source.write_text(fixture_text)
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *record['arguments'],
    '-c', str(fixture_source), '-o', str(fixture_obj)], capture_output=True, text=True, timeout=180)
(output / 'probe-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-2000:]
command[command.index(str(root / 'headless-tev-banks/main.cpp.o'))] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(fixture_obj))
exe = output / 'phase-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
packet = fixture_root / 'hm1ply-frame15.packet'
assert sha(snapshot) == proof['snapshotSha256'] and sha(packet) == proof['packetSha256']
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
rows = []
for iteration in range(3):
    raw = output / f'frame-{iteration}.yuv'
    result = subprocess.run([str(exe), str(snapshot), str(raw), str(packet)], env=env,
        capture_output=True, text=True, timeout=30)
    log = output / f'run-{iteration}.log'
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert sha(raw) == proof['rows'][0]['outputSha256']
    phases = [{'entry': entries[int(slot)], 'count': int(count), 'nanoseconds': int(ns)}
        for slot, count, ns in re.findall(r'THP_PHASE slot=(\d+) count=(\d+) ns=(\d+)', result.stdout)]
    assert len(phases) == 5
    rows.append({'phases': phases, 'outputSha256': sha(raw), 'logSha256': sha(log)})
(output / 'verification.json').write_text(json.dumps({'result': 'NATIVE_DECODER_PHASE_PROFILE_BYTE_IDENTICAL3',
    'parentBuildSha256': sha(parent_path), 'sourceSha256': sha(source), 'fixtureSourceSha256': sha(fixture_source),
    'executableSha256': sha(exe), 'fixtureProofSha256': sha(proof_path), 'sites': sites,
    'guardParentBuildSha256': sha(guard_parent_path), 'guardDependencies': guard_parent['dependencies'],
    'verifierSha256': sha(Path(__file__).resolve()), 'rows': rows,
    'limits': ['Inclusive host wall timers at original entries/BLR, nested phases not additive.',
        'Single-thread FP-active/EE-disabled fixture; instrumentation/compiler layout overhead, not original Wii or live FPS.',
        'One guest object instrumented; original instruction/arithmetic/runtime retained, output exact.']}, indent=2) + '\n')
print('NATIVE_DECODER_PHASE_PROFILE_BYTE_IDENTICAL3')
print(json.dumps(rows[0]['phases'], indent=2))
