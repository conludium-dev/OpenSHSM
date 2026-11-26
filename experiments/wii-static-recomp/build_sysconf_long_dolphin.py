"""Allow the whole original asynchronous SC chain a longer finite guest wait."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_sysconf_chain_dolphin.py')
body = parent.read_text().replace('dolphin-sysconf-chain', 'dolphin-sysconf-long').replace(
    'run_sysconf_chain_disc_dolphin.ps1', 'run_sysconf_long_disc_dolphin.ps1')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
body = body.replace(marker, "body = body.replace('pointer(code, 9, 100000)', 'pointer(code, 9, 1000000)')\n" + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-sysconf-long/generation.json')
report = json.loads(path.read_text())
report['longParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['guestSpinIterationsPerRecord'] = 1000000
report['limits'].append('Longer finite guest observation interval only; IOS timing/events/results/SC flags not supplied.')
path.write_text(json.dumps(report, indent=2) + '\n')
