"""Replay original DI86 request, SDK return and callback entry/exit observations."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_sysconf_events_dolphin.py')
body = parent.read_text().replace('verify_sysconf_chain.py', 'verify_di86_dolphin.py').replace(
    "base = root / 'dolphin-sysconf-long'", "base = root / 'dolphin-di86'").replace(
    'dolphin-sysconf-events-fixed', 'dolphin-di86-events').replace(
    'run_sysconf_events_fixed_disc_dolphin.ps1', 'run_di86_events_disc_dolphin.ps1').replace(
    '0x806c0000, 0x806e0000', '0x806d1000, 0x806e0000')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'sites' for target in node.targets))
body = body.replace(ast.get_source_segment(body, node.value), repr([
    (1, 0x80241c30, 0x5460103a, 'IPCWriteReg_entry'),
    (2, 0x802258a0, 0x9421fff0, 'DI_callback_entry'),
    (3, 0x80225940, 0x38600000, 'DI_callback_after_busy_clear'),
    (4, 0x80227f20, 0x80010014, 'DI86_API_return')]))
extra = '''    for slot, source in [(1168, 0x8052afc4), (1172, 0x8052afc8), (1176, 0x8052afe4),
        (1180, 0x80528a38), (1184, 0x8052ab10), (1188, 0x80528a98),
        (1192, 0x8052ac90), (1196, 0x8052ac94), (1200, 0x8052ac84),
        (1204, 0x8052ac80), (1208, 0x8052afc0), (1212, 0x80528b74)]:
        pointer(code, 12, source)
        code.extend([dform(32, 0, 12, 0), dform(36, 0, 11, slot)])
'''
marker = '    for slot, source, size in '
assert body.count(marker) == 1
body = body.replace(marker, extra + marker).replace('(320, 0x935e1020, 320)', '(320, 0x804983a0, 320)').replace(
    '(1104, 0x935e0000, 64)]:', '(1104, 0x935e0000, 64), (1216, 0x8052ac78, 32), (1248, 0x935e2560, 32)]:')
body = body.replace('nine replay sites', 'four replay sites')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di86-events/generation.json')
report = json.loads(path.read_text())
report['eventsParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'][-2] = 'Four private replay observers save/restore r0/r11/r12/CR/MSR, preserve LR/CTR/XER/FPR and replay displaced words.'
path.write_text(json.dumps(report, indent=2) + '\n')
