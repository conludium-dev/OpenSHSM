"""Native component checks for bounded read-only diagnostic capture; not guest execution verification."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'movie-packet-metadata'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
evidence = output / 'verification.json'
prior = json.loads(evidence.read_text())
assert prior['result'] == 'OWN_WII_CALLER_PACKET_METADATA_BYTES_IDENTIFIED'
temporary = Path(tempfile.mkdtemp(prefix='openshsm-movie-input-', dir='/private/tmp'))
source = public / 'stock_movie_input_probe.cpp'
header = public / 'stock_movie_input.h'
exe = temporary / 'probe'
arguments = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())['arguments']
sdk = arguments[arguments.index('-isysroot') + 1]
command = ['/Library/Developer/CommandLineTools/usr/bin/c++', '-isysroot', sdk, '-std=c++20', '-O2',
    '-I', str(public), str(source), '-o', str(exe)]
compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert compiled.returncode == 0, compiled.stderr[-2500:]
prefix = temporary / 'timing'
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
env['NWII_MOVIE_TIMING'] = str(prefix)
run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
assert run.returncode == 0 and 'MOVIE_INPUT_READ_ONLY_METADATA_REFUSALS_PASS' in run.stdout, run.stderr
metadata = Path(str(prefix) + '.inputs.jsonl')
data = Path(str(prefix) + '.inputs.bin')
rows = [json.loads(line) for line in metadata.read_text().splitlines()]
assert len(rows) == 128 and data.read_bytes() == b'\xff\xd8\0\0' * 128
for i, row in enumerate(rows):
    assert row['index'] == i and row['serial'] == 42 + i and row['offset'] == 4 * i and row['bytes'] == 4
    assert row['descriptorField4'] == 117 and row['component'] == 0 and row['input'] == 0x90001010
digest = [sha(metadata), sha(data)]
again = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
assert again.returncode == 0 and [sha(metadata), sha(data)] == digest
disabled = subprocess.run([str(exe)], env={key: value for key, value in env.items() if key != 'NWII_MOVIE_TIMING'},
    capture_output=True, text=True, timeout=30)
assert disabled.returncode == 0 and [sha(metadata), sha(data)] == digest
(output / 'observer-component.json').write_text(json.dumps({
    'result': 'MOVIE_INPUT_COMPONENT_READ_ONLY_CAP_EXCLUSIVE_FILES_PASS',
    'priorMetadataEvidenceSha256': sha(evidence), 'sourceSha256': sha(source), 'headerSha256': sha(header),
    'verifierSha256': sha(Path(__file__)), 'executablePath': str(exe), 'executableSha256': sha(exe),
    'metadataSha256': sha(metadata), 'dataSha256': sha(data), 'records': len(rows),
    'rangeAndMetadataRefusals': 17, 'runs': [run.returncode, again.returncode, disabled.returncode],
    'limits': ['Native component with synthetic context/MMU-shaped banks, not original game execution.',
        'Valid metadata/half-open RAM/wrap/MMIO/guard refusal; registers and complete fake banks unchanged.',
        '128record cap/serialized offsets/existing-file refusal/disabled capture checked.',
        'Actual CPUContext integration, full-frame equivalence, live packets and16MiB aggregate cap still pending.']}, indent=2) + '\n')
print('MOVIE_INPUT_COMPONENT_READ_ONLY_CAP_EXCLUSIVE_FILES_PASS', len(rows))
