"""Read-only, bounded RAM-chain observation on the existing CPU loop trace."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import argparse
from stock_completion_observation import adapt_completion_calls, adapt_completion_pe

parser = argparse.ArgumentParser()
parser.add_argument('--callback', action='store_true')
parser.add_argument('--callback-details', action='store_true')
parser.add_argument('--logical-record', action='store_true')
parser.add_argument('--cp-transport', action='store_true')
parser.add_argument('--irq-order', action='store_true')
parser.add_argument('--completion-events', action='store_true')
args = parser.parse_args()
assert not args.callback_details or args.callback
assert not args.cp_transport or not (args.callback or args.logical_record)
assert not args.irq_order or args.cp_transport
assert not args.completion_events or args.irq_order

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
build = root / 'export/build'
output = root / ('window-completion-observe' if args.completion_events else 'window-transport-irq-order' if args.irq_order else 'window-transport-observe' if args.cp_transport else 'window-ring-observe' if args.logical_record else 'window-sound-observe' if args.callback_details else 'window-callback-observe' if args.callback else 'window-observe')
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base = root / 'ipc-cpbp/ios.cpp'
text = base.read_text()
old = '      if ((hits++ % 200000) == 0)\n        std::cout'
new = '''      if ((hits++ % 200000) == 0) {
        if (const char *peek = std::getenv("NWII_PEEK")) {
            char *tail = nullptr;
            const uint32_t address = (uint32_t)std::strtoul(peek, &tail, 16);
            const unsigned words = tail && *tail == ',' ? (unsigned)std::strtoul(tail + 1, nullptr, 10) : 4;
            const uint32_t physical = address & 0x3FFFFFFF;
            const bool ram = (physical >= 0x4000 && physical <= 0x01800000 - words * 4)
                || (physical >= 0x10000000 && physical <= 0x14000000 - words * 4);
            if (words >= 1 && words <= 64 && !(address & 3) && ram) {
                std::cout << "[LoopPeek] pc=0x" << std::hex << ctx.pc
                          << " address=0x" << address << " words=";
                for (unsigned i = 0; i < words; ++i) {
                    std::cout << " " << ctx.mmu.read32(address + i * 4);
                }
                std::cout << std::dec << "\\n";
            }
        }
        if (std::getenv("NWII_LOOPCHAIN")) {
            uint32_t node = ctx.gpr[6];
            uint32_t seen[64] = {};
            unsigned count = 0;
            const char *root_env = std::getenv("NWII_LOOPROOT");
            if (root_env) {
                const uint32_t root = (uint32_t)std::strtoul(root_env, nullptr, 16);
                const uint32_t physical = root & 0x3FFFFFFF;
                if (!(root & 3) && ((physical >= 0x4000 && physical <= 0x017FFFFC)
                    || (physical >= 0x10000000 && physical <= 0x13FFFFFC))) {
                    node = ctx.mmu.read32(root);
                    std::cout << "[LoopRoot] addr=0x" << std::hex << root
                              << " head=0x" << node << " r6=0x" << ctx.gpr[6]
                              << " r13=0x" << ctx.gpr[13] << "\\n";
                }
            }
            std::cout << "[LoopChain] pc=0x" << std::hex << ctx.pc
                      << " lr=0x" << ctx.lr << " r4=0x" << ctx.gpr[4]
                      << " r5=0x" << ctx.gpr[5] << " r6=0x" << node << "\\n";
            while (node && count < 64) {
                const uint32_t physical = node & 0x1FFFFFFF;
                const bool ram = (physical < 0x01800000 && physical <= 0x017FFFF0)
                    || (physical >= 0x10000000 && physical <= 0x13FFFFF0);
                if (!ram || (node & 3)) {
                    std::cout << "[LoopChain] invalid=0x" << node << "\\n";
                    break;
                }
                bool repeated = false;
                for (unsigned i = 0; i < count; ++i) {
                    if (seen[i] == node) {
                        repeated = true;
                    }
                }
                if (repeated) {
                    std::cout << "[LoopChain] cycle=0x" << node << "\\n";
                    break;
                }
                seen[count++] = node;
                const uint32_t next = ctx.mmu.read32(node);
                std::cout << "[LoopChain] node=0x" << node << " next=0x" << next
                          << " prev=0x" << ctx.mmu.read32(node + 4)
                          << " size=0x" << ctx.mmu.read32(node + 8)
                          << " flags=0x" << ctx.mmu.read32(node + 12) << "\\n";
                node = next;
            }
            std::cout << "[LoopChain] count=" << std::dec << count
                      << " terminal=0x" << std::hex << node << std::dec << "\\n";
        }
        std::cout'''
assert text.count(old) == 1
if args.cp_transport:
    new = new.replace('        if (const char *peek = std::getenv("NWII_PEEK")) {', '''        {
            std::ostringstream line;
            line << "[LoopStack] pc=0x" << std::hex << ctx.pc << " lr=0x" << ctx.lr << " frames=";
            uint32_t frame = ctx.gpr[1];
            for (unsigned i = 0; i < 16; ++i) {
                const uint32_t physical = frame & 0x1FFFFFFF;
                const bool ram = (physical >= 0x4000 && physical <= 0x017FFFF8)
                    || (physical >= 0x10000000 && physical <= 0x13FFFFF8);
                if (!ram || (frame & 3)) {
                    break;
                }
                const uint32_t previous = ctx.mmu.read32(frame);
                line << " " << frame << ":" << ctx.mmu.read32(frame + 4);
                if (previous <= frame) {
                    break;
                }
                frame = previous;
            }
            auto& bus = MMIODispatcher::get();
            line << " cp=";
            for (uint32_t address : {0xCC000000u, 0xCC000002u, 0xCC000030u,
                    0xCC000032u, 0xCC000034u, 0xCC000036u, 0xCC000038u,
                    0xCC00003Au, 0xCC00003Cu, 0xCC00003Eu}) {
                line << " " << bus.read32(address);
            }
            line << "\\n";
            std::cout << line.str();
        }
        if (const char *peek = std::getenv("NWII_PEEK")) {''', 1)
    text = '#include <sstream>\n' + text
assert 'ctx.mmu.write' not in new and not re.search(r'ctx\.[\w\[\]]+\s*=', new)
text = text.replace(old, new)
end = '                  << ctx.lr << std::dec << "\\n";\n    }\n  }\n\n  {\n    static bool sample'
assert text.count(end) == 1
text = text.replace(end, end.replace('\n    }', '\n      }\n    }', 1))
if args.irq_order:
    finish = '              else if (active_ints & 0x00000400) { os_intr = 19; bit_to_clear = 0x00000400; } '
    token = '              else if (active_ints & 0x00000200) { os_intr = 18; bit_to_clear = 0x00000200; } '
    assert text.count(finish + '\n' + token) == 1
    text = text.replace(finish + '\n' + token, token + '\n' + finish)
source = output / 'ios.cpp'
source.write_text(text)
flags = (build / 'nWiiRuntime/CMakeFiles/nwiiruntime.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
obj = output / 'ios.cpp.o'
result = subprocess.run([compiler, *arguments, '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=120)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
objects = [obj]
if args.completion_events:
    for original, adapter in (
        (root / 'export/nWiiRuntime/src/core/os_hle_stubs.cpp', adapt_completion_calls),
        (root / 'export/nWiiRuntime/src/hw/hw_pe.cpp', adapt_completion_pe)
    ):
        observed_source = output / original.name
        observed_source.write_text(adapter(original.read_text()))
        observed_object = output / (original.name + '.o')
        result = subprocess.run([compiler, *arguments, '-c', str(observed_source), '-o', str(observed_object)], capture_output=True, text=True, timeout=120)
        (output / (original.stem + '-compile.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr[-3000:]
        objects.append(observed_object)
if args.callback:
    interpreter_base = root / 'export/nWiiRuntime/src/hle/interpreter.cpp'
    interpreter_text = interpreter_base.read_text()
    marker = '            wild_budget--;'
    observation = '''            wild_budget--;
            std::cout << "[WildRegisters]" << std::hex;
            for (unsigned i = 0; i < 32; ++i) {
                std::cout << " r" << std::dec << i << "=0x" << std::hex << ctx.gpr[i];
            }
            std::cout << std::dec << "\\n";
            const uint32_t object = ctx.gpr[27];
            if (ctx.mmu.get_ptr(object + 0x28) && ctx.mmu.get_ptr(object + 0x2B)) {
                const uint32_t owner = ctx.mmu.read32(object + 0x28);
                const uint32_t field = owner + 0x93A8;
                if (ctx.mmu.get_ptr(field) && ctx.mmu.get_ptr(field + 3)) {
                    std::cout << "[WildCallback] object=0x" << std::hex << object
                              << " owner=0x" << owner << " field=0x" << field
                              << " value=0x" << ctx.mmu.read32(field) << " words=";
                    for (int i = -4; i <= 4; ++i) {
                        const uint32_t address = field + i * 4;
                        if (ctx.mmu.get_ptr(address) && ctx.mmu.get_ptr(address + 3)) {
                            std::cout << " " << ctx.mmu.read32(address);
                        }
                    }
                    std::cout << std::dec << "\\n";
                }
            }'''
    assert interpreter_text.count(marker) == 1
    if args.callback_details:
        observation += '''
            if (ctx.mmu.get_ptr(object + 0x74) && ctx.mmu.get_ptr(object + 0x77)) {
                const uint32_t sound = ctx.mmu.read32(object + 0x30);
                std::cout << "[WildSound] object=0x" << std::hex << object
                          << " flags=0x" << ctx.mmu.read32(object + 0x74)
                          << " sound=0x" << sound;
                if (ctx.mmu.get_ptr(sound) && ctx.mmu.get_ptr(sound + 0x73)) {
                    std::cout << " words=";
                    for (unsigned i = 0; i < 29; ++i) {
                        std::cout << " " << ctx.mmu.read32(sound + i * 4);
                    }
                }
                std::cout << std::dec << "\\n";
            }
        '''
    assert 'write' not in observation and not re.search(r'ctx\.[\w\[\]]+\s*=', observation)
    interpreter_source = output / 'interpreter.cpp'
    interpreter_source.write_text(interpreter_text.replace(marker, observation))
    interpreter_obj = output / 'interpreter.cpp.o'
    result = subprocess.run([compiler, *arguments, '-c', str(interpreter_source), '-o', str(interpreter_obj)], capture_output=True, text=True, timeout=120)
    (output / 'interpreter-compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-3000:]
    objects.append(interpreter_obj)
base_archive = root / ('window-draw-done/libnwiiruntime.a' if args.completion_events else 'window-cp-transport/libnwiiruntime.a' if args.cp_transport else 'ipc-cpbp/libnwiiruntime.a')
archive = output / 'libnwiiruntime.a'
shutil.copy2(base_archive, archive)
subprocess.run(['/usr/bin/ar', 'r', str(archive), *map(str, objects)], check=True, capture_output=True)
subprocess.run(['/usr/bin/ranlib', str(archive)], check=True, capture_output=True)
members = subprocess.check_output(['/usr/bin/ar', '-t', str(base_archive)], text=True).splitlines()
retained = {}
for member in members:
    if member in {item.name for item in objects} or member.startswith('__.SYMDEF'):
        continue
    before = subprocess.check_output(['/usr/bin/ar', '-p', str(base_archive), member])
    after = subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])
    assert before == after, member
    retained[member] = hashlib.sha256(before).hexdigest()
command = shlex.split((build / 'CMakeFiles/OpenSHSMStockBaseline.dir/link.txt').read_text())
guest_variant = root / ('window-optimized' if args.cp_transport else 'window-logical-record' if args.logical_record else 'window-byte-reverse' if args.callback else 'window-psq')
manifest = json.loads((guest_variant / 'build.json').read_text())
changed = set(range(75)) if args.cp_transport else {item['index'] for item in manifest['modules']}
for index in changed:
    name = f'CMakeFiles/OpenSHSMStockBaseline.dir/output_{index}.cpp.o'
    command[command.index(name)] = str(guest_variant / f'output_{index}.cpp.o')
for name, replacement in (
    ('CMakeFiles/OpenSHSMStockBaseline.dir/nWiiRuntime/src/core/main.cpp.o', root / 'window-paced/main.cpp.o'),
    ('CMakeFiles/OpenSHSMStockBaseline.dir/main_output.cpp.o', root / 'window-lookup/main_output.cpp.o'),
    ('nWiiRuntime/libnwiiruntime.a', archive),
):
    command[command.index(name)] = str(replacement)
exe = output / ('OpenSHSMStockCompletionObserver' if args.completion_events else 'OpenSHSMStockTransportIRQOrder' if args.irq_order else 'OpenSHSMStockTransportObserver' if args.cp_transport else 'OpenSHSMStockRingObserver' if args.logical_record else 'OpenSHSMStockSoundObserver' if args.callback_details else 'OpenSHSMStockCallbackObserver' if args.callback else 'OpenSHSMStockLoopObserver')
command[command.index('-o') + 1] = str(exe)
result = subprocess.run(command, cwd=build, capture_output=True, text=True, timeout=120)
(output / 'link.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
(output / 'build.json').write_text(json.dumps({
    'result': 'READ_ONLY_LOOP_OBSERVER_BUILT',
    'baseSourceSha256': sha(base), 'sourceSha256': sha(source),
    'archiveSha256': sha(archive), 'executableSha256': sha(exe),
    'callbackObservation': args.callback,
    'transportObservation': args.cp_transport,
    'tokenBeforeFinish': args.irq_order,
    'completionObservation': args.completion_events,
    'interpreterSourceSha256': sha(interpreter_source) if args.callback else None,
    'retainedRuntimeMembers': retained,
    'retainedObjects': {item: sha(Path(item) if Path(item).is_absolute() else build / item)
        for item in command if item.endswith('.cpp.o')},
    'limits': ['CPU-thread RAM observation only; 64 nodes maximum; no guest writes.',
        'R6/next-at-zero profile is selected explicitly; no allocator repair or behavior claim.']
}, indent=2) + '\n')
print('Built observer; all guest objects retained;', len(objects), 'diagnostic host objects changed', flush=True)
