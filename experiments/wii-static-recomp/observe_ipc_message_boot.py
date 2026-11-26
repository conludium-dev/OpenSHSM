"""Observe the first request register helper entry without accepting its hardware write."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import struct

parent = Path('experiments/wii-static-recomp/build_flush_ee_boot.py')
body = parent.read_text().replace("root / 'flush-ee-profile'", "root / 'flush-packet-profile'")
body = body.replace("root / 'mass-flush-ee-boot'", "root / 'mass-ipc-message-observer'")
body = body.replace('verify_flush_ee_native.py', 'verify_flush_packet_native.py')
marker = 'sources = [output /'
injection = '''entry = entry_path.read_text()
assert entry.count(marker) == 1
entry_path.write_text(entry.replace(marker, marker + '\\n    nwii::runtime::experimentFlushPacket = true;'))
wrapper_path = output / 'boot-wrapper.cpp'
wrapper = wrapper_path.read_text()
marker = '    l2_snapshot(address, context);'
assert wrapper.count(marker) == 1
observer = ''' + repr(r'''    if (address == 0x80241c30 && context.lr == 0x80242384) {
        const auto ipc = hw::experiment_ipc_snapshot();
        std::cout << "IPC_MESSAGE_ENTRY " << std::hex << context.pc << ' ' << context.lr << ' ' << context.msr
            << ' ' << context.gpr[3] << ' ' << context.gpr[4] << ' ' << ipc.ppcMessage << ' ' << ipc.armMessage
            << ' ' << ipc.ppcControl << ' ' << ipc.armControl << ' ' << ipc.ppcMask << ' ' << ipc.delay
            << ' ' << hw::pi_intsr.load() << ' ' << hw::pi_intmr.load() << std::dec << std::endl;
        const auto* packet = context.mmu.get_ptr(context.gpr[4]);
        if (!packet) { throw std::runtime_error("Observed IPC physical packet missing"); }
        std::cout << "IPC_MESSAGE_BYTES";
        for (unsigned index = 0; index < 32; ++index) { std::cout << ' ' << unsigned(packet[index]); }
        std::cout << std::endl;
        const uint32_t pathAddress = (uint32_t(packet[12]) << 24) | (uint32_t(packet[13]) << 16) |
            (uint32_t(packet[14]) << 8) | packet[15];
        if (packet[0] == 0 && packet[1] == 0 && packet[2] == 0 && packet[3] == 1 && pathAddress < 0x017fffc0) {
            const auto* path = context.mmu.get_ptr(pathAddress);
            if (!path) { throw std::runtime_error("Observed IPC path missing"); }
            std::cout << "IPC_MESSAGE_PATH " << std::hex << pathAddress << std::dec;
            for (unsigned index = 0; index < 64 && path[index]; ++index) { std::cout << ' ' << unsigned(path[index]); }
            std::cout << std::endl;
        }
    }
''') + '''
wrapper_path.write_text(wrapper.replace(marker, observer + marker))
'''
assert body.count(marker) == 1
body = body.replace(marker, injection + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-ipc-message-observer')
environment = {key: value for key, value in os.environ.items() if not key.startswith('SHSM_')}
result = subprocess.run([str(output / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol',
    str(output / 'boot-quarantine.tsv'), 'work/private-game/static-recomp/sram-native/settings.bin'],
    env=environment, capture_output=True, text=True, timeout=30)
(output / 'observed-boot.log').write_text(result.stdout + result.stderr)
assert result.returncode == 7 and not result.stderr
lines = [line for line in result.stdout.splitlines() if line.startswith(('IPC_MESSAGE_ENTRY ', 'IPC_MESSAGE_BYTES', 'IPC_MESSAGE_PATH ', 'BOOT_BOUNDARY '))]
assert len(lines) == 4
assert lines[0] == 'IPC_MESSAGE_ENTRY 80241c30 80242384 2032 0 135e0020 0 0 38 0 40000000 0 0 40f8'
assert len(lines[1].split()) == 33
path_bytes = bytes(map(int, lines[2].split()[2:]))
assert path_bytes == b'/dev/stm/immediate'
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
section = next(i for i in range(18) if layout[18 + i] <= 0x804398f0 < layout[18 + i] + layout[36 + i])
offset = layout[section] + 0x804398f0 - layout[18 + section]
assert dol[offset:offset + len(path_bytes) + 1] == path_bytes + b'\0'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'observation.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)),
    'parentSha256': sha(parent), 'buildSha256': sha(output / 'build.json'),
    'logSha256': sha(output / 'observed-boot.log'), 'states': lines,
    'dolSha256': sha(dol_path), 'originalPathAddress': '804398F0', 'observedPath': path_bytes.decode(),
    'inferredAccess': {'instruction': '80241C38', 'address': 'CD000000', 'value': '135E0020', 'width': 4},
    'limits': ['Native helper-entry snapshot and raw32packet bytes after verified flush, not original IOS transport.',
        'Store address inferred from original helper algorithm and observed arguments; current gate unchanged.']}, indent=2) + '\n')
print('\n'.join(lines))
