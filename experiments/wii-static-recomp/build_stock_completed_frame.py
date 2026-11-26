"""Experimental completed-copy presentation; retain the verified PE candidate."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
public = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-pe-execute/build.json'
parent = json.loads(parent_path.read_text())
proof_path = root / 'window-pe-execute/component-verification.json'
proof = json.loads(proof_path.read_text())
assert proof['buildSha256'] == sha(parent_path)
assert proof['result'] == 'PE_EXECUTE_GL172_EVICTION1600_GPU6_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
assert sha(Path(parent['archivePath'])) == parent['archiveSha256']
assert sha(Path(parent['executablePath'])) == parent['executableSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-completed-frame-', dir='/private/tmp'))
archive = cache / 'libnwiiruntime.a'
shutil.copyfile(parent['archivePath'], archive)
gx_record = parent['changes']['gx.cpp']
gx_original = Path(gx_record['sourcePath'])
assert sha(gx_original) == gx_record['sourceSha256']
main_original = root / 'window-vi-timer/main.cpp'
timer = json.loads((main_original.parent / 'build.json').read_text())
assert sha(main_original) == timer['sourceSha256']
assert sha(main_original.with_suffix('.cpp.o')) == timer['objectSha256']
overlay = main_original.parent / 'stock_debug_overlay.h'
assert sha(overlay) == timer['dependencies'][str(overlay)]
shutil.copyfile(overlay, cache / overlay.name)
gx_patches = [['#include "stock_gx_completion.h"', '#include "stock_gx_completed_frame.h"'],
    ['stock_gx_execution_bounds(s_carry)', 'stock_gx_completed_frame_bounds(s_carry)'],
    ['    ++g_stat_frames;', '    if (execution.last_copy >= 0) {\n        ++g_stat_frames;\n    }']]
main_patches = [['      if (!headless) {\n        host_phases.mark(3);',
    '      host_phases.mark(3);\n      if (!headless && nwii::runtime::gx::g_state.frame_ready) {'],
    ['        SDL_GL_SwapWindow(window);',
    '        SDL_GL_SwapWindow(window);\n        nwii::runtime::gx::g_state.frame_ready = false;'],
    ['        if (trace_startup) { startup_trace("swap end"); }\n      }',
    '        if (trace_startup) { startup_trace("swap end"); }\n      } else if (!headless) {\n        host_phases.mark(4);\n        host_phases.mark(5);\n      }']]
changes = {}
for original, patches in [(gx_original, gx_patches), (main_original, main_patches)]:
    text = original.read_text()
    for before, after in patches:
        assert text.count(before) == 1, before
        text = text.replace(before, after, 1)
    restored = text
    for before, after in reversed(patches):
        assert restored.count(after) == 1
        restored = restored.replace(after, before, 1)
    assert restored == original.read_text()
    source = cache / original.name
    obj = cache / (original.name + '.o')
    source.write_text(text)
    if original == gx_original:
        command = list(gx_record['compileCommand'])
        command[command.index(str(gx_original))] = str(source)
        command[command.index('-o') + 1] = str(obj)
    else:
        flags = json.loads((root / 'window-audio-callback/build.json').read_text())['arguments']
        command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags,
            '-I', str(original.parent), '-c', str(source), '-o', str(obj)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (cache / (original.name + '.compile.log')).write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stderr[-3000:]
    changes[original.name] = {'originalPath': str(original), 'originalSha256': sha(original),
        'sourcePath': str(source), 'sourceSha256': sha(source), 'objectPath': str(obj),
        'objectSha256': sha(obj), 'patches': patches, 'compileCommand': command}
subprocess.run(['/usr/bin/ar', 'r', str(archive), changes['gx.cpp']['objectPath']], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = {}
for member, digest in parent['members'].items():
    original = subprocess.check_output(['/usr/bin/ar', '-p', parent['archivePath'], member])
    assert hashlib.sha256(original).hexdigest() == digest
    current = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    if member != 'gx.cpp.o':
        assert original == current
    else:
        assert hashlib.sha256(current).hexdigest() == changes['gx.cpp']['objectSha256']
    members[member] = hashlib.sha256(current).hexdigest()
link = list(parent['linkCommand'])
link[link.index(parent['archivePath'])] = str(archive)
link[link.index(str(main_original) + '.o')] = changes['main.cpp']['objectPath']
exe = cache / 'OpenSHSMStockCompletedFrame'
link[link.index('-o') + 1] = str(exe)
run = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
(cache / 'link.log').write_text(run.stdout + run.stderr)
assert run.returncode == 0, run.stderr[-3000:]
retained = dict(parent['retainedInputs'])
del retained[str(main_original) + '.o']
inputs = [Path(__file__).resolve(), public / 'stock_gx_completed_frame.h',
    public / 'stock_gx_completion.h', proof_path, main_original.parent / 'stock_debug_overlay.h',
    public / 'stock_host_phases.h', root / 'window-audio-callback/build.json']
report = {'result': 'COMPLETED_FRAME_BUILT_UNVERIFIED', 'parentBuildSha256': sha(parent_path),
    'changes': changes, 'archivePath': str(archive), 'archiveSha256': sha(archive),
    'members': members, 'linkCommand': link, 'executablePath': str(exe),
    'executableSha256': sha(exe), 'retainedInputs': retained,
    'dependencies': {str(path): sha(path) for path in inputs},
    'limits': ['Existing frame_ready and window front buffer only; no extra queue, renderer or image cache.',
        'CPU, VI, timebase and audio processing unchanged; completion-only batches no longer count as frames.',
        'Post-copy completion is deferred one drain; latency and original guest progress require live verification.',
        'Native boundary proof does not verify GL presentation, original Wii behavior or visual acceptance.',
        'Experimental executable is not promoted; release 0.0.41 and previous candidate remain unchanged.']}
path = cache / 'build.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
