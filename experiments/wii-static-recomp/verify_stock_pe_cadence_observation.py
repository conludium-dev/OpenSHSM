"""Check diagnostic-only PE marker bookkeeping, not runtime acknowledgement latency."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
public = Path(__file__).resolve().parent
include = root / 'work/private-game/static-recomp/stock-baseline/export/nWiiRuntime/include'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
cache = Path(tempfile.mkdtemp(prefix='openshsm-pe-cadence-proof-', dir='/private/tmp'))
inputs = [Path(__file__).resolve(), public / 'stock_pe_cadence_observation.h',
    public / 'stock_pe_cadence_observation_probe.cpp', public / 'stock_gx_completed_frame.h',
    public / 'stock_gx_completion.h', public / 'stock_movie_capture_gate.h', include / 'runtime/gx_command.h']
hashes = {str(path): sha(path) for path in inputs}
sdk = subprocess.check_output(['/usr/bin/xcrun', '--show-sdk-path'], text=True).strip()
exe = cache / 'probe'
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk,
    '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(include), '-I', str(public),
    str(public / 'stock_pe_cadence_observation_probe.cpp'), '-o', str(exe)]
run = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert run.returncode == 0, run.stderr
run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert run.returncode == 0, run.stdout + run.stderr
assert run.stdout.strip() == 'PE_CADENCE_DISABLED_INVALID_DELAY_STABLE_ID_CAP_READ_ONLY_PASS'
assert all(sha(path) == digest for path, digest in hashes.items())
report = {'result': run.stdout.strip(), 'dependencies': hashes, 'compileCommand': command,
    'executablePath': str(exe), 'executableSha256': sha(exe),
    'limits': ['Diagnostic bookkeeping only; no runtime integration, clocks, GL or original guest latency measured.',
        'Caller supplies host timestamps; command base is observational, not a second runtime queue or source of truth.',
        'Cap128 accepted batches and512 marker records; malformed delay refuses observation.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
