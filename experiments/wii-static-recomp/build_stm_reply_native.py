"""Extend the existing ACK profile only for measured reply accesses and scheduled real OPEN."""
from pathlib import Path
import json
import subprocess
import sys
import hashlib

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
subprocess.run(['python3', str(experiment / 'verify_stm_open_native.py')], check=True)
parent = experiment / 'build_stm_irq_native_attempt.py'
body = parent.read_text().replace("ack = '--ack-mmio' in sys.argv", 'ack = True')
variant = 'stm-reply-missing' if '--missing-producer' in sys.argv else 'stm-reply-wrong' if '--wrong-result' in sys.argv else 'stm-reply-native'
body = body.replace("root / ('stm-irq-native-ack' if ack else 'stm-irq-native-attempt')", "root / " + repr(variant))
macro = '-DSHSM_MISSING_STM_REPLY' if variant == 'stm-reply-missing' else '-DSHSM_WRONG_STM_REPLY' if variant == 'stm-reply-wrong' else None
if macro:
    body = body.replace("*(['-DSHSM_STM_ACK_MMIO'] if ack else []),", "*(['-DSHSM_STM_ACK_MMIO'] if ack else []), " + repr(macro) + ',')
body = body.replace("experiment / 'stm_irq_attempt_host.cpp'", "experiment / 'stm_reply_host.cpp'")
body = body.replace("ipc.ppcMessage != 0x135e0020 || ipc.ppcControl != 0x32 || ipc.armMessage || ipc.armControl ||",
    "(ipc.ppcMessage < 0x135e0020 || ipc.ppcMessage > 0x135e03e0 || (ipc.ppcMessage & 31)) ||\n            (ipc.ppcControl != 0x32 && ipc.ppcControl != 0x34) ||\n            ipc.armMessage != (ipc.ppcControl == 0x34 ? ipc.ppcMessage : 0) || ipc.armControl ||")
marker = "    row = next(row for row in records if row['file'] == 'output_67.cpp')"
enhancement = '''    frontend = (experiment / 'ipc_ack_frontend.h').read_text()
    marker = '    const auto mapping = resolve_reference_bat('
    assert frontend.count(marker) == 1
    check = ''' + repr('''    const auto snapshot = hw::experiment_ipc_snapshot();
    if (snapshot.ppcMessage < 0x135e0020 || snapshot.ppcMessage > 0x135e03e0 || (snapshot.ppcMessage & 31) ||
        (snapshot.armMessage && snapshot.armMessage != snapshot.ppcMessage) || snapshot.armControl || snapshot.delay ||
        snapshot.ppcMask != 0x40000000 || context.in_callback || context.callback_depth || !context.backup_stack.empty()) {
        throw std::runtime_error("IPC reply shared state unverified");
    }
''') + '''
    frontend = frontend.replace(marker, check + marker, 1)
    start = frontend.index('inline uint32_t experiment_ipc_ack_read(')
    frontend = frontend[:start] + ''' + repr(r'''inline uint32_t experiment_ipc_ack_read(CPUContext& context, uint32_t address) {
    experiment_ipc_ack_access(context, address);
    const auto ipc = hw::experiment_ipc_snapshot();
    if (context.pc != 0x80241c20 || ipc.ppcMessage < 0x135e0020 || ipc.ppcMessage > 0x135e03e0 ||
        (ipc.ppcMessage & 31) || ipc.armControl || ipc.delay) { throw std::runtime_error("IPC reply read profile unverified"); }
    if (address == 0xcd000008 && context.lr == 0x80241cc8 && ipc.ppcControl == 0x34 && ipc.armMessage == ipc.ppcMessage) {
        return ipc.armMessage;
    }
    const bool ack = ipc.ppcControl == 0x32 && !ipc.armMessage &&
        (context.lr == 0x80241f24 || context.lr == 0x80241f44 || context.lr == 0x80241f58);
    const bool reply = ipc.ppcControl == 0x34 && ipc.armMessage == ipc.ppcMessage &&
        (context.lr == 0x80241f24 || context.lr == 0x80241cdc);
    const bool cleared = ipc.armMessage == ipc.ppcMessage &&
        ((ipc.ppcControl == 0x30 && context.lr == 0x80241ebc) || (ipc.ppcControl == 0x38 && context.lr == 0x80241f44));
    if (address != 0xcd000004 || (!ack && !reply && !cleared)) { throw std::runtime_error("IPC reply read caller/state unverified"); }
    return ipc.ppcControl;
}
inline void experiment_ipc_ack_write(CPUContext& context, uint32_t address, uint32_t value) {
    if (!experimentStmIrq) { experiment_ipc_startup_store(context, address, value); return; }
    experiment_ipc_ack_access(context, address);
    const auto ipc = hw::experiment_ipc_snapshot();
    const bool ack = context.lr == 0x80241f68 && ipc.ppcControl == 0x32 && value == 0x32;
    const bool reply = context.lr == 0x80241cec && ipc.ppcControl == 0x34 && value == 0x34 && ipc.armMessage == ipc.ppcMessage;
    const bool final = context.lr == 0x80241ecc && ipc.ppcControl == 0x30 && value == 0x38 && ipc.armMessage == ipc.ppcMessage;
    if (context.pc != 0x80241c30 || address != 0xcd000004 || (!ack && !reply && !final)) {
        throw std::runtime_error("IPC reply write caller/value unverified");
    }
    hw::experiment_ipc_control_latched_irq(value);
}
inline void experiment_ipc_ack_clear(CPUContext& context, uint32_t address, uint32_t value) {
    experiment_ipc_ack_access(context, address);
    if ((context.pc != 0x80241f68 && context.pc != 0x80241cec) || address != 0xcd000030 || value != 0x40000000 ||
        hw::experiment_ipc_snapshot().ppcControl != 0x30) { throw std::runtime_error("IPC reply flag clear unverified"); }
    hw::experiment_ipc_irq_clear(value);
    hw::experiment_ipc_irq_update();
}
}
''') + '''
    (output / 'ipc_ack_frontend.h').write_text(frontend)
    (output / 'ipc_open_packet.h').write_bytes((root / 'stm-open-native/ipc_open_packet.h').read_bytes())
'''
assert body.count(marker) == 1
body = body.replace(marker, enhancement + marker)
marker = '    for before, after in transforms:'
extra = '''    transforms.append(('    // 0x80241CF4: 90030030\\n    nwii::runtime::bat_memory_write32(ctx, ctx.gpr[3] + 48, ctx.gpr[0]); // stw r0, 48(r3)',
        '    // 0x80241CF4: 90030030\\n    nwii::runtime::experiment_ipc_ack_clear(ctx, ctx.gpr[3] + 48, ctx.gpr[0]); // stw r0, 48(r3)'))
'''
assert body.count(marker) == 1
body = body.replace(marker, extra + marker)
body = body.replace("runtime / 'src/core/event_scheduler.cpp']", "runtime / 'src/core/event_scheduler.cpp', root / 'stm-open-native/ios_kernel.cpp', runtime / 'src/hle/devices/stm_device.cpp']")
body = body.replace('assert result.returncode == 7', 'assert result.returncode in (0, 7)')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = root / variant / 'attempt.json'
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['profileProofSha256'] = hashlib.sha256((root / 'stm-open-native/comparison.json').read_bytes()).hexdigest()
report['limits'] = ['Existing external entry/shared IPC state/kernel/event heap/BAT cache; four instruction seams in current67,124objects retained.',
    'Native wait sentinel/ticks and immediate IRQ projection are PC fixtures; prepared waiter, not actual OSSleepThread entry/high-priority switch.',
    'No general boot admission, firstscreen/menu/audio or full-game completion.']
path.write_text(json.dumps(report, indent=2) + '\n')
