"""Measure original whole EUART init/write through existing EXI observers."""
from pathlib import Path
import hashlib
import json

experiment = Path('experiments/wii-static-recomp')
builder = experiment / 'build_exi_getid_dolphin.py'
body = builder.read_text().replace('dolphin-exi-getid', 'dolphin-uart').replace('run_exi_getid_dolphin.ps1', 'run_uart_dolphin.ps1')
before = '    pointer(code, 5, 0x80500000)'
assert body.count(before) == 1
body = body.replace(before, '''    if index & 4:
        pointer(code, 11, 0xcd000000)
        code.extend([dform(14, 0, 0, 0x2800), dform(36, 0, 11, 0x6800)])
    payload = [b'O', b'OS', b'OS\\n', b'OSH\\n'][index & 3]
    pointer(code, 11, 0x8052aa70)
    code.extend([dform(14, 0, 0, 0), dform(36, 0, 11, 0)])
    pointer(code, 11, 0x8052afa4)
    pointer(code, 0, 0xa5ff005a)
    code.append(dform(36, 0, 11, 0))
    if index % 8 == 0:
        pointer(code, 11, 0x8052af98)
        code.extend([dform(14, 0, 0, 0), dform(36, 0, 11, 0)])
    pointer(code, 11, 0x8052ead8)
    code.extend([dform(14, 0, 0, 4), dform(36, 0, 11, 0)])
    pointer(code, 5, 0x80500000)''')
body = body.replace('pointer(code, 0, 0xa5a5a5a5)', "pointer(code, 0, int.from_bytes(payload.ljust(4, b'\\0'), 'big'))")
body = body.replace('    pointer(code, 3, 0)\n    pointer(code, 4, 2)', '    pointer(code, 3, 0x80500000)\n    pointer(code, 4, len(payload))')
body = body.replace('0x8020ecd0, True', '0x80240320, True')
body = body.replace("'device': 2, 'destinationInitial': 0xa5a5a5a5", "'device': 1, 'clock': 4, 'payloadHex': payload.hex(), 'clearExtInt': bool(index & 4), 'resetUartInit': index % 8 == 0")
body = body.replace('    pointer(code, 11, 0x8052aa08)\n    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 76)])',
                    '    pointer(code, 11, 0x8052af98)\n    code.extend([dform(32, 0, 11, 0), dform(36, 0, 30, 76)])')
body = body.replace('    pointer(code, 11, 0xcc000000)\n    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 60),', '''    pointer(code, 11, 0x80500000)
    for offset in range(0, 16, 4):
        code.extend([dform(32, 0, 11, offset), dform(36, 0, 30, 640 + offset)])
    pointer(code, 11, 0xcc000000)
    code.extend([dform(32, 0, 11, 0x3000), dform(36, 0, 30, 60),''')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-uart/generation.json')
report = json.loads(path.read_text())
report['baseGeneratorSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['scope'] = 'Whole original80240320/EUART init802401D0/helpers/EXI;3replaying observers.16NI0/1 length1..4 calls, explicitclock4/Barnacle magic/BootInfo-null/init resets/EXTINT acknowledgement.'
report['limits'] = ['Prepared whole EUART write, not retail startup/physical Wii; observers add MMIO reads and scratch stores.',
                    'No BIOS/font/ROM reads; MaskROM device provided by existing Dolphin.']
path.write_text(json.dumps(report, indent=2) + '\n')
