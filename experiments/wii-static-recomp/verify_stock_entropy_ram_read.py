"""Run actual MMU boundary probe and reuse alternating full-frame equality benchmark."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

public = Path(__file__).resolve().parent
base = public / 'verify_stock_entropy_spin_cleanup.py'
code = base.read_text()
code = code.replace("'openshsm-entropy-spin-'", "'openshsm-entropy-ram-'")
code = code.replace('ENTROPY_SPIN_CONSOLE_ONLY_BUILT_UNVERIFIED', 'ENTROPY_RAM_FIRST_BUILT_UNVERIFIED')
start = code.index("original = Path(build['originalSourcePath']).read_text()")
end = code.index('project = Path(__file__)', start)
code = code[:start] + '''original = Path(build['originalSourcePath']).read_text()
before, after = build['functionPatch']
assert original.count(before) == 1
assert build['include'] + original.replace(before, after, 1) == Path(build['sourcePath']).read_text()
''' + code[end:]
code = code.replace('openshsm-entropy-spin-tests-', 'openshsm-entropy-ram-tests-')
code = code.replace('ENTROPY_SPIN_SAME_PACKETS_FULL_YUV_SELECTED_PPC_EQUAL36',
    'ENTROPY_RAM_SAME_PACKETS_FULL_YUV_SELECTED_PPC_EQUAL36')
code = code.replace('Only console diagnostic conditions removed, all output/state checks exact; not original Wii timing or live IRQ-context proof.',
    'Only RAM-first read32 helpers changed; all output/state checks exact, not original Wii timing or live IRQ-context proof.')
marker = 'rows = []'
assert code.count(marker) == 1
boundary = '''
probe = public / 'stock_entropy_ram_read_probe.cpp'
probe_obj = cache / 'memory.cpp.o'
flags_path = root / 'window-movie-late/build.json'
flags = json.loads(flags_path.read_text())['changes']['37']['arguments']
probe_compile = ['/Library/Developer/CommandLineTools/usr/bin/c++', *flags, '-UNDEBUG',
    '-fsanitize=undefined', '-c', str(probe), '-o', str(probe_obj)]
compiled = subprocess.run(probe_compile, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-3000:]
probe_link = list(link)
probe_link[probe_link.index(fixture)] = str(probe_obj)
probe_link.insert(1, '-fsanitize=undefined')
probe_exe = cache / 'memory-probe'
probe_link[probe_link.index('-o') + 1] = str(probe_exe)
linked = subprocess.run(probe_link, cwd=root / 'export/build', capture_output=True, text=True, timeout=180)
assert linked.returncode == 0, linked.stderr[-3000:]
probe_env = dict(env, UBSAN_OPTIONS='halt_on_error=1')
memory_run = subprocess.run([str(probe_exe)], env=probe_env, capture_output=True, text=True, timeout=30)
assert memory_run.returncode == 0 and 'ACTUAL_MMU_RAM_READ_ALIASES_UNALIGNED_PAD_NULL_LOCKED_MMIO_PASS' in memory_run.stdout, memory_run.stdout + memory_run.stderr
'''
code = code.replace(marker, boundary + '\n' + marker, 1)
scope = {'__file__': str(Path(__file__).resolve()), 'public': public}
exec(compile(code, str(base), 'exec'), scope)
path = scope['path']
report = json.loads(path.read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
report.update(result='ENTROPY_RAM_ACTUAL_MMU_UBSAN_FULL_YUV_SELECTED_PPC_EQUAL36',
    baseVerifierSha256=sha(base), boundaryStdout=scope['memory_run'].stdout,
    boundaryStderr=scope['memory_run'].stderr, boundaryCompileCommand=scope['probe_compile'],
    boundaryLinkCommand=scope['probe_link'], boundaryProbeSha256=sha(scope['probe']),
    helperSha256=sha(public / 'stock_entropy_ram_read.h'))
report['limits'].append('Actual MMU backend with forwarding-only spy verifies fallback route; UBSan applies to probe/helper, not all retained runtime objects.')
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(report['boundaryStdout'])
