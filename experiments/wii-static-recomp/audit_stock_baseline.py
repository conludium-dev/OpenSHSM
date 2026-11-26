"""Verify stock provenance, complete build gates and the observed scheduler wait without broad equivalence claims."""
from pathlib import Path
import hashlib
import json
import re

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
prep = json.loads((root / 'preparation.json').read_text())
assert prep['revision'] == '595f176f1d24cc54ff2e8389feed12d7fb553cc2'
for name, row in prep['files'].items():
    assert sha(root / 'upstream-source' / name) == row['sha256'], name
for name, row in prep['dependencies'].items():
    assert sha(Path(row['path'])) == row['sha256'], name
for phase in ('configure', 'toolchain', 'export', 'game-configure', 'game-build'):
    report = json.loads((root / (phase + '-result.json')).read_text())
    assert report['returncode'] == 0 and report['phase'] == phase
    assert sha(root / (phase + '.log')) == report['logSha256']
export_log = (root / 'export.log').read_text()
assert 'Discovered 17873 functions.' in export_log
generated = sorted((root / 'export').glob('output_*.cpp'))
assert len(generated) == 75
exe = root / 'export/build/OpenSHSMStockBaseline'
for name in ('stock-headless', 'stock-peek'):
    result = json.loads((root / (name + '-result.json')).read_text())
    assert result['executableSha256'] == sha(exe)
    assert result['terminalReturncode'] == -15 and result['deadlineReached']
    assert result['logSha256'] == sha(root / (name + '.log'))
    assert result['originalDolSha256'] == sha(project / 'work/private-game/disc/DATA/sys/main.dol')
    assert any('pc=0x8021a8e8' in line for line in result['samples'])
peek_log = (root / 'stock-peek.log').read_text()
rows = re.findall(r'\[Peek\] 8052ab04: ([0-9a-f]+) ([0-9a-f]+)', peek_log)
assert rows and all(hint == '1' and bitmap == '0' for hint, bitmap in rows)
(root / 'audit.json').write_text(json.dumps({'result': 'STOCK_COMPILED_EXECUTED_SCHEDULER_WAIT_OBSERVED',
    'auditSha256': sha(Path(__file__)), 'preparationSha256': sha(root / 'preparation.json'),
    'executableSha256': sha(exe), 'generatedSources': {path.name: sha(path) for path in generated},
    'headlessResultSha256': sha(root / 'stock-headless-result.json'), 'peekResultSha256': sha(root / 'stock-peek-result.json'),
    'limits': ['Complete stock build and observed wait, not original hardware equivalence, renderer verification or first screen.',
        'RunQueueHint1/RunQueueBits0 observed; missing wakeup origin not yet proved.']}, indent=2) + '\n')
print('PASS stock source/build/full export/bounded execution/scheduler wait; no first-screen claim')
