"""Replay the original concurrent DVD inquiry/ES request, wait and callback chain."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_sysconf_events_dolphin.py')
body = parent.read_text().replace('verify_sysconf_chain.py', 'verify_di_burst_dolphin.py').replace(
    "base = root / 'dolphin-sysconf-long'", "base = root / 'dolphin-di-burst'").replace(
    'dolphin-sysconf-events-fixed', 'dolphin-di-burst-events').replace(
    'run_sysconf_events_fixed_disc_dolphin.ps1', 'run_di_burst_events_disc_dolphin.ps1').replace(
    '0x806c0000, 0x806e0000', '0x806d1000, 0x806e0000')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'sites' for target in node.targets))
body = body.replace(ast.get_source_segment(body, node.value), repr([
    (1, 0x80241c30, 0x5460103a, 'IPCWriteReg_entry'),
    (2, 0x802258a0, 0x9421fff0, 'DI_callback_entry'),
    (3, 0x80225940, 0x38600000, 'DI_callback_after_busy_clear'),
    (4, 0x80223b10, 0x83e1000c, 'DVDInquiryAsync_return'),
    (5, 0x802497d4, 0x80010014, 'ESP_InitLib_return'),
    (6, 0x80222f80, 0x9421ffe0, 'Inquiry_upper_callback_entry'),
    (7, 0x80211060, 0x8004000c, 'Inquiry_final_callback_entry'),
    (8, 0x8021b4e0, 0x9421fff0, 'OSSleepThread_entry'),
    (9, 0x8021a8d0, 0x38632a70, 'SelectThread_idle_context_prepare')]))
extra = '''    for slot, source in [(1168, 0x800000c0), (1172, 0x800000d4), (1176, 0x800000e4),
        (1180, 0x800000d8), (1184, 0x80492920), (1188, 0x80492934),
        (1192, 0x80528ce8), (1196, 0x8052ac44), (1200, 0x8052ac50),
        (1204, 0x8052ab04), (1208, 0x935e016c), (1212, 0x935e0170)]:
        pointer(code, 12, source)
        code.extend([dform(32, 0, 12, 0), dform(36, 0, 11, slot)])
'''
marker = '    for slot, source, size in '
assert body.count(marker) == 1
body = body.replace(marker, extra + marker).replace('(320, 0x935e1020, 320)', '(320, 0x804983a0, 320)').replace(
    '(640, 0x804b3000, 400)', '(640, 0x80492260, 96), (736, 0xd35e0140, 64), (800, 0x935e0140, 64), (864, 0x804b2a80, 80), (944, 0x8052ac28, 64)').replace(
    '(1040, 0x935e1000, 64)', '(1040, 0x800030c0, 64)').replace(
    '(1104, 0x935e0000, 64)]:', '(1104, 0x80492920, 64), (1216, 0x8052ac78, 32), (1248, 0x935e2560, 32)]:')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-di-burst-events/generation.json')
report = json.loads(path.read_text())
report['eventsParentGeneratorSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'][-2] = 'Nine replay observers save/restore r0/r11/r12/CR/MSR; LR/CTR/XER/FPR preserved, original non-branch words replayed.'
report['limits'].append('Inquiry/block96, third request64x2, FIFO80, thread64, boot fields and DVD globals are original CPU snapshots, not injected state.')
path.write_text(json.dumps(report, indent=2) + '\n')
