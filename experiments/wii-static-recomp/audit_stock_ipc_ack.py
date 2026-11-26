"""Verify the isolated ACK delta and actual startup continuation; do not claim full IOS equivalence."""
from pathlib import Path
import hashlib
import json
import re

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
output = root / 'ipc-ack'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
original = root / 'export/nWiiRuntime/src/hw/hw_ipc.cpp'
assert build['builderSha256'] == sha(project / 'experiments/wii-static-recomp/build_stock_ipc_ack.py')
assert build['baseSourceSha256'] == sha(original) and build['sourceSha256'] == sha(output / 'hw_ipc.cpp')
expected = original.read_text().replace('  ipc_arm_msg  = virt_addr & 0x1FFFFFFF;\n  ipc_arm_ctrl = 0x00000003;',
    '  if (result != -0x70000001) {\n    ipc_arm_msg = virt_addr & 0x1FFFFFFF;\n  }\n  ipc_arm_ctrl = 0x00000003;').replace(
    'ipc_ppc_ctrl |= 0x2C;', 'ipc_ppc_ctrl |= 0x22;')
assert (output / 'hw_ipc.cpp').read_text() == expected
for name, digest in build['retainedObjects'].items():
    assert sha(root / 'export/build' / name) == digest
assert len(build['retainedObjects']) == 77
assert build['baseArchiveSha256'] == sha(root / 'export/build/nWiiRuntime/libnwiiruntime.a')
assert build['executableSha256'] == sha(output / 'OpenSHSMStockIPCAck')
assembly = (project / 'work/private-game/static-recomp/dtk-output/asm/auto_03_802045CC_text.s').read_text()
dol = (project / 'work/private-game/disc/DATA/sys/main.dol').read_bytes()
for address, word in (('80241F24', '70600014'), ('80241F44', '70600022')):
    match = re.search(r'/\* ' + address + r' ([0-9A-F]{8})  ((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) \*/', assembly)
    assert match and bytes.fromhex(match[2]).hex().upper() == word
    offset = int(match[1], 16)
    assert dol[offset:offset + 4] == bytes.fromhex(word)
baseline = (root / 'stock-trace.log').read_text()
live = (root / 'ipc-ack-trace.log').read_text()
assert '[CALL] 0x8021cc70' in baseline and '[CALL] 0x8021cc70' not in live
assert "path='/dev/usb/oh1/57e/305'" in live
assert '[USB] HCI command opcode 0xc03' in live and '[USB] event ->' in live
result = json.loads((root / 'ipc-ack-trace-result.json').read_text())
assert result['executableSha256'] == sha(output / 'OpenSHSMStockIPCAck')
assert result['deadlineReached'] and result['terminalReturncode'] == -15 and result['logSha256'] == sha(root / 'ipc-ack-trace.log')
(output / 'audit.json').write_text(json.dumps({'result': 'ACK_FIX_BOOT_REACHES_USB_HCI_RESET',
    'auditSha256': sha(Path(__file__)), 'buildSha256': sha(output / 'build.json'),
    'runSha256': sha(root / 'ipc-ack-trace-result.json'),
    'limits': ['Original ISR mask bytes and actual premature-callback removal/continued boot verified.',
        'USB event was generated but delivery still stalls; full IPC ordering, controller or first screen unverified.']}, indent=2) + '\n')
print('PASS isolated ACK delta/77 retained objects/original ISR masks/no premature STM callback/USB HCI reached')
