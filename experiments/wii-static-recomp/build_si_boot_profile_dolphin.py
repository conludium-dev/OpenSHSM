"""Exercise the existing CPU-delivered SI oracle with observed boot mask/context addresses."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_si_vector_dolphin.py')
body = parent.read_text().replace('dolphin-si-vector', 'dolphin-si-boot-profile')
body = body.replace('run_si_vector_dolphin.ps1', 'run_si_boot_profile_dolphin.ps1')
marker = "namespace = {'__file__': __file__}\nexec(compile(body, str(namespace.get('builder', parent)), 'exec'), namespace)"
assert body.count(marker) == 1
body = body.replace(marker, '''body = body.replace('0x80501000', '0x80492658').replace('0x00501000', '0x00492658')
body = body.replace('0xfffff7ff', '0xf7fff7f0').replace('(0xcc003004, 8)', '(0xcc003004, 0xf8)')
''' + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-si-boot-profile/generation.json')
report = json.loads(path.read_text())
report['profileParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['scope'] = 'CPU-delivered SI packets with observed boot PI maskF8/software maskF7FFF7F0/context80492658.'
report['limits'] = ['Prepared interrupt context contents/vector/tables and callback-present packets; not retail boot/null-callback oracle.',
    'Original vector/handler/context-return code retained, three existing replaying instruction observers.',
    'Dolphin four None ports, not physical Wii or attached controllers.']
path.write_text(json.dumps(report, indent=2) + '\n')
