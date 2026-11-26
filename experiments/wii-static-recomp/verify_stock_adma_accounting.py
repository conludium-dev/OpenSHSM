"""Compare original/counted converter PCM and run the actual backend fixture with balance checks enabled."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-adma-accounting'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
arguments = json.loads((root / 'window-debug-overlay/build.json').read_text())['arguments']
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
proofs = []
for label, include, counted in [('baseline', public, False), ('counted', output, True)]:
    obj = output / (label + '-converter.cpp.o')
    source = public / 'stock_adma_accounting_probe.cpp'
    compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-I', str(include),
        *(['-DCOUNTED'] if counted else []), *arguments, '-c', str(source), '-o', str(obj)],
        capture_output=True, text=True, timeout=180)
    assert compiled.returncode == 0, compiled.stderr[-3000:]
    command = list(build['linkCommand'])
    main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    if not counted:
        archive = next(arg for arg in command if Path(arg).name == 'libnwiiruntime.a')
        command[command.index(archive)] = str(root / 'window-adma-chunks/libnwiiruntime.a')
    exe = output / (label + '-converter-probe')
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
    pcm = output / (label + '-converter.pcm')
    result = subprocess.run([str(exe), str(pcm)], env=env, capture_output=True, text=True, timeout=30)
    log = output / (label + '-converter.log')
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'ADMA_ACCOUNTING_CAP_SWITCH_PCM_PASS' in result.stdout, (result.returncode, result.stdout, result.stderr)
    proofs.append({'label': label, 'executableSha256': sha(exe), 'pcmSha256': sha(pcm), 'logSha256': sha(log)})
assert proofs[0]['pcmSha256'] == proofs[1]['pcmSha256']
source = public / 'stock_adma_chunks_probe.cpp'
obj = output / 'backend-probe.cpp.o'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
assert compiled.returncode == 0, compiled.stderr[-3000:]
command = list(build['linkCommand'])
main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
command.insert(1, str(obj))
exe = output / 'backend-accounting-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
result = subprocess.run([str(exe)], env=dict(env, NWII_DSP_SUPPLY='1'), capture_output=True, text=True, timeout=30)
log = output / 'backend-probe.log'
log.write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'ADMA_CHUNKS_SDK_PCM_IRQ_RATE_PASS' in result.stdout, (result.returncode, result.stdout, result.stderr)
(output / 'component-verification.json').write_text(json.dumps({'result': 'ADMA_ACCOUNTING_CAP_SWITCH_PCM_BALANCE_PASS',
    'buildSha256': sha(build_path), 'converterProbeSha256': sha(public / 'stock_adma_accounting_probe.cpp'),
    'backendProbeSha256': sha(source), 'backendExecutableSha256': sha(exe), 'backendLogSha256': sha(log),
    'converterRows': proofs, 'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Exact original/counted mixed-rate PCM, near-full cap rejection/acceptance, switch/stop flush and flush drops.',
        'Actual SDK/DSP/AI/rate/IRQ fixture with enabled accepted-supplied=ring invariant after every operation.',
        'Native controlled fixture, not physical Wii/real-clock/FPS/human listening acceptance.']}, indent=2) + '\n')
print('ADMA_ACCOUNTING_CAP_SWITCH_PCM_BALANCE_PASS')
