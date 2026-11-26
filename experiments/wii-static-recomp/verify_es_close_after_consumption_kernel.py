"""Verify actual kernel FD4 close/reuse/error using unchanged ES16 device component."""
from pathlib import Path
import json

parent = Path('experiments/wii-static-recomp/verify_es_consumption_device.py')
body = parent.read_text().replace("'device-probe.cpp'", "'close-kernel-probe.cpp'").replace(
    "'device-probe'", "'close-kernel-probe'").replace("'compile.log'", "'close-kernel-compile.log'").replace(
    "'execution.log'", "'close-kernel-execution.log'").replace("'device-verification.json'", "'close-kernel-verification.json'")
marker = '    std::cout << "ES16_KERNEL_FD4_GUARDS32_PENDING_18REFUSALS_PASS'
extra = '''    std::array<uint8_t,36> saved{};
    std::copy_n(guarded, 36, saved.begin());
    std::array<uint8_t,8> savedInput{};
    std::copy_n(input, 8, savedInput.begin());
    if (kernel.close(context, 4) != IPC_OK || kernel.close(context, 4) != IPC_EINVAL ||
        kernel.ioctlv(context, req) != IPC_EINVAL || kernel.close(context, 99) != IPC_EINVAL) { return 20; }
    if (kernel.open(context, "/dev/es", 0) != 4 || kernel.close(context, 4) != IPC_OK) { return 21; }
    if (!std::equal(saved.begin(), saved.end(), guarded) || !std::equal(savedInput.begin(), savedInput.end(), input) || devices::experiment_stm_pending() != pending ||
        pending->cmd != original.cmd || pending->fd != original.fd || pending->req_addr != original.req_addr ||
        pending->in_buf != original.in_buf || pending->out_buf != original.out_buf) { return 22; }
'''
assert body.count(marker) == 1
body = body.replace(marker, extra + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/es-consumption-device/close-kernel-verification.json')
report = json.loads(path.read_text())
report['result'] = 'ACTUAL_ES_FD4_CLOSE_REUSE_CLOSED_IOCTL_REFUSAL_BUFFERS_PENDING_PASS'
report['limits'].append('Actual kernel closesFD4, repeated/invalid/closed-IOCTLV returnEINVAL, reopen reuses4 while other slots stay allocated; no native IRQ proof.')
path.write_text(json.dumps(report, indent=2) + '\n')
print('PASS actual ES kernel FD4 close/repeated-invalid-closedIOCTLV errors/reopen4/guard-input-pending unchanged')
