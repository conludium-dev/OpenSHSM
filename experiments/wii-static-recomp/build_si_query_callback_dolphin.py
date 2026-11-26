"""Extend the retained bus fixture with original GetTypeCallback invocation."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_si_query_dolphin.py'
body = builder.read_text().replace('dolphin-si-query', 'dolphin-si-query-callback').replace('run_si_query_dolphin.ps1', 'run_si_query_callback_dolphin.ps1')
marker = '    pointer(code, 0, 0xc001cafe)'
assert body.count(marker) == 1
insertion = '''    pointer(code, 3, channel)
    code.append(dform(32, 4, 30, 48))
    code.append(branch(base + len(code) * 4, 0x80210110, True))
    pointer(code, 11, 0x8042b708 + channel * 4)
    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 92)])
'''
body = body.replace(marker, insertion + marker)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-si-query-callback/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Original setup8020FD00/hardware START wait/completion8020F550/GetTypeCallback80210110; completion and callback invoked by disclosed fixture, not automatic IRQ.'
report['limits'] = ['Prepared Si/type/buffers/r2-r13/MSR/HID; not whole SIGetType/SITransfer/alarm/interrupt-handler route.',
    'None0 configuration on all4SIports; no attached controllers, Wiimote, physical Wii or retail image. SRAM shadow/cache producers remain unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')
