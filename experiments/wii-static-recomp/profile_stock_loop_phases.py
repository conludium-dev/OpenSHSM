"""Instrument existing decoder phase boundaries on exact captured LOOP packets."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import statistics
import struct
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--replay-proof', type=Path, required=True)
args = parser.parse_args()
proof_path = args.replay_proof.resolve()
proof = json.loads(proof_path.read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert proof['result'] == 'BP_ORDER_LOOP_SAME_PACKETS_ISOLATED_CLOCK_EE_ENDPOINTS_EQUAL27'
assert all(sha(path) == digest for path, digest in proof['dependencies'].items())
project = Path(__file__).resolve().parents[2]
root = project / 'work/private-game/static-recomp/stock-baseline'
recipe_path = root / 'window-movie-late/build.json'
recipe = json.loads(recipe_path.read_text())['changes']['37']
original_object = Path(next(arg for arg in proof['linkCommand'] if Path(arg).name == 'output_37.cpp.o'))
assert original_object.parent == recipe_path.parent
original = original_object.with_suffix('')
assert sha(original) == recipe['sourceSha256'] and sha(original_object) == recipe['objectSha256']
assert str(original_object) in proof['linkCommand']
assert '-O3' in recipe['arguments'] and '-ffp-contract=off' in recipe['arguments']
text = original.read_text()
dol_path = project / 'work/private-game/disc/DATA/sys/main.dol'
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
entries = [0x80209D80, 0x8020AC70, 0x8020B900, 0x8020AFD0, 0x8020B460,
    0x8020BDB0, 0x8020C430, 0x8020CAD0]
sites, patches = [], []
for slot, entry in enumerate(entries):
    marker = f'void func_{entry:08X}(CPUContext& ctx) {{'
    start = text.index(marker)
    end = text.find('\nvoid func_', start + 1)
    if end < 0:
        end = len(text)
    before = text[start:end]
    points = [(entry, int(re.search(rf'// 0x{entry:08X}: ([0-9A-F]{{8}})', before)[1], 16))]
    points += [(int(address, 16), 0x4E800020) for address in re.findall(r'// 0x([0-9A-F]{8}): 4E800020', before)]
    assert len(points) > 1
    for address, word in points:
        section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
        assert struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0] == word
    after = before.replace(marker, marker + '\n    const auto phase_started = std::chrono::steady_clock::now();', 1)
    for address, word in points[1:]:
        ret = f'    // 0x{address:08X}: {word:08X}\n'
        assert after.count(ret) == 1
        after = after.replace(ret, ret + f'    loop_phase_record({slot}, phase_started);\n', 1)
    patches.append([before, after])
    text = text[:start] + after + text[end:]
    sites.extend(points)
restored = text
for before, after in reversed(patches):
    restored = restored.replace(after, before, 1)
assert restored == original.read_text()
helper = '''#include <array>
#include <chrono>
#include <cstdio>
static std::array<uint64_t, 8> loop_phase_counts{}, loop_phase_ns{};
static void loop_phase_record(unsigned slot, std::chrono::steady_clock::time_point started) {
    loop_phase_ns[slot] += std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - started).count();
    ++loop_phase_counts[slot];
}
extern "C" void report_loop_phases() {
    for (unsigned slot = 0; slot < 8; ++slot) {
        std::printf("LOOP_PHASE slot=%u count=%llu ns=%llu\\n", slot,
            (unsigned long long)loop_phase_counts[slot], (unsigned long long)loop_phase_ns[slot]);
    }
}
'''
cache = Path(tempfile.mkdtemp(prefix='openshsm-loop-phases-', dir='/private/tmp'))
source, obj = cache / 'output_37.cpp', cache / 'output_37.cpp.o'
source.write_text(helper + text)
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *recipe['arguments'],
    '-I', str(original.parent), '-I', str(root / 'headless-psq-scale'), '-c', str(source), '-o', str(obj)]
print('Compiling owned phase-only decoder', cache, flush=True)
compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
(cache / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
prior_path = root / 'late-packet-replay/verification.json'
prior = json.loads(prior_path.read_text())
fixture_original = Path(prior['linkCommand'][1]).with_suffix('')
assert sha(fixture_original) == prior['sourceSha256']
fixture_text = fixture_original.read_text()
marker = '        std::cout << "COMPLETE_FRAME_REPLAY_RETURN0 ns=" << ns << \'\\n\';'
assert fixture_text.count(marker) == 1
fixture_source, fixture_obj = cache / 'frame.cpp', cache / 'frame.cpp.o'
fixture_source.write_text('extern "C" void report_loop_phases();\n' + fixture_text.replace(marker,
    marker + '\n        report_loop_phases();'))
flags_path = root / 'window-movie-late/build.json'
flags = json.loads(flags_path.read_text())['changes']['37']['arguments']
fixture_command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
    '-c', str(fixture_source), '-o', str(fixture_obj)]
compiled = subprocess.run(fixture_command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(proof['linkCommand'])
link[link.index(str(original_object))] = str(obj)
link[link.index(prior['linkCommand'][1])] = str(fixture_obj)
exe = cache / 'frame'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
assert sha(snapshot) == prior['snapshotSha256']
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env.update(NWII_WALLTB='1', SHSM_REPLAY_EE1='1')
rows = []
for iteration in range(3):
    for case in proof['cases']:
        reference = next(row for row in proof['rows'] if row['label'] == case['label']
            and row['mode'] == 'wall-ee1' and row['iteration'] == 0)
        assert sha(reference['outputPath']) == reference['outputSha256']
        assert sha(str(reference['outputPath']) + '.state') == reference['rawStateSha256']
        raw = cache / f'{case["label"]}-{iteration}.yuv'
        run = subprocess.run([str(exe), str(snapshot), str(raw), case['packetPath']],
            env=env, capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stdout + run.stderr
        assert raw.read_bytes() == Path(reference['outputPath']).read_bytes()
        assert Path(str(raw) + '.state').read_bytes() == Path(str(reference['outputPath']) + '.state').read_bytes()
        phases = [{'entry': entries[int(slot)], 'count': int(count), 'nanoseconds': int(ns)}
            for slot, count, ns in re.findall(r'LOOP_PHASE slot=(\d+) count=(\d+) ns=(\d+)', run.stdout)]
        assert len(phases) == 8
        log = raw.with_suffix('.log')
        log.write_text(run.stdout + run.stderr)
        rows.append({'label': case['label'], 'iteration': iteration, 'phases': phases,
            'outputPath': str(raw), 'outputSha256': sha(raw), 'stateSha256': sha(str(raw) + '.state'),
            'logPath': str(log), 'logSha256': sha(log)})
summary = []
for case in proof['cases']:
    selected = [row for row in rows if row['label'] == case['label']]
    summary.append({'label': case['label'], 'phases': [{'entry': entry,
        'counts': sorted({row['phases'][slot]['count'] for row in selected}),
        'medianMs': statistics.median(row['phases'][slot]['nanoseconds'] for row in selected) / 1e6}
        for slot, entry in enumerate(entries)]})
report = {'result': 'CURRENT_LOOP_PHASE_O3_FULL_YUV_SELECTED_PPC_EQUAL9',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), proof_path, recipe_path,
        original, original_object, dol_path, prior_path, fixture_original, snapshot, flags_path]},
    'sites': sites, 'sourcePath': str(source), 'sourceSha256': sha(source), 'patches': patches,
    'fixtureSourcePath': str(fixture_source), 'fixtureSourceSha256': sha(fixture_source),
    'compileCommand': command, 'fixtureCompileCommand': fixture_command, 'linkCommand': link,
    'executablePath': str(exe), 'executableSha256': sha(exe), 'rows': rows, 'summary': summary,
    'limits': ['Inclusive host wall timers, nested phases are not additive; instrumentation/layout perturbs timings.',
        'Same owned packets/current code but earlier isolated snapshot, not live IRQ/device context or physical Wii oracle.',
        'No game/runtime optimization or live FPS improvement; private instrumentation only.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(summary, indent=2))
