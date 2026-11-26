"""Verify existing FS stream transfers actual16384 bytes and refuses repeat/bad transfers."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_sysconf_open_device.py')
body = parent.read_text().replace('mass-sysconf-open-boot', 'mass-sysconf-read-boot')
injection = '''    auto* destination = context.mmu.get_ptr(0x4b31a0);
    std::fill(destination, destination + 0x4000, 0x5a);
    if (kernel.read(context, 99, 0x4b31a0, 0x4000) != -4) { return 13; }
    for (unsigned test = 0; test < 2; ++test) {
        try {
            kernel.read(context, 3, test == 0 ? 0x4b31a1 : 0x4b31a0, test == 0 ? 0x4000 : 0x3fff);
            return 14;
        } catch (const std::runtime_error&) {}
        for (unsigned i = 0; i < 0x4000; ++i) { if (destination[i] != 0x5a) { return 15; } }
    }
    std::ifstream reference(argv[1], std::ios::binary);
    std::array<char, 0x4000> expected{};
    reference.read(expected.data(), expected.size());
    if (!reference || kernel.read(context, 3, 0x4b31a0, 0x4000) != 0x4000) { return 16; }
    for (unsigned i = 0; i < 0x4000; ++i) { if (destination[i] != uint8_t(expected[i])) { return 17; } }
    try { kernel.read(context, 3, 0x4b31a0, 0x4000); return 18; } catch (const std::runtime_error&) {}
    for (unsigned i = 0; i < 0x4000; ++i) { if (destination[i] != uint8_t(expected[i])) { return 19; } }
    if (devices::experiment_stm_pending() != pending) { return 20; }
    for (unsigned i = 0; i < 32; ++i) { if (bytes[i] != 0xa5) { return 21; } }
'''
marker = '    if (refused != 12) { return 12; }'
assert body.count(marker) == 1
body = body.replace(marker, marker + injection.replace('\n', '\\n'))
body = body.replace("host.write_text('#include <algorithm>\\n#include <cstdlib>\\n' + text)",
    "host.write_text('#include <algorithm>\\n#include <cstdlib>\\n#include <fstream>\\n#include <array>\\n' + text)")
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-sysconf-read-boot/device-guards.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['result'] = 'ACTUAL16384_FILE_BYTES_SHARED_KERNEL_12_INHERITED_PLUS_BAD_FD2_BAD_TRANSFERS_REPEAT_OUTPUT_PENDING_PASS'
report['limits'] = ['Read-only laboratory stream component; original dynamic callback/free proof is in audit_sysconf_read_boot.py.',
    'Production console settings, later read/seek/write/close/SC completion remain unverified.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS actual READ16384 equals full lab file;bad FD/2bad transfers/repeat preserve bytes+STM;12 inherited guards')
