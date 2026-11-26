"""Add only guest diagnostics to the corrected FP-context runtime."""
from pathlib import Path
import hashlib
import json
import subprocess
import argparse
from stock_psq_anomaly import adapt_anomalies
from stock_block_fixture import adapt_block_fixtures
from stock_idct_callbacks import adapt_callbacks

parser = argparse.ArgumentParser()
parser.add_argument('--fixtures', action='store_true')
parser.add_argument('--callbacks', action='store_true')
args = parser.parse_args()
assert not args.callbacks or args.fixtures

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, guest = root / 'window-fp-context', root / 'window-thp-dcbz'
output = root / ('window-idct-fixtures' if args.fixtures else 'window-psq-anomaly')
if args.callbacks:
    output = root / 'window-idct-callbacks'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((base / 'build.json').read_text())
guest_build = json.loads((guest / 'build.json').read_text())
assert sha(base / 'OpenSHSMStockFPContext') == build['executableSha256']
assert sha(guest / 'output_37.cpp') == guest_build['sourceSha256']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
text, sites = adapt_anomalies((guest / 'output_37.cpp').read_text(), dol_path.read_bytes())
if args.fixtures:
    text = adapt_block_fixtures(text)
callback_sites = []
if args.callbacks:
    text, callback_sites = adapt_callbacks(text, dol_path.read_bytes())
source, obj = output / 'output_37.cpp', output / 'output_37.cpp.o'
source.write_text(text)
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *guest_build['arguments'],
    '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(build['linkCommand'])
command[command.index(str(guest / 'output_37.cpp.o'))] = str(obj)
exe = output / ('OpenSHSMStockIDCTFixtures' if args.fixtures else 'OpenSHSMStockPSQAnomaly')
if args.callbacks:
    exe = output / 'OpenSHSMStockIDCTCallbacks'
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=root / 'export/build', capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({'result': 'READ_ONLY_PSQ_ANOMALY_OBSERVER',
    'baseBuildSha256': sha(base / 'build.json'), 'guestBuildSha256': sha(guest / 'build.json'),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'sites': sites,
    'callbackSites': callback_sites,
    'executableSha256': sha(exe), 'archiveSha256': sha(base / 'libnwiiruntime.a'),
    'linkCommand': command, 'arguments': guest_build['arguments'],
    'limits': ['First64nonpositive/nonfinite pairs only; not all bad writes are necessarily covered.',
        'Read-only snapshots before/after original PSQ store; logging may affect timing.',
        'No guest state/input/readiness/clock/callback modifications.']}, indent=2) + '\n')
print('Built32DOL-checked PSQ sites,64pair limit;76guest objects/current FP archive retained')
