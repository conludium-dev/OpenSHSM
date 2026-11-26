"""Historical exploratory SDA columns; only SC status offsets are validated."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_sysconf_register_dolphin.py')
body = parent.read_text().replace('dolphin-sysconf-register', 'dolphin-sysconf-arena').replace(
    'run_sysconf_register_disc_dolphin.ps1', 'run_sysconf_arena_disc_dolphin.ps1')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
capture = '''        if index >= 8:
            for slot, displacement in [(608, -0x3718), (612, -0x3704), (616, -0x3702),
                (620, -0x374c), (624, -0x3748), (628, -0x3758), (632, -0x3744)]:
                code.extend([dform(34 if slot < 620 else 32, 0, 13, displacement), dform(36, 0, 30, slot)])
            for slot, displacement in [(656, -0x373c), (660, -0x3738)]:
                code.extend([dform(32, 0, 13, displacement), dform(36, 0, 30, slot)])
'''
extension = "body = body.replace('            for slot, address in [(704,', " + repr(
    capture + '            for slot, address in [(704,') + ")\n"
body = body.replace(marker, extension + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-sysconf-arena/generation.json')
report = json.loads(path.read_text())
report['arenaParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'].append('Read-only SC status words plus exploratory neighboring SDA columns. Neighbor offsets do NOT identify the intended FS/IPC bounds; exclude them from arena evidence.')
path.write_text(json.dumps(report, indent=2) + '\n')
