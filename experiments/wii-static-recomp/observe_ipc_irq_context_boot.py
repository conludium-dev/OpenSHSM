"""Read registered IPC IRQ27, software masks, response queue and current thread before send."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/observe_ipc_message_boot.py')
body = parent.read_text().replace('mass-ipc-message-observer', 'mass-ipc-irq-context-observer')
body = body.replace('index < 32;', 'index < 64;').replace('len(lines[1].split()) == 33', 'len(lines[1].split()) == 65')
marker = '        const auto ipc = hw::experiment_ipc_snapshot();'
observer = '''        std::cout << "IPC_IRQ_LAYOUT" << std::hex;
        for (uint32_t address : {0x800000c0u, 0x800000c4u, 0x800000c8u, 0x800000d4u, 0x800000d8u,
            0x800000e4u, 0x80003010u, 0x8052aad8u, 0x800030acu, 0x8052ab00u, 0x8052ab04u,
            0x80528b70u, 0x80528b74u, 0x8052afd8u, 0x8052afdcu}) {
            std::cout << ' ' << address << ' ' << bat_memory_read32(context, address);
        }
        std::cout << std::dec << std::endl;
        std::cout << "IPC_IRQ_RESPONSES" << std::hex;
        for (unsigned offset = 0; offset < 80; offset += 4) {
            std::cout << ' ' << bat_memory_read32(context, 0x804b2a80 + offset);
        }
        std::cout << std::dec << std::endl;
        const uint32_t currentThread = bat_memory_read32(context, 0x800000e4);
        if (currentThread < 0x80000000 || currentThread > 0x817ffce8) {
            throw std::runtime_error("IPC current thread outside MEM1");
        }
        std::cout << "IPC_IRQ_THREAD " << std::hex << currentThread;
        for (unsigned offset = 0; offset < 0x318; offset += 4) {
            std::cout << ' ' << bat_memory_read32(context, currentThread + offset);
        }
        std::cout << std::dec << std::endl;
'''
assert body.count(marker) == 1
body = body.replace(marker, observer + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-ipc-irq-context-observer')
log = (output / 'observed-boot.log').read_text()
lines = [line for line in log.splitlines() if line.startswith('IPC_IRQ_')]
assert len(lines) == 3
layout = lines[0].split()[1:]
assert len(layout) == 30
layout = {int(layout[index], 16): int(layout[index + 1], 16) for index in range(0, len(layout), 2)}
assert layout[0x8052aad8] == 0x80003040 and layout[0x800030ac] == 0x80241f00
thread = [int(value, 16) for value in lines[2].split()[1:]]
assert len(thread) == 1 + 0x318 // 4 and thread[0] == layout[0x800000e4]
responses = [int(value, 16) for value in lines[1].split()[1:]]
assert len(responses) == 20
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
(output / 'irq-context.json').write_text(json.dumps({'builderSha256': sha(Path(__file__)),
    'parentSha256': sha(parent), 'observationSha256': sha(output / 'observation.json'),
    'logSha256': sha(output / 'observed-boot.log'), 'layout': {hex(key): hex(value) for key, value in layout.items()},
    'threadAddress': thread[0], 'threadWords': thread[1:], 'responseWords': responses,
    'limits': ['Native startup before request send; cached reads may allocate lines, no stores/IRQ clears/admission.',
        'Registered original IPCInterruptHandler27 verified; no original IRQ delivery or sleeping-thread state yet.']}, indent=2) + '\n')
print(lines[0])
print(lines[1])
print('IPC thread=' + hex(thread[0]) + ' context=' + hex(layout[0x800000d4]) + ' words=' + str(len(thread) - 1))
