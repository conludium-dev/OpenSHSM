"""Compare current compiled queue endpoints and preserve unsupported-state refusals."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp')
experiment = Path('experiments/wii-static-recomp')
output = root / 'si-queue-native'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['builderSha256'] == sha(experiment / 'build_si_queue_native.py') and build['returnCode'] == 0
assert build['baseBootSha256'] == sha(root / 'mass-finite-mem2-boot/boot.json')
assert build['records'] == json.loads((root / 'mass-finite-mem2-boot/boot.json').read_text())['records']
for row in build['records']:
    assert sha(Path(row['source'])) == row['sourceSha256'] and sha(Path(row['object'])) == row['objectSha256']
for path, digest in {**build['sourceHashes'], **build['headerHashes']}.items():
    assert sha(Path(path)) == digest
expected = (experiment / 'si_external_delivery.h').read_text()
for before, after in [('hw::pi_intmr.load() != 8', 'hw::pi_intmr.load() != 0xf8'),
        ('0x00501000', '0x00492658'), ('0x80501000', '0x80492658'), ('0xfffff7ff', '0xf7fff7f0')]:
    expected = expected.replace(before, after)
assert (output / 'si_external_delivery.h').read_text() == expected
for name in ('processor_adapter.cpp', 'ipc_reset_backend.cpp', 'ai_mask_backend.cpp', 'dsp_startup_backend.cpp'):
    assert (output / name).read_bytes() == (experiment / name).read_bytes()
oracle_path = root / 'dolphin-si-queue/comparison.json'
oracle = json.loads(oracle_path.read_text())
def validate(log):
    lines = log.splitlines()
    assert len(lines) == 16
    for index, state in enumerate(oracle['states']):
        tokens = lines[index].split()
        assert tokens[:2] == ['SI_QUEUE_CASE', str(index)]
        values = list(map(int, tokens[2:]))
        context = list(state['context'][:8])
        context[1] = 0x807f0000
        assert values == context + state['completed'] + [state['scalar'][18], (index + 1) * 4, (index + 1) * 4], index
validate((output / 'native.log').read_text())
exe = output / 'si-queue-probe'
assert build['executableSha256'] == sha(exe)
fresh = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol'], capture_output=True, text=True, timeout=30)
assert fresh.returncode == 0 and not fresh.stderr
validate(fresh.stdout)
guards = subprocess.run([str(exe), 'work/private-game/disc/DATA/sys/main.dol', 'guards'], capture_output=True, text=True, timeout=30)
assert guards.returncode == 0 and guards.stdout == 'SI_QUEUE_GUARDS 12\n' and not guards.stderr
for position in (3, 10, 14, 20):
    lines = fresh.stdout.splitlines()
    tokens = lines[0].split()
    tokens[position] = str(int(tokens[position]) ^ 1)
    lines[0] = ' '.join(tokens)
    try:
        validate('\n'.join(lines))
    except AssertionError:
        pass
    else:
        raise AssertionError('Context/type/queue/PI mutant accepted')
(output / 'comparison.json').write_text(json.dumps({'result': 'CURRENT_COMPILED_SI_QUEUE16_64_TYPES_CONTEXT_RETURN12_GUARDS_PASS',
    'buildSha256': sha(output / 'build.json'), 'verifierSha256': sha(Path(__file__)), 'oracleSha256': sha(oracle_path),
    'limits': build['limits'] + ['Native807F0000wait sentinel substitutes only caller PC; original ISR/context/rfi remain compiled.',
        'Compared saved context ABI/queue/type/PI endpoint; fixed post-due clock is not physical completion timing.']}, indent=2) + '\n')
print('PASS current compiled queued SI16groups/64types/context-return;12guards/fresh replay/4mutants')
