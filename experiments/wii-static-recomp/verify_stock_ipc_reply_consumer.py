"""Execute the original command-selection fragment with actual baseline/corrected headers."""
from pathlib import Path
import hashlib
import json
import platform
import struct
import sys

assert platform.machine() == 'x86_64'
sys.path.insert(0, '_scratch/tmp/wii-static-recomp-tools/python-x64')
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import ppc_const as ppc

root = Path('work/private-game/static-recomp/stock-baseline/window-ipc-reply')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
build_path = root / 'build.json'
build = json.loads(build_path.read_text())
for path, expected in build['dependencies'].items():
    assert sha(Path(path)) == expected
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
header = struct.unpack('>64I', dol[:256])
start, length = 0x80241D04, 40
section = next(i for i in range(18) if header[18 + i] <= start
    and start + length <= header[18 + i] + header[36 + i])
offset = header[section] + start - header[18 + section]
fragment = dol[offset:offset + length]
uc = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
uc.ctl_set_cpu_model(ppc.UC_CPU_PPC32_750CL_V2_0)
uc.mem_map(0x80000000, 24 * 1024 * 1024)
uc.mem_write(start, fragment)
targets = {0x80241D2C: 'read', 0x80241D60: 'ioctl', 0x80241D98: 'ioctlv', 0x80241E5C: 'none'}
def hook(machine, address, size, data):
    if address in targets:
        machine.emu_stop()
uc.hook_add(UC_HOOK_CODE, hook)
rows = []
for variant in ['baseline', 'corrected']:
    log = root / (variant + '.log')
    assert sha(log) == build['records'][variant]['logSha256']
    lines = [line.split()[1:] for line in log.read_text().splitlines() if line.startswith('REPLY ')]
    assert len(lines) == 28
    for line in lines:
        command, fd, reply, result, original = map(int, line)
        packet = 0x80560000
        uc.mem_write(packet, struct.pack('>III', reply, result & 0xFFFFFFFF, original))
        uc.reg_write(ppc.UC_PPC_REG_31, packet)
        uc.emu_start(start, 0x80241F00, count=32)
        pc = uc.reg_read(ppc.UC_PPC_REG_PC)
        expected = {3: 'read', 6: 'ioctl', 7: 'ioctlv'}.get(original, 'none')
        assert targets.get(pc) == expected, (variant, line, hex(pc))
        if variant == 'corrected':
            assert expected == {3: 'read', 6: 'ioctl', 7: 'ioctlv'}.get(command, 'none')
        rows.append({'variant': variant, 'command': command, 'fd': fd, 'selected': expected, 'pc': pc})
assert any(row['variant'] == 'baseline' and row['command'] == 5 and row['fd'] == 7
    and row['selected'] == 'ioctlv' for row in rows)
assert any(row['variant'] == 'corrected' and row['command'] == 5 and row['fd'] == 7
    and row['selected'] == 'none' for row in rows)
(root / 'original-consumer.json').write_text(json.dumps({'result': 'ORIGINAL_REPLY_SELECTION_PASS56',
    'dolSha256': sha(dol_path), 'fragmentSha256': hashlib.sha256(fragment).hexdigest(),
    'buildSha256': sha(build_path), 'verifierSha256': sha(Path(__file__)), 'cases': rows,
    'limits': ['Actual original PPC command-selection fragment only; not full cache/IRQ/callback/scheduler execution.',
        'Software750CL execution, not original Wii hardware behavior.']}, indent=2) + '\n')
print('ORIGINAL_REPLY_SELECTION_PASS56 seek/FD7 baseline wrongly selects IOCTLV; corrected selects none')
