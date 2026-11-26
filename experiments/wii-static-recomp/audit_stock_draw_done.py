"""Verify the single parser correction without treating boot failure as acceptance."""
import hashlib
import json
import subprocess
from pathlib import Path
from stock_draw_done_patch import adapt_draw_done

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-draw-done'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
base = root / 'export/nWiiRuntime/src/hle/gx/fifo_parser.cpp'
assert adapt_draw_done(base.read_text()) == (output / 'fifo_parser.cpp').read_text()
assert sha(base) == build['baseSourceSha256']
assert sha(output / 'fifo_parser.cpp') == build['sourceSha256']
assert sha(output / 'fifo_parser.cpp.o') == build['objectSha256']
assert len(build['retainedObjects']) == 77
for name, expected in build['retainedObjects'].items():
    path = Path(name)
    assert sha(path if path.is_absolute() else root / 'export/build' / path) == expected
for member, expected in build['retainedRuntimeMembers'].items():
    for archive in (root / 'window-transport-irq-order/libnwiiruntime.a', output / 'libnwiiruntime.a'):
        data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        assert hashlib.sha256(data).hexdigest() == expected
contract = subprocess.run([str(output / 'draw-done-contract')], capture_output=True, text=True, timeout=20)
assert contract.returncode == 0 and 'PASS 12' in contract.stdout
label = 'window-draw-done-headless-gx-windowed-drawdone60'
run = json.loads((root / (label + '-result.json')).read_text())
assert sha(output / 'OpenSHSMStockDrawDone') == build['executableSha256'] == run['executableSha256']
assert sha(root / (label + '.log')) == run['logSha256']
assert sha(Path('work/private-game/disc/DATA/sys/main.dol')) == run['originalDolSha256']
report = {
    'result': 'DRAW_DONE_SOURCE_COMPONENT_PROVENANCE_PASS', 'contract': contract.stdout.strip(),
    'terminalReturncode': run['terminalReturncode'], 'deadlineReached': run['deadlineReached'],
    'gpuHangReported': 'GPU Hang' in (root / (label + '.log')).read_text(errors='replace'),
    'retainedObjects': 77, 'buildSha256': sha(output / 'build.json'),
    'runSha256': sha(root / (label + '-result.json')),
    'limits': ['No original dynamic GPU oracle, full timing, rendering or menu acceptance.',
        'Only false EFB-copy finish removed and DrawDone low-byte selector corrected.']
}
(output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS actual 12-case contract and retained runtime; boot GPU Hang:', report['gpuHangReported'])
