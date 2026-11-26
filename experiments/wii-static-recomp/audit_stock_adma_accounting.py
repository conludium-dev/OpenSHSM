"""Audit exact output balance and producer-owned TB snapshots, for each isolated clock-mode run."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from stock_adma_accounting_patch import counted_output, counted_dsp

parser = argparse.ArgumentParser()
parser.add_argument('--tag', choices=('adma-accounting-live', 'adma-walltb-live'), default='adma-accounting-live')
args = parser.parse_args()
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-adma-accounting'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build_path = output / 'build.json'
build = json.loads(build_path.read_text())
for path, digest in {**build['dependencies'], **build['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
parent_path = root / 'window-adma-chunks/build.json'
parent = json.loads(parent_path.read_text())
assert sha(parent_path) == build['parentBuildSha256']
source = output / 'hw_dsp.cpp'
assert sha(source) == build['sourceSha256'] and source.read_text() == counted_dsp((root / 'window-adma-chunks/hw_dsp.cpp').read_text())
assert (output / 'stock_adma_output.h').read_text() == counted_output((public / 'stock_adma_output.h').read_text())
archive = output / 'libnwiiruntime.a'
exe = output / 'OpenSHSMStockADMAAccounting'
assert sha(archive) == build['archiveSha256'] and sha(exe) == build['executableSha256']
names = [name for name in subprocess.run(['/usr/bin/ar', 't', str(archive)], check=True,
    capture_output=True, text=True).stdout.splitlines() if name.endswith('.o')]
assert set(names) == set(parent['members']) and len(names) == len(set(names))
for name in names:
    actual = hashlib.sha256(subprocess.run(['/usr/bin/ar', 'p', str(archive), name], check=True, capture_output=True).stdout).hexdigest()
    assert actual == build['members'][name]
    if name != 'hw_dsp.cpp.o':
        assert actual == parent['members'][name]
command = list(parent['linkCommand'])
command[command.index(str(root / 'window-adma-chunks/libnwiiruntime.a'))] = str(archive)
command[command.index('-o') + 1] = str(exe)
assert command == build['linkCommand']
component_path = output / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path) and component['result'] == 'ADMA_ACCOUNTING_CAP_SWITCH_PCM_BALANCE_PASS'
run_path = root / ('headless-sc-pc-headless-windowed-' + args.tag + '-result.json')
run = json.loads(run_path.read_text())
assert run['windowed'] and run['debugOverlay'] and run['dspSupply'] and not run['capture']
assert run['terminalReturncode'] == 0 and run['deadlineReached'] and run['executableSha256'] == sha(exe)
if args.tag == 'adma-walltb-live':
    assert run['wallTimebase']
log = root / ('headless-sc-pc-headless-windowed-' + args.tag + '.log')
assert sha(log) == run['logSha256']
fields = ['wallUs', 'input32', 'input48', 'accepted', 'dropped', 'flushAccepted', 'flushDropped',
    'supplied', 'requested', 'short', 'ring', 'tbFirst', 'tbLast', 'tbFrequency', 'tbWallUs']
text = log.read_text(errors='replace')
rows = [dict(zip(fields, map(int, match.groups()))) for match in re.finditer(
    r'\[ADMAAccounting\] ' + ' '.join(name + r'=(\d+)' for name in fields), text)]
assert len(rows) > 2
for index, row in enumerate(rows):
    assert row['accepted'] - row['supplied'] == row['ring']
    assert row['flushAccepted'] <= row['accepted'] and row['flushDropped'] <= row['dropped']
    if index:
        for field in ['wallUs', 'input32', 'input48', 'accepted', 'dropped', 'flushAccepted', 'flushDropped',
            'supplied', 'requested', 'short', 'tbLast', 'tbWallUs']:
            assert row[field] >= rows[index - 1][field]
    if row['input48'] == 0:
        assert row['input32'] == row['accepted'] + row['dropped']
active = [row for row in rows if row['tbWallUs'] > 1000000 and row['tbFrequency']]
assert active
last = active[-1]
ratio = (last['tbLast'] - last['tbFirst']) * 1000000 / (last['tbFrequency'] * last['tbWallUs'])
if args.tag == 'adma-walltb-live':
    assert 0.99 < ratio < 1.01
summary = {'rows': len(rows), 'last': last, 'balanceVerified': True,
    'configuredTbToWallRatio': ratio, 'lastMeanInput32FramesPerWallSecond':
        last['input32'] * 1000000 / last['wallUs'],
    'wallTimebaseFlag': run.get('wallTimebase', 'absent-in-earlier-run-schema')}
(output / (args.tag + '-audit.json')).write_text(json.dumps({
    'result': 'ADMA_ACCOUNTING_SOURCE_COMPONENT_BALANCE_CLOCK_AUDITED', 'buildSha256': sha(build_path),
    'componentSha256': sha(component_path), 'runSha256': sha(run_path), 'logSha256': sha(log),
    'auditorSha256': sha(Path(__file__).resolve()), 'rows': rows, 'summary': summary,
    'limits': ['Exact accepted/supplied/ring, count-only converter derivation/unchanged PCM/scheduling/75guests/main.',
        'TB ratio compares configured experimental runtime clock, NOT verified original hardware or whole-game simulation speed.',
        'Input average includes boot before DMA start; runs have different frame/IRQ/clock contents, no controlled FPS speedup.',
        'No capture or human listening/quality/profile/story/controller/fullgoal acceptance, no default clock promotion.']}, indent=2) + '\n')
print('ADMA_ACCOUNTING_SOURCE_COMPONENT_BALANCE_CLOCK_AUDITED')
print(json.dumps(summary, indent=2))
