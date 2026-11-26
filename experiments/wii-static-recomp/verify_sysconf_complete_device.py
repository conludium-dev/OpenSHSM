"""Actual two-file stream/kernel lifecycle, bad product sources/transfers and FD reuse."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_sysconf_close_device.py')
body = parent.read_text().replace('mass-sysconf-close-boot', 'mass-sysconf-complete-boot')
marker = '    if (devices::experiment_stm_pending() != pending) { return 27; }'
assert body.count(marker) == 1
injection = '''
    if (kernel.read(context, 3, 0x4b31a0, 0x4000) != 0x4000 || kernel.close(context, 3) != IPC_OK) { return 28; }
    const char* productPath = "/title/00000001/00000002/data/setting.txt";
    const char* productFile = "_scratch/tmp/dolphin-sysconf-long-disc-user/Wii/title/00000001/00000002/data/setting.txt";
    auto* productBytes = context.mmu.get_ptr(0x3800);
    std::fill(productBytes, productBytes + 256, 0x5a);
    for (unsigned test = 0; test < 3; ++test) {
        unsetenv("SHSM_SC_LAB_PRODUCT");
        if (test == 1) { setenv("SHSM_SC_LAB_PRODUCT", "_scratch/tmp/no-such-product-file", 1); }
        if (test == 2) { setenv("SHSM_SC_LAB_PRODUCT", argv[1], 1); }
        try { kernel.open(context, productPath, 1); return 29; } catch (const std::runtime_error&) {}
        if (devices::experiment_stm_pending() != pending) { return 30; }
        for (unsigned i = 0; i < 256; ++i) { if (productBytes[i] != 0x5a) { return 31; } }
    }
    setenv("SHSM_SC_LAB_PRODUCT", productFile, 1);
    if (kernel.open(context, productPath, 1) != 3) { return 32; }
    try { kernel.close(context, 3); return 33; } catch (const std::runtime_error&) {}
    for (unsigned test = 0; test < 2; ++test) {
        try { kernel.read(context, 3, test == 0 ? 0x3801 : 0x3800, test == 0 ? 256 : 255); return 34; }
        catch (const std::runtime_error&) {}
        for (unsigned i = 0; i < 256; ++i) { if (productBytes[i] != 0x5a) { return 35; } }
    }
    std::ifstream productReference(productFile, std::ios::binary);
    std::array<char, 256> productExpected{};
    productReference.read(productExpected.data(), productExpected.size());
    if (!productReference || kernel.read(context, 3, 0x3800, 256) != 256) { return 36; }
    for (unsigned i = 0; i < 256; ++i) { if (productBytes[i] != uint8_t(productExpected[i])) { return 37; } }
    try { kernel.read(context, 3, 0x3800, 256); return 38; } catch (const std::runtime_error&) {}
    if (kernel.close(context, 3) != IPC_OK || kernel.close(context, 3) != -4 || kernel.read(context, 3, 0x3800, 256) != -4) { return 39; }
    for (unsigned i = 0; i < 256; ++i) { if (productBytes[i] != uint8_t(productExpected[i])) { return 40; } }
    if (devices::experiment_stm_pending() != pending) { return 41; }
'''
body = body.replace(marker, marker + injection)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-sysconf-complete-boot/device-guards.json')
report = json.loads(path.read_text())
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['result'] = 'TWO_ACTUAL_FILES16384_256_SHARED_STREAM_REGISTRY_FD3_REUSE_BAD_SOURCE_TRANSFER_REPEAT_CLOSE_PENDING_PASS'
report['limits'] = ['Actual private laboratory two-file read-only adapter; SDK parsing/state checked separately.',
    'Product is opaque256 bytes, not a host decoder or validated physical Wii console identity; public settings policy pending.']
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS actual both files16384+256/same stream/sharedFD3 reuse/3bad product sources/2bad transfers/repeat/premature close/STM;inherited guards')
