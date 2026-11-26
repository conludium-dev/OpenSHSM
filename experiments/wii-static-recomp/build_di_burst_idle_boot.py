"""Admit only the observed three-request wait; retain unverified sender refusal."""
from pathlib import Path
import json

parent = Path('experiments/wii-static-recomp/build_di86_boot.py')
body = parent.read_text().replace('mass-di86-boot', 'mass-di-burst-idle-boot')
body = body.replace("\"('verify_di86_events_dolphin.py',)\"", "\"('verify_di86_events_dolphin.py', 'verify_di_burst_events_dolphin.py', 'verify_di86_idle_native.py')\"")
marker = 'body = body[:start] + changes + body[end:]'
assert body.count(marker) == 1
addition = '''
changes += "(output / 'di_burst_idle.h').write_bytes((experiment / 'di_burst_idle.h').read_bytes())\\n"
changes += "replace(output / 'si_external_delivery.h', 'inline bool experiment_fpu_vector_active(CPUContext& context);', 'inline bool experiment_fpu_vector_active(CPUContext& context);\\\\n}\\\\n#include \\\"di_burst_idle.h\\\"\\\\nnamespace nwii::runtime {')\\n"
changes += "replace(output / 'si_external_delivery.h', 'bat_memory_read32(context, (hw::experiment_ipc_snapshot().ppcMessage | 0x80000000u) + 44) != 0x80492658', '(bat_memory_read32(context, (hw::experiment_ipc_snapshot().ppcMessage | 0x80000000u) + 44) != 0x80492658 && !experiment_di_burst_wait(context))')\\n"
'''
body = body.replace(marker, addition + '\n' + marker)
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
output = Path('work/private-game/static-recomp/mass-di-burst-idle-boot')
report = json.loads((output / 'build.json').read_text())
report['limits'].append('Only exact observed queued-ES wait admitted; next IRQ sender/services remain refused. Native burst not complete.')
(output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
