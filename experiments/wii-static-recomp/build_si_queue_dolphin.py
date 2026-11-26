"""Exercise original CPU-delivered SI with observed queued requests and populated context."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
parent = experiment / 'build_si_vector_dolphin.py'
evidence_path = Path('work/private-game/static-recomp/mass-interrupt-context-observer/audit.json')
evidence = json.loads(evidence_path.read_text())
assert evidence['result'] == 'STARTUP_CALLBACK_PRESENT_THREE_QUEUED_SI_PACKETS_POPULATED_CONTEXT_CONFIRMED'
context_words = evidence['contextWords']
assert len(context_words) == 0x1c8 // 4

def queued_body(body):
    body = body.replace('0x80501000', '0x80492658').replace('0x00501000', '0x00492658')
    body = body.replace('0xfffff7ff', '0xf7fff7f0').replace('(0xcc003004, 8)', '(0xcc003004, 0xf8)')
    old = '''    pointer(code, 11, 0x80492658)
    pointer(code, 0, 0)
    for offset in range(0, 0x1c8, 4):
        code.append(dform(36, 0, 11, offset))'''
    assert body.count(old) == 1
    new = '''    pointer(code, 11, 0x80492658)
    for offset, value in enumerate(context_words):
        pointer(code, 0, value)
        code.append(dform(36, 0, 11, offset * 4))
    pointer(code, 11, 0x800000d8)
    pointer(code, 0, 0x80492658)
    code.append(dform(36, 0, 11, 0))
    for port in range(4):
        pointer(code, 11, 0x8042b708 + port * 4)
        pointer(code, 0, 0x80)
        code.append(dform(36, 0, 11, 0))
        if port == channel:
            continue
        pointer(code, 11, 0x80492010 + port * 32)
        for slot, value in enumerate([port, 0x8052aa28, 1, 0x8042b708 + port * 4, 3, 0x80210110, 0, 0xf6c]):
            pointer(code, 0, value)
            code.append(dform(36, 0, 11, slot * 4))'''
    body = body.replace(old, new)
    old = '''    code.extend([dform(32, 0, 30, 108), 0x2c000000])
    code.append(0x41820000 | ((wait_callback - (base + len(code) * 4)) & 0xfffc))'''
    assert body.count(old) == 1
    new = '''    pointer(code, 11, 0x8042b708)
    for port in range(4):
        code.extend([dform(32, 0, 11, port * 4), 0x2c000080])
        code.append(0x41820000 | ((wait_callback - (base + len(code) * 4)) & 0xfffc))'''
    body = body.replace(old, new).replace("'waitEnd': wait_callback + 12", "'waitEnd': wait_callback + 56")
    marker = '    pointer(code, 0, 0xc001cafe)'
    assert body.count(marker) == 1
    snapshot = '''    for port in range(4):
        for address, slot in [(0x8042b708 + port * 4, 448 + port * 4), (0x80492010 + port * 32, 464 + port * 4)]:
            pointer(code, 11, address)
            code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
    for address, slot in [(0x8042b6f0, 480), (0x8042b700, 484), (0x800000d8, 488)]:
        pointer(code, 11, address)
        code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, slot)])
'''
    return body.replace(marker, snapshot + marker)

source = parent.read_text().replace('dolphin-si-vector', 'dolphin-si-queue')
source = source.replace('run_si_vector_dolphin.ps1', 'run_si_queue_dolphin.ps1')
marker = "namespace = {'__file__': __file__}\nexec(compile(body, str(namespace.get('builder', parent)), 'exec'), namespace)"
assert source.count(marker) == 1
source = source.replace(marker, "body = queued_body(body)\nnamespace = {'__file__': __file__, 'context_words': context_words}\nexec(compile(body, str(parent), 'exec'), namespace)")
exec(compile(source, str(parent), 'exec'), {'__file__': __file__, 'queued_body': queued_body, 'context_words': context_words})
path = Path('work/private-game/static-recomp/dolphin-si-queue/generation.json')
report = json.loads(path.read_text())
report['queueParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['contextEvidenceSha256'] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
report['scope'] = 'Original CPU external vector/handler callback with active packet +3 observed queued request layouts, populatedcontext.'
report['limits'] = ['Prepared queue/context from native startup evidence, not an unmodified retail-loader execution.',
    'All four disconnected None ports, no controller/Wiimote/physical Wii timing proof.',
    'Three prior replaying instruction observers; original handler/vector/callback bodies retained.']
path.write_text(json.dumps(report, indent=2) + '\n')
