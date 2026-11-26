"""Observe ACK ARM-message retention without CPU-handler races, original register helpers."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_open_dolphin.py')
body = parent.read_text().replace("startup = '--startup-control' in sys.argv", 'startup = True')
body = body.replace("output_name = 'dolphin-stm-open-startup' if startup else 'dolphin-stm-open'", "output_name = 'dolphin-stm-pair-ack'")
body = body.replace("wrapper_name = 'run_stm_open_startup_dolphin.ps1' if startup else 'run_stm_open_dolphin.ps1'", "wrapper_name = 'run_stm_pair_ack_dolphin.ps1'")
body = body.replace('physical = 0x135e0020 + index * 64', 'physical = 0x135e0020')
body = body.replace('path_address = 0x4398f0 if index < 8 else 0x6a1000', 'path_address = 0x4398f0 if not index % 2 else 0x439904')
body = body.replace("'/dev/stm/immediate' if index < 8 else '/dev/openshsm_missing'", "'/dev/stm/immediate' if not index % 2 else '/dev/stm/eventhook'")
start = body.index('    if index >= 8:')
end = body.index('    pointer(code, 0, path_address)', start)
body = body[:start] + body[end:]
start = body.index('    pointer(code, 0, 0x40f8)')
end = body.index('    physical = ', start)
block = body[start:end]
body = body[:start] + '    if index == 0:\n' + ''.join('    ' + line + '\n' for line in block.splitlines()) + body[end:]
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/dolphin-stm-pair-ack/generation.json')
report = json.loads(path.read_text())
report['ackPairParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Original register-helper consecutive OPEN/ACK/reply with retained ARM-message, single initial hardware setup; EEoff polling, no CPU IRQ or sleep proof here.',
    'Complements independent original whole-sender/CPU pair oracle; no callback/IOCTL/retail timing proof.']
path.write_text(json.dumps(report, indent=2) + '\n')
