"""Measured third async request on existing STM device/kernel/event heap, no fabricated reply."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_stm_async_dolphin.py')], check=True)
parent = experiment / 'build_stm_eventhook_boot.py'
body = parent.read_text().replace('mass-stm-eventhook-boot', 'mass-stm-async-boot')
extra = '''front = front.replace('stmSubmitted == 1 || stmSubmitted == 3', 'stmSubmitted == 1 || stmSubmitted == 3 || stmSubmitted == 5')
front = front.replace('stmSubmitted == 0 || stmSubmitted == 2', 'stmSubmitted == 0 || stmSubmitted == 2 || (stmSubmitted == 4 && !std::getenv("SHSM_STM_ASYNC_DISABLED"))')
front = front.replace('(stmSubmitted == 2 && state.ppcMessage == value)', '(stmSubmitted >= 2 && state.ppcMessage == value)')
marker = '            MMIODispatcher::get().write32(address, value);'
check = ''' + repr('''            if (stmSubmitted == 4) {
                const auto* packet = context.mmu.get_ptr(value);
                const std::array<uint32_t, 8> expected{6, 1, 1, 0x1000, 0x493060, 32, 0x493080, 32};
                if (value != 0x135e0020) { throw std::runtime_error("STM async physical request unverified"); }
                for (unsigned index = 0; index < expected.size(); ++index) {
                    if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                        throw std::runtime_error("STM async request header unverified");
                    }
                }
                if (bat_memory_read32(context, (value | 0x80000000) + 32) != 0x8021cc70 ||
                    bat_memory_read32(context, (value | 0x80000000) + 36) || bat_memory_read32(context, (value | 0x80000000) + 40)) {
                    throw std::runtime_error("STM async cached callback metadata unverified");
                }
            }
''') + '''
assert front.count(marker) == 1
front = front.replace(marker, check + marker)
(output / 'stm_async_dispatch.h').write_bytes((experiment / 'stm_async_dispatch.h').read_bytes())
event_path = output / 'ipc_event_order_probe.cpp'
event = event_path.read_text().replace('EventScheduler::Callback beforeReply = {})', 'EventScheduler::Callback beforeReply = {}, bool deferred = false)')
event = event.replace('[request, beforeReply]', '[request, beforeReply, deferred]')
event = event.replace('experiment_fixture_reply_after(request, 1, beforeReply)', 'experiment_fixture_reply_after(request, 1, beforeReply, deferred)')
event = event.replace('        ipc_arm_msg = request;', '        if (deferred) { return; }\\n        ipc_arm_msg = request;', 1)
event_path.write_text(event)
device = (runtime / 'src/hle/devices/stm_device.cpp').read_text()
device = '#include <optional>\\n#include <stdexcept>\\n' + device
device = device.replace('public:\\n', '    std::optional<IpcRequest> pending_;\\npublic:\\n    const IpcRequest* pending() const { return pending_ ? &*pending_ : nullptr; }\\n', 1)
start = device.index('        std::cout << "[STM] ioctl cmd=')
end = device.index('    }\\n    int32_t ioctlv', start)
handler = ''' + repr('''        if (req.cmd != 6 || req.fd != 1 || req.req_addr != 0x135e0020 || req.ioctl_cmd != 0x1000 ||
            req.in_buf != 0x493060 || req.in_size != 32 || req.out_buf != 0x493080 || req.out_size != 32 || pending_) {
            throw std::runtime_error("STM device pending request outside measured profile");
        }
        pending_ = req;
        return IPC_NO_REPLY;
''') + '''
device = device[:start] + handler + device[end:]
device = device.replace('return IPC_OK;', 'throw std::runtime_error("STM ioctlv unverified");')
device = device.replace('std::unique_ptr<IDevice> create_stm_device() {', 'static STMDevice* observer = nullptr;\\nconst IpcRequest* experiment_stm_pending() { return observer ? observer->pending() : nullptr; }\\nstd::unique_ptr<IDevice> create_stm_device() {')
device = device.replace('    return std::make_unique<STMDevice>();', '    auto device = std::make_unique<STMDevice>();\\n    observer = device.get();\\n    return device;')
(output / 'stm_device.cpp').write_text(device)
'''
marker = 'marker = "(output / \'ipc_ack_frontend.h\').write_text(front)"'
assert body.count(marker) == 1
body = body.replace(marker, 'extension += ' + repr(extra) + '\n' + marker, 1)
support_change = '''support = '#include "stm_async_dispatch.h"\\n' + support
needle = '    hw::experiment_fixture_reply_after(request, 2,'
branch = ''' + repr('''    if (stmSubmitted == 5) {
        hw::experiment_fixture_reply_after(request, 2, [request](CPUContext& active, uint64_t) {
            experiment_stm_dispatch_async(active, request);
        }, true);
        return;
    }
''') + '''
assert support.count(needle) == 1
support = support.replace(needle, branch + needle)
'''
# Include must precede the namespace opened by the existing wrapper.
support_change = support_change.replace("support = '#include \"stm_async_dispatch.h\"\\n' + support\n", '')
mutations = [
    ('support = host[start:end]', 'support = host[start:end]\n' + support_change),
    ('#include "ipc_ack_frontend.h"\n#define main unused_stm_event_main', '#include "ipc_ack_frontend.h"\n#include "stm_async_dispatch.h"\n#define main unused_stm_event_main'),
    ("root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hle/devices/stm_device.cpp'", "root / 'stm-open-native/ios_kernel.cpp', output / 'stm_device.cpp'")
]
dispatch = '''row = next(row for row in records if row['file'] == 'main_output.cpp')
text = Path(row['source']).read_text()
marker = '            case 0x80217520: func_80217520(ctx); break;'
assert text.count(marker) == 1
text = text.replace(marker, marker + '\\n            case 0x8021753C: func_80217520(ctx); break;')
target = output / 'main_output.cpp'
target.write_text(text)
obj = output / 'main_output.cpp.o'
result = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-DSHSM_SI_EXTERNAL_DELIVERY',
    *includes, '-c', str(target), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'dispatcher-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
row.update(source=str(target), sourceSha256=sha(target), object=str(obj), objectSha256=sha(obj))
'''
# The existing startup builder spells out include arguments rather than an includes variable.
dispatch = dispatch.replace('*includes,', "'-include', str(output / 'finite_mem2_clear.h'), '-I', str(output), '-I', str(experiment), '-I', str(root / 'mass-current'), '-I', str(runtime / 'include'),")
mutations.append(('sources = [wrapper_path,', dispatch + 'sources = [wrapper_path,'))
pending_print = '''    std::cout << "BOOT_STM_ASYNC dispatched=" << nwii::runtime::stmAsyncDispatched;
    const auto* pending = nwii::runtime::devices::experiment_stm_pending();
    std::cout << " pending=" << (pending != nullptr);
    if (pending) {
        for (uint32_t value : {pending->cmd, pending->fd, pending->req_addr, pending->ioctl_cmd,
            pending->in_buf, pending->in_size, pending->out_buf, pending->out_size}) {
            std::cout << ' ' << value;
        }
    }
    std::cout << '\\n';
'''
replace_wrapper = 'wrapper = wrapper.replace(' + repr('    return result;') + ', ' + repr(pending_print + '    return result;') + ', 1)\nwrapper_path.write_text(wrapper)'
mutations.append(('wrapper_path.write_text(wrapper)', replace_wrapper))
memory_print = '''            std::cout << "BOOT_STM_ASYNC_MEMORY" << std::hex;
            for (uint32_t address : {0x8052ab1cu, 0x8052ab28u, 0x80528b70u, 0x8052ab00u, 0x8052ab04u,
                0x8052ab08u, 0x800000c0u, 0x800000d4u, 0x800000d8u, 0x800000e4u, 0x80492920u,
                0x804b2b4cu, 0x935e0004u, 0x804b2a80u, 0x804b2a84u, 0x804b2a88u, 0x804b2a8cu}) {
                std::cout << ' ' << address << ' ' << nwii::runtime::bat_memory_read32(context, address);
            }
            std::cout << std::dec << '\\n';
            for (bool cached : {false, true}) {
                std::cout << (cached ? "BOOT_STM_ASYNC_CACHED" : "BOOT_STM_ASYNC_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, 0x135e0020 + index +
                        (cached ? 0x80000000 : 0xc0000000)));
                }
                std::cout << '\\n';
            }
'''
needle = '            if (context.pc == 0x80241c30 && context.lr == 0x80242384 &&'
replace_entry = 'entry = entry.replace(' + repr(needle) + ', ' + repr(memory_print + needle) + ', 1)\nentry_path.write_text(entry)'
mutations.append(('entry_path.write_text(entry)', replace_entry))
inject = ''.join('body = body.replace(' + repr(before) + ', ' + repr(after) + ', 1)\n' for before, after in mutations)
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
assert body.count(marker) == 1
body = body.replace(marker, inject + marker, 1)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = root / 'mass-stm-async-boot'
path = output / 'build.json'
report = json.loads(path.read_text())
report['asyncParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['asyncOracleSha256'] = hashlib.sha256((root / 'dolphin-stm-async/comparison.json').read_bytes()).hexdigest()
report['dispatcherResume'] = {'pc': '0x8021753c', 'function': '0x80217520', 'instruction': '0x54838ffe'}
report['sourceHashes'][str(output / 'ipc_event_order_probe.cpp')] = hashlib.sha256((output / 'ipc_event_order_probe.cpp').read_bytes()).hexdigest()
report['limits'] = ['Existing STM device owns one deferred request; observer pointer is read-only, no second pending queue or registry.',
    'Exactly original1000 request/ACK/no-reply profile; no completion/rearm/cancel or power event implemented.',
    'Original caller/heap/cache retained; native event tick and PI/loader profiles are disclosed PC adaptations.']
path.write_text(json.dumps(report, indent=2) + '\n')
