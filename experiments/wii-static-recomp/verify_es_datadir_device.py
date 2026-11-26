"""Run actual GetDataDir device guards alongside the inherited title/metadata guards."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/verify_es_title_device.py')
body = parent.read_text().replace('mass-es-title-boot', 'mass-es-datadir-boot')
body = body.replace('es_title_adapter.h', 'es_datadir_adapter.h')
injection = '''    IpcRequest directory{};
    directory.cmd = 7;
    directory.fd = 3;
    directory.req_addr = 0x135e0080;
    directory.ioctl_cmd = 0x1d;
    directory.arg_cnt_in = 1;
    directory.arg_cnt_out = 1;
    directory.ioctlv_vecs = {{0x53ff40, 8}, {0x4b2cc0, 30}};
    auto* input = context.mmu.get_ptr(0x53ff40);
    auto* output = context.mmu.get_ptr(0x4b2cc0);
    std::copy(title.begin(), title.end(), input);
    const std::string expected = "/title/00010000/52355745/data";
    for (uint8_t sentinel : {uint8_t(0xa5), uint8_t(0), uint8_t(0x7c)}) {
        std::fill(output, output + 32, sentinel);
        if (kernel.ioctlv(context, directory) != IPC_OK) { return 12; }
        for (unsigned index = 0; index < 32; ++index) {
            if (output[index] != (index < 29 ? uint8_t(expected[index]) : sentinel)) { return 13; }
        }
    }
    unsigned directoryRefused = 0;
    for (unsigned test = 0; test < 12; ++test) {
        auto bad = directory;
        std::copy(title.begin(), title.end(), input);
        std::fill(output, output + 32, 0xa5);
        if (test == 0) { bad.cmd = 6; }
        if (test == 1) { bad.fd = 99; }
        if (test == 2) { bad.req_addr += 32; }
        if (test == 3) { bad.ioctl_cmd = 0x1e; }
        if (test == 4) { bad.arg_cnt_in = 0; }
        if (test == 5) { bad.arg_cnt_out = 0; }
        if (test == 6) { bad.ioctlv_vecs.clear(); }
        if (test == 7) { bad.ioctlv_vecs[0].len = 9; }
        if (test == 8) { bad.ioctlv_vecs[0].addr += 32; }
        if (test == 9) { bad.ioctlv_vecs[1].len = 29; }
        if (test == 10) { bad.ioctlv_vecs[1].addr += 32; }
        if (test == 11) { input[0] ^= 1; }
        try {
            if (kernel.ioctlv(context, bad) != IPC_OK) { ++directoryRefused; }
        } catch (const std::runtime_error&) {
            ++directoryRefused;
        }
        if (devices::experiment_stm_pending() != pending) { return 14; }
        for (unsigned index = 0; index < 32; ++index) { if (output[index] != 0xa5) { return 15; } }
    }
    if (directoryRefused != 12) { return 16; }
    auto* packet = context.mmu.get_ptr(0x135e0080);
    auto* vectors = context.mmu.get_ptr(0x540010);
    const std::array<uint32_t, 8> header{7, 0, 3, 0x1d, 1, 1, 0x540010, 0};
    const std::array<uint32_t, 4> entries{0x53ff40, 8, 0x4b2cc0, 30};
    unsigned packetRefused = 0;
    for (unsigned test = 0; test < 14; ++test) {
        std::fill(packet, packet + 64, 0);
        for (unsigned index = 0; index < header.size(); ++index) {
            experiment_ipc_store_be32(packet + index * 4, header[index]);
        }
        for (unsigned index = 0; index < entries.size(); ++index) {
            experiment_ipc_store_be32(vectors + index * 4, entries[index]);
        }
        std::copy(title.begin(), title.end(), input);
        std::fill(output, output + 32, 0xa5);
        if (test < 8) { packet[test * 4 + 3] ^= 1; }
        if (test >= 8 && test < 12) { vectors[(test - 8) * 4 + 3] ^= 1; }
        if (test == 12) { input[0] ^= 1; }
        const std::vector<uint8_t> before(packet, packet + 64);
        bool rejected = false;
        try { experiment_es_datadir_dispatch(context, 0x135e0080); }
        catch (const std::runtime_error&) { rejected = true; }
        if (test < 13) {
            if (!rejected || !std::equal(before.begin(), before.end(), packet)) { return 17; }
            for (unsigned index = 0; index < 32; ++index) { if (output[index] != 0xa5) { return 18; } }
            ++packetRefused;
        } else {
            if (rejected || experiment_ipc_be32(packet) != 8 || experiment_ipc_be32(packet + 4) != 0 ||
                experiment_ipc_be32(packet + 8) != 7) { return 19; }
            for (unsigned index = 0; index < 32; ++index) {
                if (output[index] != (index < 29 ? uint8_t(expected[index]) : 0xa5)) { return 20; }
            }
        }
        if (devices::experiment_stm_pending() != pending) { return 21; }
    }
    if (packetRefused != 13) { return 22; }
'''
marker = '    std::cout << "ES_TITLE_DEVICE_OUTPUT8_GUARDS24_REFUSALS11_PENDING_RETAINED'
assert body.count(marker) == 1
body = body.replace(marker, injection + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-es-datadir-boot/device-guards.json')
report = json.loads(path.read_text())
report['result'] = 'ES_DATADIR_ACTUAL29_TAIL3_SENTINELS3_REFUSALS12_PACKET13_WITH_TITLE_METADATA_GUARDS_PASS'
report['parentVerifierSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['directoryRefusals'] = 12
report['directorySentinels'] = [0xa5, 0, 0x7c]
report['packetRefusals'] = 13
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS actual GetDataDir device29/tail3 in A5/zero/7C;12 device+13 packet refusals; inherited title11/metadata6')
