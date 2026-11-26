"""Read both next-request views on existing two-OPEN boot; no submission permission."""
from pathlib import Path
import hashlib
import json

parent = Path('experiments/wii-static-recomp/build_stm_eventhook_boot.py')
body = parent.read_text().replace('mass-stm-eventhook-boot', 'mass-stm-async-packet-observer')
marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
snapshot = '''                std::cout << "BOOT_STM_NEXT_CACHED " << physical;
                for (unsigned index = 0; index < 64; ++index) {
                    std::cout << ' ' << unsigned(nwii::runtime::bat_memory_read8(context, (physical | 0x80000000) + index));
                }
                std::cout << '\\n';
'''
needle = '                const auto path = nwii::runtime::experiment_ipc_be32(packet + 12);'
injection = "body = body.replace(" + repr(needle) + ", " + repr(snapshot.replace('\\n', '\\\\n') + needle) + ", 1)\n"
assert body.count(marker) == 1
body = body.replace(marker, injection + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/mass-stm-async-packet-observer/build.json')
report = json.loads(path.read_text())
report['observerParentSha256'] = hashlib.sha256(parent.read_bytes()).hexdigest()
report['limits'] = ['Read-only additional cached-view observation at retained third-request guard; no command6 submission or callback execution.',
    'Existing whole-boot two-OPEN native profile and original pair/ACK references; cached metadata requires source verification.']
path.write_text(json.dumps(report, indent=2) + '\n')
