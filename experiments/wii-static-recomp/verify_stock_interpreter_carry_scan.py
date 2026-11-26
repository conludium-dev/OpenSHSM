"""Re-link the existing scanner probe against the corrected interpreter without rebuilding the game."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--addze', action='store_true')
args = parser.parse_args()

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-numeric-flight', root / 'interpreter-carry-corrected'
if args.addze:
    output = root / 'interpreter-addze-corrected'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
probe = json.loads((base / 'probe-build.json').read_text())
for path, digest in probe['linkInputs'].items():
    assert sha(Path(path)) == digest
build = json.loads((output / 'build.json').read_text())
archive = output / 'libnwiiruntime.a'
assert sha(archive) == build['runtime']['archiveSha256']
command = list(probe['command'])
original_archive = next(arg for arg in command if Path(arg).name == 'libnwiiruntime.a')
command[command.index(original_archive)] = str(archive)
exe = output / 'scan-probe'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', check=True, capture_output=True, timeout=60)
proof = json.loads((root / 'window-scan-routes/original-compare.json').read_text())
request = ''.join((row['input'] or '-') + ' ' + row['format'] + '\n' for row in proof['cases'])
env = {key: value for key, value in os.environ.items() if not key.startswith(('NWII_', 'SHSM_'))}
result = subprocess.run([str(exe), str(Path('work/private-game/disc/DATA/sys/main.dol').resolve())],
    input=request + b'55.15'.hex() + ' ' + b'%f'.hex() + '\n', env=env,
    capture_output=True, text=True, timeout=30)
assert result.returncode == 0
log_path = output / 'scan-regression.log'
log_path.write_text(result.stdout + result.stderr)
rows = re.findall(r'^SCAN (\d+) ([0-9a-f]{256})$', result.stdout, re.M)
reference = re.findall(r'^SCAN (\d+) ([0-9a-f]{256})$', (root / 'window-scan-routes/original-compare-native.log').read_text(), re.M)
assert len(rows) == 21 and rows[:20] == reference
assert rows[-1][0] == '1' and rows[-1][1][:8] == '425c999a'
assert '[Interp]' not in result.stdout + result.stderr
report = {'result': 'CORRECTED_CARRY_SCAN_REGRESSION_PASS', 'regressionCases': 20,
    'newCase': {'input': '55.15', 'format': '%f', 'float32Hex': '425c999a'},
    'buildSha256': sha(output / 'build.json'), 'parentProbeBuildSha256': sha(base / 'probe-build.json'),
    'scriptSha256': sha(Path(__file__)), 'executableSha256': sha(exe), 'logSha256': sha(log_path),
    'linkInputs': {arg: sha(Path(arg)) for arg in command if Path(arg).is_file() and Path(arg).suffix in ('.o', '.a')},
    'limits': ['55.15 logical float32 reference, not original PPC float oracle.',
        'Direct scanner does not reproduce live IRQ/thread state, consumer behavior or menu transition.']}
(output / 'scan-regression.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['result'])
