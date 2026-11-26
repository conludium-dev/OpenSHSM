"""Check the proposed carry boundary, not GPU execution or Wii frame identity."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
public = Path(__file__).resolve().parent
include = root / 'work/private-game/static-recomp/stock-baseline/export/nWiiRuntime/include'
cache = Path(tempfile.mkdtemp(prefix='openshsm-completed-frame-proof-', dir='/private/tmp'))
exe = cache / 'completed-frame-probe'
inputs = [Path(__file__).resolve(), public / 'stock_gx_completed_frame.h',
    public / 'stock_gx_completion.h', public / 'stock_gx_completed_frame_probe.cpp',
    include / 'runtime/gx_command.h']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
hashes = {str(path): sha(path) for path in inputs}
sdk = subprocess.check_output(['/usr/bin/xcrun', '--show-sdk-path'], text=True).strip()
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk, '-std=c++20', '-O2',
    '-Wall', '-Wextra', '-Werror', '-I', str(include), '-I', str(public),
    str(public / 'stock_gx_completed_frame_probe.cpp'), '-o', str(exe)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr
run = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=30)
assert run.stdout.strip() == 'COMPLETED_COPY_CUTOFF_EXHAUSTIVE_137257_CARRY_PE_DRAIN_PASS'
assert all(sha(Path(path)) == digest for path, digest in hashes.items())
report = {'result': run.stdout.strip(), 'dependencies': hashes, 'compileCommand': command,
    'executablePath': str(exe), 'executableSha256': sha(exe), 'cases': 137257,
    'limits': ['Pure native command-boundary check only; no live runtime or GPU verification.',
        'Seven command classes, exhaustive lengths zero through six; no original Wii timing oracle.',
        'Copy cutoff leaves post-copy PE completion in existing carry for the next drain.',
        'Presentation gating, frame statistics and latency remain unimplemented and unverified.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
