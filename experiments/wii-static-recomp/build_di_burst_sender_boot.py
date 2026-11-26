"""Retain concurrent requests and ACK inquiry; unverified ES sender still stops."""
from pathlib import Path
import json

parent = Path('experiments/wii-static-recomp/build_di_burst_idle_boot.py')
body = parent.read_text().replace('mass-di-burst-idle-boot', 'mass-di-burst-sender-boot')
extra = '''
(output / 'di_burst_sender.h').write_bytes((experiment / 'di_burst_sender.h').read_bytes())
replace(output / 'di_burst_idle.h', 'stmSubmitted != 32 || ipc.ppcMessage != 0x135e0080', '(stmSubmitted != 32 && stmSubmitted != 34) || ipc.ppcMessage != (stmSubmitted == 34 ? 0x135e00e0u : 0x135e0080u)')
replace(output / 'di_burst_idle.h', '0x804b2a80) != 16', '0x804b2a80) != (stmSubmitted == 34 ? 17u : 16u)')
replace(output / 'di_burst_idle.h', '0x804b2a88) != 0', '0x804b2a88) != (stmSubmitted == 34 ? 1u : 0u)')
replace(front, 'inline unsigned stmSubmitted = 0;', 'inline unsigned stmSubmitted = 0;\\n}\\n#include "di_burst_sender.h"\\nnamespace nwii::runtime {')
replace(front, 'inline uint32_t experiment_ipc_ack_read(CPUContext& context, uint32_t address) {', 'inline uint32_t experiment_ipc_ack_read(CPUContext& context, uint32_t address) {\\n    uint32_t burstValue = 0;\\n    if (experiment_di_burst_sender_read(context, address, burstValue)) { return burstValue; }')
replace(front, 'inline void experiment_ipc_ack_write(CPUContext& context, uint32_t address, uint32_t value) {', 'inline void experiment_ipc_ack_write(CPUContext& context, uint32_t address, uint32_t value) {\\n    if (experiment_di_burst_sender_write(context, address, value)) { return; }')
replace(front, 'inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm) {', 'inline bool experiment_fs_prior_arm(uint32_t message, uint32_t arm) {\\n    if ((stmSubmitted == 33 || stmSubmitted == 34) && message == 0x135e00e0 && arm == 0x135e0080 && experimentDiBurstPending[0] == arm) { return true; }')
replace(wrapper, 'void experiment_stm_submit(CPUContext&, uint32_t request) {', 'void experiment_di_burst_ack(CPUContext&, uint32_t request) {\\n    const unsigned slot = request == 0x135e0080 ? 0 : request == 0x135e00e0 ? 1 : 3;\\n    if (slot >= 2 || experimentDiBurstPending[slot]) { throw std::runtime_error("Concurrent DI ACK owner unverified"); }\\n    experimentDiBurstPending[slot] = request;\\n    hw::ipc_ppc_ctrl = 0x31;\\n    EventScheduler::get().schedule_after(64, [request](CPUContext&, uint64_t) {\\n        if (hw::ipc_ppc_msg != request || hw::ipc_ppc_ctrl != 0x31) { throw std::runtime_error("Concurrent DI ACK event state unverified"); }\\n        hw::ipc_ppc_ctrl = 0x32;\\n    });\\n    std::cout << "DI_BURST_PENDING_ACK " << std::hex << request << std::dec << \'\\\\n\';\\n}\\nvoid experiment_stm_submit(CPUContext& context, uint32_t request) {')
start = wrapper.read_text().index('    if (stmSubmitted == 31) {')
end = wrapper.read_text().index('    if (stmSubmitted == 25 ||', start)
replace(wrapper, wrapper.read_text()[start:end], '    if (stmSubmitted == 31) {\\n        experiment_di_burst_ack(context, request);\\n        return;\\n    }\\n')
'''
marker = "body = body.replace(marker, addition + '\\n' + marker)"
extra = extra.replace(chr(39) + chr(92) * 2 + 'n' + chr(39), 'std::endl')
assert body.count(marker) == 1
body = body.replace(marker, 'addition += ' + repr('changes += ' + repr(extra) + '\n') + '\n' + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-di-burst-sender-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['Two concurrent request owners retained; inquiry ACK via existing EventScheduler, replies withheld until third request policy.',
    'Next ES IRQ sender remains refused; no DI86/inquiry response or source callback completion claimed.64 ticks is PC adaptation.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
