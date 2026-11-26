"""Third ES request and first two shared-kernel replies; inquiry response remains refused."""
from pathlib import Path
import json

parent = Path('experiments/wii-static-recomp/build_di_burst_sender_boot.py')
body = parent.read_text().replace('mass-di-burst-sender-boot', 'mass-di-burst-es-boot')
extra = '''
(output / 'di_burst_es.h').write_bytes((experiment / 'di_burst_es.h').read_bytes())
replace(front, '#include "di_burst_sender.h"', '#include "di_burst_sender.h"\\n#include "di_burst_es.h"')
replace(front, '    if (experiment_di_burst_sender_write(context, address, value))', '    if (experiment_di_burst_es_write(context, address, value)) { return; }\\n    if (experiment_di_burst_sender_write(context, address, value))')
replace(front, '    if (experiment_di_burst_sender_read(context, address, burstValue))', '    if (experiment_di_burst_es_read(context, address, burstValue)) { return burstValue; }\\n    if (experiment_di_burst_sender_read(context, address, burstValue))')
replace(front, '    if ((stmSubmitted == 33 || stmSubmitted == 34)', '    if (experiment_di_burst_arm_match(message, arm)) { return true; }\\n    if ((stmSubmitted == 35) && message == 0x135e0140 && arm == 0x135e0080 && experimentDiBurstPending[0] == arm) { return true; }\\n    if ((stmSubmitted == 33 || stmSubmitted == 34)')
replace(front, 'ipc.armMessage == ipc.ppcMessage', '(ipc.armMessage == ipc.ppcMessage || experiment_di_burst_arm_match(ipc.ppcMessage, ipc.armMessage))', front.read_text().count('ipc.armMessage == ipc.ppcMessage'))
replace(front, '|| stmSubmitted == 32)', '|| stmSubmitted == 32 || stmSubmitted == 36)', front.read_text().count('|| stmSubmitted == 32)'))
replace(output / 'si_external_delivery.h', '|| stmSubmitted == 32)', '|| stmSubmitted == 32 || stmSubmitted == 36)', 2)
replace(output / 'si_external_delivery.h', '(ipc.ppcControl == 0x32 ||', '(ipc.ppcControl == 0x34 || ipc.ppcControl == 0x32 ||')
replace(front, '(kind != 4 && stmSubmitted == 32)', '(kind != 4 && stmSubmitted == 36)')
replace(front, '    hw::experiment_ipc_control_latched_irq(value);', '    if (stmSubmitted == 36 && final && context.gpr[31] == 0x935e0080) {\\n        if (bat_memory_read32(context, 0x804983a8) || bat_memory_read32(context, 0x804b2b4c) != 0x935e0060) { throw std::runtime_error("DI86 source retirement unverified"); }\\n        experimentDiBurstFirstRetired = true;\\n    }\\n    hw::experiment_ipc_control_latched_irq(value);')
replace(wrapper, 'void experiment_di_burst_ack(CPUContext&, uint32_t request) {', (experiment / 'di_burst_replies.inc').read_text() + '\\nvoid experiment_di_burst_ack(CPUContext&, uint32_t request) {')
replace(wrapper, 'request == 0x135e00e0 ? 1 : 3', 'request == 0x135e00e0 ? 1 : request == 0x135e0140 ? 2 : 3')
replace(wrapper, 'slot >= 2', 'slot >= 3')
replace(wrapper, '    std::cout << "DI_BURST_PENDING_ACK "', '    if (slot == 2) { experiment_di_burst_reply_begin(); }\\n    std::cout << "DI_BURST_PENDING_ACK "')
observer = """if (nwii::runtime::stmSubmitted == 36) {
            for (bool cached : {false, true}) {
                std::cout << (cached ? "DI_BURST_REPLY_CACHED" : "DI_BURST_REPLY_PHYSICAL");
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (cached ? 0x935e0080u : 0xd35e0080u) + index));
                }
                std::cout << std::endl;
            }
        }
        """
replace(output / 'mass_boot.cpp', 'std::cout << "BOOT_ES_LAYOUT "', observer + 'std::cout << "BOOT_ES_LAYOUT "')
'''
marker = 'extra = extra.replace(chr(39)'
assert body.count(marker) == 1
body = body.replace(marker, 'extra += ' + repr(extra) + '\n' + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-di-burst-es-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'] = ['All three requests retained; DI86 reply prepared through existing kernel/scheduler.',
    'ES reply scheduled only after source retirement; runtime currently stops at unmapped dcbi BEFORE DI86 callback. ES/inquiry response and cache audit unverified. PC ticks are not Wii cycles.']
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
