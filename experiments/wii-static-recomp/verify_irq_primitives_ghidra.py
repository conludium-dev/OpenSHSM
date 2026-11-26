"""Inspect original interrupt enable-state primitives with the existing Ghidra exporter."""
from pathlib import Path
import hashlib
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--reschedule', action='store_true')
args = parser.parse_args()

builder = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = builder.read_text()
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
roots = [('OSDisableInterrupts', 0x802174E0, 5), ('OSRestoreInterrupts', 0x80217520, 9)]
if args.reschedule:
    roots.append(('__OSReschedule', 0x8021A9C0, 5))
body = body.replace(old, repr([(name, 'auto_03_802045CC_text.o', count, count * 4) for name, entry, count in roots]))
folder = 'ios-thread-cycle-deferred' if args.reschedule else 'ios-thread-cycle-irqs'
body = body.replace("output = private / 'frsp-roots/ghidra'", f"output = private / '{folder}/ghidra'")
body = body.replace('shsm-frsp-roots-', 'shsm-irq-primitives-')
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
                    f'PASS original interrupt/reschedule roots Ghidra{sum(count for name, entry, count in roots)}instructions; IRQ delivery remains unverified')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp') / folder / 'ghidra/verification.json'
report = json.loads(path.read_text())
for name, entry, count in roots:
    addresses = [int(line.split()[0], 16) for line in (path.parent / (name + '.asm')).read_text().splitlines()]
    assert len(addresses) == count and {address - addresses[0] for address in addresses} == set(range(0, count * 4, 4))
report['result'] = 'ORIGINAL_INTERRUPT_PRIMITIVES_GHIDRA14_INSTRUCTIONS56_BYTES_PASS'
if args.reschedule:
    report['result'] = 'ORIGINAL_IRQ_RESCHEDULE_GHIDRA19_INSTRUCTIONS76_BYTES_PASS'
    report['rescheduleDtkSpanBytes'] = 24
    report['rescheduleUnreachableBlrAddress'] = '0x8021a9d4'
report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['limits'] = ['Static dtk SDK-labelled boundaries/decompilation only; execution checked by separate PPC/native cycle.',
                    'No pending IRQ delivery, vector execution, scheduler timing or full boot acceptance.',
                    'Headless Ghidra; Ghidra MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')
