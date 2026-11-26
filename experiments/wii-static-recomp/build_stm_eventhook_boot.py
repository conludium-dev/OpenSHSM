"""Extend existing boot profile for exactly the proven consecutive eventhook OPEN."""
from pathlib import Path
import hashlib
import json
import subprocess

experiment = Path('experiments/wii-static-recomp')
root = Path('work/private-game/static-recomp')
for verifier in ('verify_stm_pair_dolphin.py', 'verify_stm_pair_ack_dolphin.py'):
    subprocess.run(['python3', str(experiment / verifier)], check=True)
parent = experiment / 'build_stm_startup_boot.py'
body = parent.read_text().replace('mass-stm-startup-boot', 'mass-stm-eventhook-boot')
extension = '''front = front.replace('stmSubmitted == 1', '(stmSubmitted == 1 || stmSubmitted == 3)')
front = front.replace('state.armMessage ||', '(state.armMessage && !(stmSubmitted >= 2 && state.armMessage == state.ppcMessage)) ||')
front = front.replace('!stmSubmitted && !state.ppcMessage &&', '(stmSubmitted == 0 || stmSubmitted == 2) && (!state.ppcMessage || (stmSubmitted == 2 && state.ppcMessage == value)) &&')
front = '#include "ipc_open_packet.h"\\n' + front
marker = '            MMIODispatcher::get().write32(address, value);'
assert front.count(marker) == 1
check = ''' + repr('''            if (stmSubmitted == 2) {
                const auto* packet = context.mmu.get_ptr(value);
                if (value != 0x135e0020 || experiment_ipc_be32(packet) != 1 ||
                    experiment_ipc_be32(packet + 12) != 0x439904 || experiment_ipc_be32(packet + 16) != 0) {
                    throw std::runtime_error("Consecutive STM eventhook request unverified");
                }
            }
''') + '''
front = front.replace(marker, check + marker)
front = front.replace('!ipc.armMessage &&', '(!ipc.armMessage || (stmSubmitted >= 3 && ipc.armMessage == ipc.ppcMessage)) &&')
delivery_path = output / 'si_external_delivery.h'
delivery = delivery_path.read_text().replace('namespace nwii::runtime {', 'namespace nwii::runtime {\\nextern unsigned stmSubmitted;', 1)
marker = 'ipc.armMessage != (ipc.ppcControl == 0x34 ? ipc.ppcMessage : 0)'
assert delivery.count(marker) == 1
delivery = delivery.replace(marker, 'ipc.armMessage != ((ipc.ppcControl == 0x34 || stmSubmitted >= 3) ? ipc.ppcMessage : 0)')
delivery_path.write_text(delivery)
packet_path = output / 'ipc_open_packet.h'
packet = packet_path.read_text().replace('(path != "/dev/stm/immediate" && path != "/dev/openshsm_missing")', '(path != "/dev/stm/immediate" && path != "/dev/stm/eventhook" && path != "/dev/openshsm_missing")')
packet = packet.replace('(path == "/dev/stm/immediate" && mode != 0)', '((path == "/dev/stm/immediate" || path == "/dev/stm/eventhook") && mode != 0)')
packet_path.write_text(packet)
'''
marker = "(output / 'ipc_ack_frontend.h').write_text(front)"
assert body.count(marker) == 1
body = body.replace(marker, extension + marker)
marker = 'wrapper_path.write_text(wrapper)'
replacements = [
    ('if (address == 0x80242550 && stmProduced == 1 && stmSubmitted == 2)',
        'if ((address == 0x80242550 && stmProduced == 1 && stmSubmitted == 2) || (address == 0x802174e0 && context.lr == 0x8021c940 && stmProduced == 2 && stmSubmitted == 4))'),
    ('std::cout << "BOOT_STM_FIRST_COMPLETE"', 'std::cout << (stmProduced == 2 ? "BOOT_STM_SECOND_COMPLETE" : "BOOT_STM_FIRST_COMPLETE")'),
    ("std::cout << std::dec << '\\n';\n        for (bool cached", "std::cout << std::dec << '\\n';\n        std::cout << \"BOOT_STM_FDS \" << bat_memory_read32(context, 0x8052ab20) << ' ' << bat_memory_read32(context, 0x8052ab24) << '\\n';\n        for (bool cached"),
    ('"BOOT_STM_FIRST_CACHED" : "BOOT_STM_FIRST_PHYSICAL"', '(stmProduced == 2 ? "BOOT_STM_SECOND_CACHED" : "BOOT_STM_FIRST_CACHED") : (stmProduced == 2 ? "BOOT_STM_SECOND_PHYSICAL" : "BOOT_STM_FIRST_PHYSICAL")')
]
observe = ''.join('wrapper = wrapper.replace(' + repr(before) + ', ' + repr(after) + ')\n' for before, after in replacements)
assert body.count(marker) == 1
body = body.replace(marker, observe + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = root / 'mass-stm-eventhook-boot/build.json'
report = json.loads(path.read_text())
report['parentBuilderSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['pairOracleSha256'] = hashlib.sha256((root / 'dolphin-stm-pair/comparison.json').read_bytes()).hexdigest()
report['ackOracleSha256'] = hashlib.sha256((root / 'dolphin-stm-pair-ack/comparison.json').read_bytes()).hexdigest()
report['limits'] = ['Exactly two original whole-boot STM OPENs attempted; retained ARM pointer is measured, not cleared.',
    'Eventhook OPEN mode0 only; subsequent IOCTL/callback/power-event behavior remains unverified and guarded.',
    'Existing event ticks/PI projection/loader native adaptations; not full original startup/physical timing or first-frame proof.']
path.write_text(json.dumps(report, indent=2) + '\n')
