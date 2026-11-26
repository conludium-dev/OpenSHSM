"""Exercise actual recurring VI and existing safe delivery in isolated native processes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-vi-busy-latch'
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(Path(build['archivePath'])) == build['archiveSha256']
probe = Path('experiments/wii-static-recomp/stock_vi_timer_latch_probe.cpp').resolve()
cache = Path(tempfile.mkdtemp(prefix='openshsm-timer-latch-tests-', dir='/private/tmp'))
obj = cache / 'probe.cpp.o'
flags = json.loads((root / 'window-movie-late/build.json').read_text())['changes']['37']['arguments']
compile_command = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, '-UNDEBUG', '-c', str(probe), '-o', str(obj)]
compiled = subprocess.run(compile_command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
link = list(build['linkCommand'])
main = next(arg for arg in link if Path(arg).name == 'main.cpp.o')
link[link.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
link.insert(1, str(obj))
exe = cache / 'timer-latch-probe'
link[link.index('-o') + 1] = str(exe)
linked = subprocess.run(link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
rows = []
for mode in range(3):
    run = subprocess.run([str(exe), str(mode)], env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0 and f'ACTUAL_PERIODIC_VI_LATCH_DEFER_COALESCE_DELIVER_MODE{mode}_PASS' in run.stdout, run.stdout + run.stderr
    rows.append({'mode': mode, 'stdout': run.stdout, 'stderr': run.stderr})
(output / 'timer-latch-verification.json').write_text(json.dumps({
    'result': 'ACTUAL_PERIODIC_VI_EE0_BUSY_IDLE_NONIDLE_COALESCE_DELIVER_PASS3',
    'buildSha256': sha(build_path), 'probeSha256': sha(probe), 'verifierSha256': sha(Path(__file__)),
    'compileCommand': compile_command, 'linkCommand': link, 'executableSha256': sha(exe), 'runs': rows,
    'limits': ['Actual current recurring timer fires under instruction clock, latches EE0/busy idle/nonidle and remains pending across another due period.',
        'Existing IOS dispatch occurs after safe gates release; synthetic dispatch address, not original handler or asynchronous hardware oracle.',
        'No live performance/source-position/visual/audio/profile/controller acceptance or promotion.']}, indent=2) + '\n')
print('ACTUAL_PERIODIC_VI_EE0_BUSY_IDLE_NONIDLE_COALESCE_DELIVER_PASS3')
