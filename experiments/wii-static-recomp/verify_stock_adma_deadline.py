"""Reproduce old deadline loss and compare batched/regular actual DSP+AI+SDL event results."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--baseline-only', action='store_true')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'adma-deadline-research'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
source = public / 'stock_adma_deadline_probe.cpp'
arguments = json.loads((root / 'window-debug-overlay/build.json').read_text())['arguments']
obj = output / 'probe.cpp.o'
compiled = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
assert compiled.returncode == 0, compiled.stderr[-3000:]
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_DSP_SUPPLY'] = '1'
rows = []
for label in (['baseline'] if args.baseline_only else ['baseline', 'candidate']):
    build_path = root / ('window-adma-accounting' if label == 'baseline' else 'window-adma-deadline') / 'build.json'
    build = json.loads(build_path.read_text())
    for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
        assert sha(Path(path)) == digest
    command = list(build['linkCommand'])
    main = next(arg for arg in command if Path(arg).name == 'main.cpp.o')
    command[command.index(main)] = str(root / 'headless-tev-banks/contract-entry.cpp.o')
    command.insert(1, str(obj))
    exe = output / (label + '-probe')
    command[command.index('-o') + 1] = str(exe)
    subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
    cases = [('baseline-loss', 10, 60750000, 32000)] if label == 'baseline' else [
        (mode, chunks, frequency, rate) for frequency in (40500000, 60750000)
        for rate in (32000, 48000) for chunks in (1, 2, 10, 12, 13, 97, rate // 8)
        for mode in ('regular', 'batched')]
    if label == 'candidate':
        cases += [(mode, 10, frequency, rate) for frequency in (40500000, 60750000)
            for rate in (32000, 48000) for mode in ('stop-regular', 'stop-batched')]
    for mode, chunks, frequency, rate in cases:
        stem = f'{label}-{mode}-{chunks}-{frequency}-{rate}'
        pcm = output / (stem + '.pcm')
        result = subprocess.run([str(exe), mode, str(chunks), str(frequency), str(rate), str(pcm)],
            env=env, capture_output=True, text=True, timeout=30)
        log = output / (stem + '.log')
        log.write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and 'ADMA_DEADLINE_CASE' in result.stdout, (result.returncode, result.stdout, result.stderr)
        rows.append({'variant': label, 'mode': mode, 'chunks': chunks, 'frequency': frequency, 'rate': rate,
            'pcmSha256': sha(pcm), 'pcmBytes': pcm.stat().st_size, 'logSha256': sha(log),
            'buildSha256': sha(build_path), 'executableSha256': sha(exe)})
        if mode in ('batched', 'stop-batched'):
            regular_mode = 'regular' if mode == 'batched' else 'stop-regular'
            regular = next(row for row in rows if row['variant'] == label and row['mode'] == regular_mode and
                (row['chunks'], row['frequency'], row['rate']) == (chunks, frequency, rate))
            assert regular['pcmSha256'] == sha(pcm)
name = 'baseline-verification.json' if args.baseline_only else 'verification.json'
(output / name).write_text(json.dumps({'result': 'ADMA_DEADLINE_LOSS_REPRODUCED' if args.baseline_only
    else 'ADMA_DEADLINE_BATCH_REGULAR_PCM_EQUAL64', 'rows': rows, 'sourceSha256': sha(source),
    'verifierSha256': sha(Path(__file__).resolve()),
    'limits': ['Actual backend/MMIO/events/SDL, deterministic manual TB, no original CPU IRQ-handler interleaving/hardware clock proof.',
        'Baseline10deadlines yield2chunks16frames vs80; candidate exact regular/batched PCM/count/stop/cap/32-48k.',
        'No original Wii physical timing or complete real-world audible/graphics/story/controller acceptance.']}, indent=2) + '\n')
print('ADMA_DEADLINE_LOSS_REPRODUCED' if args.baseline_only else 'ADMA_DEADLINE_BATCH_REGULAR_PCM_EQUAL64')
