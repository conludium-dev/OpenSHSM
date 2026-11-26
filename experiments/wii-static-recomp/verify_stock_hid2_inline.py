"""Retained guard differential plus alternating same-frame replays on the current full runtime."""
from pathlib import Path
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
parser.add_argument('--candidate', choices=('window-hid2-inline', 'window-decoder-o3'), default='window-hid2-inline')
args = parser.parse_args()
output = root / args.candidate
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedInputs']}.items():
    assert sha(Path(path)) == digest
old_guard = (root / 'headless-constant-fp/constant_fp_guard.h').read_text()
restored = (output / 'constant_fp_guard.h').read_text().replace(build['accessorBody'] + '\n', '', 1)
assert restored.replace('stock_inline_read_hid2(ctx)', 'experiment_read_hid2(ctx)') == old_guard
assert (output / 'output_37.cpp').read_bytes() == (root / 'headless-psq-scale/output_37.cpp').read_bytes()
assert sha(Path(build['linkCommand'][build['linkCommand'].index('-o') + 1])) == build['executableSha256']
opcodes = sorted(set(row['opcode'] for row in json.loads((root / 'headless-constant-fp/build.json').read_text())['sites']))
cases = '#pragma once\n#include "constant_fp_guard.h"\n#include <array>\nusing namespace nwii::runtime;\n'
cases += 'struct GuardCase { uint32_t opcode; bool uses_fp; void (*call)(CPUContext&, uint32_t); };\n'
cases += f'inline const std::array<GuardCase, {len(opcodes)}> cases = {{{{\n'
cases += ''.join(f'{{0x{x:08X}, stock_constant_uses_fp(0x{x:08X}), &stock_constant_fp_preinstruction<0x{x:08X}>}},\n' for x in opcodes)
cases += '}};\n'
(output / 'constant_fp_cases.h').write_text(cases)
guard_source, guard_obj = public / 'stock_constant_fp_probe.cpp', output / 'guard-probe.cpp.o'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'], '-I', str(output),
    '-c', str(guard_source), '-o', str(guard_obj)], capture_output=True, text=True, timeout=180)
assert result.returncode == 0, result.stderr[-2000:]
def link(command, obj, executable):
    command = list(command)
    main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    command[command.index('-o') + 1] = str(executable)
    subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
guard_exe = output / 'guard-probe'
link(build['linkCommand'], guard_obj, guard_exe)
result = subprocess.run([str(guard_exe)], capture_output=True, text=True, timeout=30)
(output / 'guard-probe.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and f'CONSTANT_FP_DIFFERENTIAL_PASS {len(opcodes)*40}' in result.stdout
fixture = root / 'headless-thp-snapshot/hm1ply-frame15-replay'
proof_path = fixture / 'verification.json'
proof = json.loads(proof_path.read_text())
fixture_original, fixture_source, fixture_obj = fixture / 'probe.cpp', output / 'frame-probe.cpp', output / 'frame-probe.cpp.o'
assert sha(fixture_original) == proof['probeSourceSha256']
fixture_text = fixture_original.read_text()
marker = '        std::cout << "COMPLETE_FRAME_REPLAY_RETURN0 ns=" << ns << \'\\n\';'
assert fixture_text.count(marker) == 1
state_dump = '''
        std::ofstream state_file(std::string(argv[2]) + ".state", std::ios::binary);
        auto write_state = [&](const auto& value) {
            state_file.write(reinterpret_cast<const char*>(&value), sizeof(value));
        };
        write_state(ctx.gpr); write_state(ctx.gqr); write_state(ctx.fpr); write_state(ctx.ps1); write_state(ctx.cr);
        write_state(ctx.pc); write_state(ctx.lr); write_state(ctx.ctr); write_state(ctx.xer); write_state(ctx.msr);
        write_state(ctx.fpscr); write_state(ctx.srr0); write_state(ctx.srr1); write_state(ctx.inst_count); write_state(ctx.hid2);
        if (!state_file) { return 21; }
'''
fixture_source.write_text(fixture_text.replace(marker, marker + state_dump))
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *build['arguments'],
    '-c', str(fixture_source), '-o', str(fixture_obj)], capture_output=True, text=True, timeout=180)
assert result.returncode == 0, result.stderr[-2000:]
parent_path = root / 'window-audio-callback/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
executables = {}
for label, command in [('baseline', parent['linkCommand']), ('candidate', build['linkCommand'])]:
    exe = output / (label + '-frame-probe')
    link(command, fixture_obj, exe)
    executables[label] = exe
snapshot = root / 'headless-sc-pc-decoder-snapshot-retry-decoder-entry.bin'
packet = fixture / 'hm1ply-frame15.packet'
assert sha(snapshot) == proof['snapshotSha256'] and sha(packet) == proof['packetSha256']
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
rows = []
reference_state = None
for iteration in range(6):
    for label in (('baseline', 'candidate') if iteration % 2 == 0 else ('candidate', 'baseline')):
        raw = output / f'{label}-{iteration}.yuv'
        result = subprocess.run([str(executables[label]), str(snapshot), str(raw), str(packet)],
            env=env, capture_output=True, text=True, timeout=30)
        log = output / f'{label}-{iteration}.log'
        log.write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-2000:]
        assert sha(raw) == proof['rows'][0]['outputSha256']
        state = Path(str(raw) + '.state')
        if reference_state is None:
            reference_state = state.read_bytes()
        assert state.read_bytes() == reference_state
        ns = int(re.search(r'COMPLETE_FRAME_REPLAY_RETURN0 ns=(\d+)', result.stdout)[1])
        rows.append({'variant': label, 'iteration': iteration, 'nanoseconds': ns,
            'outputSha256': sha(raw), 'stateSha256': sha(state), 'logSha256': sha(log)})
medians = {label: statistics.median(row['nanoseconds'] for row in rows if row['variant'] == label) for label in executables}
result_name = 'HID2_INLINE_GUARD_FRAME_STATE_IDENTICAL12' if args.candidate == 'window-hid2-inline' else 'DECODER_O3_GUARD_FRAME_STATE_IDENTICAL12'
(output / 'verification.json').write_text(json.dumps({'result': result_name,
    'buildSha256': sha(build_path), 'guardCases': len(opcodes)*40, 'guardLogSha256': sha(output / 'guard-probe.log'),
    'guardSourceSha256': sha(guard_source), 'casesSha256': sha(output / 'constant_fp_cases.h'),
    'fixtureSourceSha256': sha(fixture_source), 'fixtureObjectSha256': sha(fixture_obj),
    'fixtureProofSha256': sha(proof_path), 'snapshotSha256': sha(snapshot), 'packetSha256': sha(packet),
    'executables': {label: sha(path) for label, path in executables.items()}, 'rows': rows,
    'medianNs': medians, 'ratio': medians['baseline']/medians['candidate'], 'verifierSha256': sha(Path(__file__)),
    'limits': ['Full guard differential retains runtime success/trap/refusal messages/order/CPU state.',
        '12alternating replays of same HM1PLYframe15 exact fullYUV; original hardware/fullmemory oracle not claimed.',
        'Fixture FP-active/EE-disabled/single-thread, timing not liveFPS; no default promotion.']}, indent=2) + '\n')
print(result_name, len(opcodes)*40, medians, 'ratio', medians['baseline']/medians['candidate'])
