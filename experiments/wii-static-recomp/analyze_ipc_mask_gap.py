"""Pin the next original store and the absent handler in the selected vendor IPC file."""
from pathlib import Path
import hashlib
import json
import re
import struct

private = Path('work/private-game/static-recomp')
source = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime/src/hw/hw_ipc.cpp')
body = source.read_text()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
cases = sorted({int(value, 16) for value in re.findall(r'case\s+(0x[0-9a-fA-F]+)\s*:', body)})
assert cases == [0, 4, 8, 12] and 0x34 not in cases
assert '0xCD000000, 0xCD00FFFF' in body and '0x0D000000, 0x0D00FFFF' in body
boot_path = private / 'mass-pi-mask/boot.json'
boot = json.loads(boot_path.read_text())
assert 'memory instruction=802175d4 address=cd000034 value=40000000 length=4 physical=d000034' in boot['stdout']
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
address = 0x802175d4
section = next(i for i in range(7) if header[18 + i] <= address < header[18 + i] + header[36 + i])
assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == 0x90030034
report = {'result': 'SELECTED_VENDOR_IPC_FILE_HAS_NO_PPC_IRQMASK_HANDLER_NEXT_ORIGINAL_WRITE_REFUSED',
          'instruction': hex(address), 'opcode': '0x90030034', 'virtualTarget': '0xcd000034', 'value': '0x40000000',
          'vendorCaseOffsets': [hex(value) for value in cases], 'vendorSourceSha256': sha(source),
          'bootSha256': sha(boot_path), 'dolSha256': sha(dol_path), 'scriptSha256': sha(Path(__file__)),
          'primaryReference': 'https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/HW/WII_IPC.cpp',
          'classification': 'Wii opcode/native attempted store; vendor source gap; Dolphin reference semantics, not physical Wii proof.',
          'limits': ['Absence applies to the pinned hw_ipc.cpp switch handlers, not all possible upstream implementations.',
                     'Register offset34 reset/IOS-update/event side effects need independent original measurements and implementation.',
                     'No vendor IPC fallback enabled; live store remains refused.']}
(private / 'mass-pi-mask/ipc-mask-gap.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS nextoriginalIPCmask store pinned; selectedvendorIPCswitch lacks offset34; no fallback enabled')
