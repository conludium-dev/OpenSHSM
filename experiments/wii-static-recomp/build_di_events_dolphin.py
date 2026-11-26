"""Replay observations at original IPC writes and DVDLowInit returns, preserving CPU state."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_sysconf_events_dolphin.py')
body = parent.read_text().replace('verify_sysconf_chain.py', 'verify_di_initialized_dolphin.py').replace(
    "base = root / 'dolphin-sysconf-long'", "base = root / 'dolphin-di-initialized'").replace(
    'dolphin-sysconf-events-fixed', 'dolphin-di-events').replace(
    'run_sysconf_events_fixed_disc_dolphin.ps1', 'run_di_events_disc_dolphin.ps1').replace(
    '0x806c0000, 0x806e0000', '0x806d0000, 0x806e0000')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'sites' for target in node.targets))
body = body.replace(ast.get_source_segment(body, node.value), repr([
    (1, 0x80241c30, 0x5460103a, 'IPCWriteReg_entry'),
    (2, 0x80225cbc, 0x80010014, 'DVDLowInit_return')]))
marker = '    for slot, source, size in '
extra = '''    for slot, source in [(1168, 0x8052afc4), (1172, 0x8052afc8), (1176, 0x8052afe4),
        (1180, 0x80528a38), (1184, 0x8052ab10), (1188, 0x80528a98),
        (1192, 0x8052ac90), (1196, 0x8052ac94), (1200, 0x8052ac84),
        (1204, 0x8052ac80), (1208, 0x8052afc0), (1212, 0x80528b74)]:
        pointer(code, 12, source)
        code.extend([dform(32, 0, 12, 0), dform(36, 0, 11, slot)])
'''
assert body.count(marker) == 1
body = body.replace(marker, extra + marker)
body = body.replace('(1104, 0x935e0000, 64)]:',
    '(1104, 0x935e0000, 64), (1216, 0x935e25c0, 32), (1248, 0x935e2540, 32)]:')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-events/generation.json')
report = json.loads(path.read_text())
report['eventsParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'][-2] = 'Two private replay observers save/restore r0/r11/r12/CR/MSR, preserve LR/CTR/XER/FPR and replay displaced words.'
path.write_text(json.dumps(report, indent=2) + '\n')
