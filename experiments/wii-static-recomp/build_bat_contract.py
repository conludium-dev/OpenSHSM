"""Reuse a fingerprinted test binary; Darwin link UUIDs need not repeat across rebuilds."""
from pathlib import Path
import hashlib
import json
import shlex
import shutil
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/mass-bat')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
sources = [experiment / 'bat_contract.cpp', experiment / 'processor_adapter.cpp']
flags = ['-std=c++20', '-O0', '-include', 'bit', '-I', str(experiment), '-I', str(output), '-I', str(upstream / 'nWiiRuntime/include')]
dependencies = set()
for source in sources:
    result = subprocess.run(['clang++', *flags, '-MM', '-MT', 'bat-contract', str(source)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    tokens = shlex.split(result.stdout.replace('\\\n', ' '))
    assert tokens[0] == 'bat-contract:'
    dependencies.update(tokens[1:])
identity = {'dependencies': {name: sha(Path(name)) for name in sorted(dependencies)}, 'flags': flags,
            'compilerSha256': sha(Path(shutil.which('clang++'))), 'scriptSha256': sha(Path(__file__))}
exe, report_path = output / 'bat-contract', output / 'contract-build.json'
if report_path.exists() and exe.exists():
    prior = json.loads(report_path.read_text())
    if prior['identity'] == identity and prior['executableSha256'] == sha(exe):
        print('Reused fingerprinted BAT contract binary; all compiler-discovered dependencies unchanged')
        raise SystemExit(0)
result = subprocess.run(['clang++', *flags, *map(str, sources), '-o', str(exe)], capture_output=True, text=True, timeout=30)
log = output / 'contract-build.log'
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
report_path.write_text(json.dumps({'result': 'COMPILED_CONTRACT_EXECUTION_PENDING', 'identity': identity,
                                  'executableSha256': sha(exe), 'buildLogSha256': sha(log),
                                  'limits': ['Pinned artifact identity, not byte-identical rebuilds across Darwin linker invocations or machines.']}, indent=2) + '\n')
print('Built fingerprinted BAT contract binary')
