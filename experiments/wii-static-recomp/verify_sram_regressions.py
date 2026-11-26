"""Rebuild old GetID/UART profiles without changing their retained base artifacts."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parents = []
for filename in ('build_exi_getid_native.py', 'verify_exi_getid_native.py', 'build_uart_native.py', 'verify_uart_native.py'):
    parent = experiment / filename
    body = parent.read_text().replace('exi-getid-native', 'sram-getid-regression').replace('uart-native', 'sram-uart-regression')
    dependency = "subprocess.run(['python3', str(experiment / 'verify_exi_getid_native.py')], check=True)\n"
    if filename in ('build_uart_native.py', 'verify_uart_native.py'):
        assert body.count(dependency) == 1
        body = body.replace(dependency, '')
    if filename.startswith('verify_'):
        builder = 'build_exi_getid_native.py' if filename == 'verify_exi_getid_native.py' else 'build_uart_native.py'
        before = "sha(experiment / '" + builder + "')"
        assert body.count(before) == 1
        body = body.replace(before, 'sha(Path(__file__))')
    exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
    parents.append({'path': str(parent), 'sha256': hashlib.sha256(parent.read_bytes()).hexdigest()})
private = Path('work/private-game/static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(private / 'sram-uart-regression/regressions.json').write_text(json.dumps({'result': 'SRAM_EXTENSION_GETID16_UART16_AND_NEGATIVES_PASS',
    'runnerSha256': sha(Path(__file__)), 'parents': parents, 'backendSha256': sha(experiment / 'exi_getid_backend.h'),
    'getidProofSha256': sha(private / 'sram-getid-regression/comparison.json'), 'uartProofSha256': sha(private / 'sram-uart-regression/comparison.json'),
    'limits': ['Rebuilt default sramAllowed=false profiles; isolated output directories preserve old base proof/object hashes.',
        'No full boot/frame/physical-Wii acceptance.']}, indent=2) + '\n')
print('PASS SRAM extension preserves GetID16/32phases and UART16/96phases with old negative tests')
