"""Verify transport provenance and report boot failure separately from component correctness."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from stock_cp_idle_patch import adapt_cp_idle, adapt_gx_idle
from stock_cp_transport_patch import adapt_cp_transport, adapt_gx_transport, adapt_pi_transport

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / 'window-cp-transport'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
assert build['transportEnabled']
for source, name, adapter in (
    (root / 'ipc-cpbp/hw_cp.cpp', 'hw_cp.cpp', lambda text: adapt_cp_transport(adapt_cp_idle(text))),
    (root / 'export/nWiiRuntime/src/hle/gx.cpp', 'gx.cpp', lambda text: adapt_gx_transport(adapt_gx_idle(text))),
    (root / 'export/nWiiRuntime/src/hw/hw_pi.cpp', 'hw_pi.cpp', adapt_pi_transport)
):
    assert adapter(source.read_text()) == (output / name).read_text()
    assert sha(source) == build['sources'][name]['baseSha256']
    assert sha(output / name) == build['sources'][name]['sourceSha256']
    assert sha(output / (name + '.o')) == build['sources'][name]['objectSha256']
assert len(build['retainedObjects']) == 77
for name, expected in build['retainedObjects'].items():
    path = Path(name)
    assert sha(path if path.is_absolute() else root / 'export/build' / path) == expected
for member, expected in build['retainedRuntimeMembers'].items():
    for archive in (root / 'ipc-cpbp/libnwiiruntime.a', output / 'libnwiiruntime.a'):
        data = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
        assert hashlib.sha256(data).hexdigest() == expected
contract = subprocess.run([str(output / 'cp-idle-contract')], capture_output=True, text=True, timeout=20)
assert contract.returncode == 0 and 'PASS 2 MEM1/MEM2' in contract.stdout
label = 'window-cp-transport-headless-gx-windowed-' + args.tag
run = json.loads((root / (label + '-result.json')).read_text())
assert run['variant'] == 'window-cp-transport' and run['windowed'] and run['capture']
assert run['executableSha256'] == sha(output / 'OpenSHSMStockCPTransport') == build['executableSha256']
assert run['logSha256'] == sha(root / (label + '.log'))
assert run['originalDolSha256'] == sha(Path('work/private-game/disc/DATA/sys/main.dol'))
log = (root / (label + '.log')).read_text(errors='replace')
report = {
    'result': 'TRANSPORT_PROVENANCE_AND_COMPONENTS_PASS',
    'contract': contract.stdout.strip(),
    'runTag': args.tag,
    'terminalReturncode': run['terminalReturncode'],
    'deadlineReached': run['deadlineReached'],
    'gpuHangReported': 'GPU Hang' in log,
    'transportGuardReported': '[CPTRANSPORT]' in log or 'uncaught exception' in log,
    'retainedGuestEntryDispatcherObjects': 77,
    'buildSha256': sha(output / 'build.json'),
    'runSha256': sha(root / (label + '-result.json')),
    'limits': ['Component/provenance PASS does not prove successful boot, menu, audio, controllers or physical Wii equivalence.',
        'Dolphin source corroborates hardware contracts; host timing and concurrent reset remain PC adaptations.',
        'Watermark backpressure, partial-buffer reset and full parser/GX correctness remain unverified.']
}
(output / ('audit-' + args.tag + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ('result', 'terminalReturncode', 'gpuHangReported', 'transportGuardReported')}))
