"""Read actual idle/queue/async-packet state without relaxing the stopped native guard."""
from pathlib import Path
import ast
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_di86_inputs_native.py')
body = parent.read_text().replace('mass-di-open-boot', 'mass-di86-boot').replace(
    'mass-di86-inputs-observer', 'mass-di86-idle-observer')
node = next(node for node in ast.parse(body).body if isinstance(node, ast.Assign) and
    any(isinstance(target, ast.Name) and target.id == 'observer' for target in node.targets))
observer = r'''        if (context.pc == 0x8021a8e8 && context.lr == 0x8021a8dc && nwii::runtime::stmSubmitted == 32) {
            std::cout << "DI86_IDLE_STATE" << std::hex << ' ' << context.msr;
            for (uint32_t address : {0x800000e4u, 0x800000d8u, 0x800000d4u, 0x800000c0u,
                0x8052ab08u, 0x8052ab04u, 0x935e00acu, 0x935e00b0u, 0x804b2a80u, 0x804b2a84u,
                0x8049292cu, 0x80492930u, 0x80492934u, 0x80492938u, 0x8049293cu}) {
                std::cout << ' ' << nwii::runtime::bat_memory_read32(context, address);
            }
            std::cout << ' ' << nwii::runtime::bat_memory_read16(context, 0x80492920) << std::dec << '\n';
            std::cout << "DI86_IDLE_DVD_GLOBALS" << std::hex;
            for (uint32_t address : {0x8052ac44u, 0x8052ac50u, 0x8052ac40u, 0x8052abc0u}) {
                std::cout << ' ' << nwii::runtime::bat_memory_read32(context, address);
            }
            std::cout << std::dec << '\n';
            const auto block = nwii::runtime::bat_memory_read32(context, 0x8052ac50);
            if (block >= 0x80400000 && block <= 0x80540000 - 64) {
                std::cout << "DI86_IDLE_DVD_BLOCK";
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, block + index));
                }
                std::cout << '\n';
            }
            const auto ipc = nwii::runtime::hw::experiment_ipc_snapshot();
            std::cout << "DI86_IDLE_IPC" << std::hex << ' ' << ipc.ppcControl << ' ' << ipc.ppcMessage
                << ' ' << ipc.armMessage << ' ' << ipc.armControl << ' ' << ipc.delay << std::dec << '\n';
            for (const auto& region : std::array<std::tuple<const char*, uint32_t, unsigned>, 8>{
                std::tuple{"DI86_IDLE_PACKET", 0x935e0080u, 64u},
                std::tuple{"DI86_IDLE_THREAD", 0x80492920u, 64u},
                std::tuple{"DI86_IDLE_CALLBACK", 0x804983a0u, 64u},
                std::tuple{"DI86_IDLE_QUEUED_PACKET", 0x935e00e0u, 64u},
                std::tuple{"DI86_IDLE_WAIT_PACKET", 0x935e0140u, 64u},
                std::tuple{"DI86_IDLE_COMMAND_RING", 0x935e2540u, 128u},
                std::tuple{"DI86_IDLE_REQUEST_QUEUE", 0x804b2a80u, 80u},
                std::tuple{"DI86_IDLE_ES_PATH", 0x80528cf0u, 32u}}) {
                std::cout << std::get<0>(region);
                for (unsigned index = 0; index < std::get<2>(region); ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, std::get<1>(region) + index));
                }
                std::cout << '\n';
            }
        }
'''
body = body.replace(ast.get_source_segment(body, node.value), repr(observer)).replace(
    "assert 'DI86_INPUTS ' in result.stdout", "assert 'DI86_IDLE_STATE ' in result.stdout").replace(
    'pc=80241c30 lr=80242384 msr=2032', 'pc=8021a8e8 lr=8021a8dc msr=8032')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-di86-idle-observer/observation.json')
report = json.loads(path.read_text())
report['idleParentObserverSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Read-only stopped native DI86 attempt, all125 PPC objects unchanged; no idle-guard relaxation or successful response claim.',
    'The inherited preliminary audit verifies the unchanged DI-OPEN parent, not completion of the DI86 attempt.']
path.write_text(json.dumps(report, indent=2) + '\n')
