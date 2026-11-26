"""Run whole original DVDLowInit twice after actual whole SC, not a fabricated OPEN result."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_sysconf_chain_dolphin.py')
body = parent.read_text().replace('dolphin-sysconf-chain', 'dolphin-di-open').replace(
    'run_sysconf_chain_disc_dolphin.ps1', 'run_di_open_disc_dolphin.ps1')
old = 'code.append(branch(callsite, 0x802474f0, True))'
assert body.count(old) == 1
body = body.replace(old, 'code.append(branch(callsite, 0x80225a70 if index in (6, 7) else 0x802474f0, True))')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
body = body.replace(marker, "body = body.replace('pointer(code, 9, 100000)', 'pointer(code, 9, 1000000)')\n" + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-open/generation.json')
report = json.loads(path.read_text())
report['diParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
for row in report['records']:
    if row['index'] in (6, 7):
        row['kind'] = 'DVDLowInit'
report['limits'] = ['Original pending STM/whole SC then whole DVDLowInit twice; source allocates path/heap/descriptor itself.',
    'Finite laboratory bootstrap/private emulator console files; no forced DI result/descriptor/callback/disc data or physical retail claim.']
path.write_text(json.dumps(report, indent=2) + '\n')
