"""Try only measured EE-enabled UART EXISync reads on the existing async boot."""
from pathlib import Path
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3', str(experiment / 'verify_uart_ee_dolphin.py')], check=True)
parent = experiment / 'observe_exi_sync_boot.py'
body = parent.read_text().replace('mass-exi-sync-observer', 'mass-exi-sync-ee-boot')
marker = 'header.write_text(text.replace(marker, observe + marker))'
assert body.count(marker) == 1
admission = r'''    if (!std::getenv("SHSM_EXI_SYNC_EE_DISABLED") && experimentExiRiUart &&
        hw::experimentExiTransfer.uartAllowed && context.msr == 0xa032 &&
        instruction == 0x8020dce0 && address == 0xcd00680c &&
        context.pc == 0x8020def4 &&
        context.gpr[3] == 0xcd000000 && context.gpr[31] == 0x80491f50 &&
        (hw::experimentExiMaskState[0] & 0x3f0) == 0x140 &&
        (((context.lr == 0x80240444 || context.lr == 0x80240464) &&
            hw::experimentExiTransfer.uartCommand == 0x30000100) ||
            ((context.lr == 0x802404d0 || context.lr == 0x80240500) &&
            hw::experimentExiTransfer.uartCommand == 0xb0000100)) &&
        !context.in_callback && !context.callback_depth && context.backup_stack.empty()) {
        const auto& state = bat_context(context);
        const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
        if (mapping.physical != 0x0d00680c || mapping.wimg != 5 || mapping.slot != 1 ||
            (hw::experimentExiTransfer.control != 0x34 && hw::experimentExiTransfer.control != 0x30)) {
            throw std::runtime_error("EXISync EE read state unverified");
        }
        std::cout << "EXI_SYNC_EE_READ lr=" << std::hex << context.lr << " control="
            << hw::experimentExiTransfer.control << std::dec << '\n';
        return MMIODispatcher::get().read32(address);
    }
'''
read_marker = 'inline uint32_t experiment_getid_read32(CPUContext& context, uint32_t address, uint32_t instruction = 0) {\n'
body = body.replace(marker, marker + '\ntext = header.read_text()\nassert text.count(' + repr(read_marker) +
    ') == 1\nheader.write_text(text.replace(' + repr(read_marker) + ', ' + repr(read_marker + admission) + '))')
entry_marker = '                const auto path = nwii::runtime::experiment_ipc_be32(packet + 12);'
entry_observer = r'''
                if (nwii::runtime::experiment_ipc_be32(packet) == 1 && path >= 0x135e0000 && path < 0x135e2000) {
                    for (bool cached : {false, true}) {
                        std::cout << (cached ? "BOOT_NEXT_OPEN_PATH_CACHED" : "BOOT_NEXT_OPEN_PATH_PHYSICAL");
                        for (unsigned offset = 0; offset < 64; ++offset) {
                            const auto byte = nwii::runtime::bat_memory_read8(context, path + offset +
                                (cached ? 0x80000000 : 0xc0000000));
                            std::cout << ' ' << unsigned(byte);
                            if (!byte) { break; }
                        }
                        std::cout << '\n';
                    }
                }
'''
body = body.replace('sources = [output', "entry_path = output / 'mass_boot.cpp'\nentry = entry_path.read_text()\nassert entry.count(" + repr(entry_marker) +
    ') == 1\nentry_path.write_text(entry.replace(' + repr(entry_marker) + ', ' + repr(entry_marker + entry_observer) + "))\nsources = [output", 1)
body = body.replace('0x80240440: 0x4bfcd861}', '0x80240440: 0x4bfcd861, 0x80240460: 0x4bfcd841, 0x802404cc: 0x4bfcd7d5, 0x802404fc: 0x4bfcd7a5}')
start = body.index("assert 'EXI_SYNC_ACCESS' in result.stdout")
end = body.index('lines = ', start)
body = body[:start] + "assert 'EXI_SYNC_EE_READ' in result.stdout\nassert 'BOOT_STM_ASYNC dispatched=1 pending=1' in result.stdout\n" + body[end:]
body = body.replace("('EXI_SYNC_', 'BOOT_BOUNDARY'", "('EXI_SYNC_', 'BOOT_BOUNDARY'")
body = body.replace('Read-only guard diagnostics; object 62 recompiled from byte-identical source, other objects/admission/backend unchanged; no transfer or hardware read performed by the observer.',
    'Private read-only admission for exact original UART EXISync A032 poll sites; object62 byte-identical source/124objects retained, backend unchanged. No full startup/physical timing proof.')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-exi-sync-ee-boot')
report = json.loads((output / 'observation.json').read_text())
row = next(row for row in report['records'] if row['file'] == 'output_62.cpp')
row.update(report['observerObject'])
report['observerParentSha256'] = __import__('hashlib').sha256(parent.read_bytes()).hexdigest()
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
