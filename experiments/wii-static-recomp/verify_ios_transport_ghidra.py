"""Check the original transport body with the existing independent Ghidra exporter."""
from pathlib import Path
import hashlib
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--reply-handler', action='store_true')
parser.add_argument('--wakeup', action='store_true')
parser.add_argument('--select-thread', action='store_true')
parser.add_argument('--set-context', action='store_true')
parser.add_argument('--load-context', action='store_true')
parser.add_argument('--save-context', action='store_true')
parser.add_argument('--sleep', action='store_true')
parser.add_argument('--ipc-interrupt', action='store_true')
parser.add_argument('--irq-dispatch', action='store_true')
parser.add_argument('--scheduler-guards', action='store_true')
parser.add_argument('--exception-vector', action='store_true')
args = parser.parse_args()
if args.exception_vector:
    assert not any((args.reply_handler, args.wakeup, args.select_thread, args.set_context, args.load_context, args.save_context, args.sleep, args.ipc_interrupt, args.irq_dispatch, args.scheduler_guards))
    builder = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
    body = builder.read_text().replace("output = private / 'frsp-roots/ghidra'", "output = private / 'ios-exception-vector/ghidra'")
    old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
    assert body.count(old) == 1
    body = body.replace(old, "[('OSExceptionVector', 'auto_03_802045CC_text.o', 38, 152)]")
    body = body.replace('shsm-frsp-roots-', 'shsm-exception-vector-')
    exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
    path = Path('work/private-game/static-recomp/ios-exception-vector/ghidra/verification.json')
    report = json.loads(path.read_text())
    addresses = [int(line.split()[0], 16) for line in (path.parent / 'OSExceptionVector.asm').read_text().splitlines()]
    assert len(addresses) == 38 and {pc - addresses[0] for pc in addresses} == set(range(0, 152, 4))
    report['result'] = 'ORIGINAL_EXCEPTION_VECTOR_GHIDRA38_INSTRUCTIONS152_BYTES_PASS'
    report['limits'] = ['Copied template body boundaries/decompilation/offsets only; trailing end NOP excluded.', 'SDK label from dtk; relocated execution and SPRG lowerings checked separately; headless Ghidra, not MCP.']
    path.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS original exception vector Ghidra38instructions/152bytes')
    raise SystemExit(0)
assert not args.scheduler_guards or not any((args.reply_handler, args.wakeup, args.select_thread, args.set_context, args.load_context, args.save_context, args.sleep, args.ipc_interrupt, args.irq_dispatch))
if args.scheduler_guards:
    builder = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
    body = builder.read_text().replace("output = private / 'frsp-roots/ghidra'", "output = private / 'ios-external-irq/ghidra'")
    old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
    assert body.count(old) == 1
    body = body.replace(old, "[('OSDisableScheduler', 'auto_03_802045CC_text.o', 15, 60), ('OSEnableScheduler', 'auto_03_802045CC_text.o', 15, 60)]")
    body = body.replace('shsm-frsp-roots-', 'shsm-irq-scheduler-')
    body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
                        'PASS original scheduler guards Ghidra30instructions/120bytes')
    exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
    path = Path('work/private-game/static-recomp/ios-external-irq/ghidra/verification.json')
    report = json.loads(path.read_text())
    for name in ('OSDisableScheduler', 'OSEnableScheduler'):
        addresses = [int(line.split()[0], 16) for line in (path.parent / (name + '.asm')).read_text().splitlines()]
        assert len(addresses) == 15 and {pc - addresses[0] for pc in addresses} == set(range(0, 60, 4))
    report['result'] = 'ORIGINAL_SCHEDULER_GUARDS_GHIDRA30_INSTRUCTIONS120_BYTES_PASS'
    report['limits'] = ['Original scheduler guard boundaries/decompilation/offsets only; IRQ runtime behavior checked separately.',
                        'SDK labels from dtk; headless Ghidra, not MCP.']
    path.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0)
assert sum((args.reply_handler, args.wakeup, args.select_thread, args.set_context, args.load_context, args.save_context, args.sleep, args.ipc_interrupt, args.irq_dispatch)) <= 1
name, count, size = ('fn_80241CA0', 150, 600) if args.reply_handler else ('__ios_Ipc2', 144, 576)
if args.wakeup:
    name, count, size = 'fn_8021B5D0', 61, 244
if args.select_thread:
    name, count, size = 'SelectThread', 139, 556
if args.set_context:
    name, count, size = 'OSSetCurrentContext', 23, 92
if args.load_context:
    name, count, size = 'OSLoadContext', 54, 216
if args.save_context:
    name, count, size = 'fn_802138A0', 32, 128
if args.sleep:
    name, count, size = 'OSSleepThread', 59, 236
if args.ipc_interrupt:
    name, count, size = 'IPCInterruptHandler', 107, 428

builder = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = builder.read_text().replace("output = private / 'frsp-roots/ghidra'", "output = private / 'ios-transport/ghidra'")
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, "[('fn_802179B0', 'auto_03_802045CC_text.o', 170, 680), ('ExternalInterruptHandler', 'auto_03_802045CC_text.o', 20, 80)]" if args.irq_dispatch else f"[('{name}', 'auto_03_802045CC_text.o', {count}, {size})]")
if args.reply_handler:
    body = body.replace("output = private / 'ios-transport/ghidra'", "output = private / 'ios-reply-handler/ghidra'")
if args.wakeup:
    body = body.replace("output = private / 'ios-reply-handler/ghidra'" if args.reply_handler else
                        "output = private / 'ios-transport/ghidra'", "output = private / 'ios-wakeup/ghidra'")
if args.select_thread:
    body = body.replace("output = private / 'ios-transport/ghidra'", "output = private / 'ios-select-thread/ghidra'")
if args.set_context:
    body = body.replace("output = private / 'ios-transport/ghidra'", "output = private / 'ios-set-context/ghidra'")
if args.load_context:
    body = body.replace("output = private / 'ios-transport/ghidra'", "output = private / 'ios-load-context/ghidra'")
if args.save_context:
    body = body.replace("output = private / 'ios-transport/ghidra'", "output = private / 'ios-save-context/ghidra'")
if args.sleep:
    body = body.replace("output = private / 'ios-transport/ghidra'", "output = private / 'ios-sleep/ghidra'")
if args.ipc_interrupt:
    body = body.replace("output = private / 'ios-transport/ghidra'", "output = private / 'ios-ipc-interrupt/ghidra'")
if args.irq_dispatch:
    body = body.replace("output = private / 'ios-transport/ghidra'", "output = private / 'ios-irq-dispatch/ghidra'")
body = body.replace('shsm-frsp-roots-', 'shsm-ios-transport-')
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
                    f'PASS original {name} Ghidra{count}instructions/{size}bytes; execution remains pending')
if args.irq_dispatch:
    body = body.replace(f'PASS original {name} Ghidra{count}instructions/{size}bytes; execution remains pending',
                        'PASS original external IRQ/dispatcher Ghidra190instructions/760bytes; execution remains pending')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
if args.irq_dispatch:
    path = Path('work/private-game/static-recomp/ios-irq-dispatch/ghidra/verification.json')
    report = json.loads(path.read_text())
    for selected, total in [('fn_802179B0', 170), ('ExternalInterruptHandler', 20)]:
        addresses = [int(line.split()[0], 16) for line in (path.parent / (selected + '.asm')).read_text().splitlines()]
        assert len(addresses) == total and {address - addresses[0] for address in addresses} == set(range(0, total * 4, 4))
    report['result'] = 'ORIGINAL_EXTERNAL_IRQ_AND_DISPATCH_GHIDRA190_INSTRUCTIONS760_BYTES_PASS'
    report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
    report['limits'] = ['Static two-body boundaries/decompilation/exact offsets only; no execution or original vector acceptance.',
                        'Dispatcher identification inferred; dtk name is fn_802179B0. Ghidra MCP unavailable.']
    path.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0)
path = Path('work/private-game/static-recomp/ios-sleep/ghidra/verification.json' if args.sleep else
            'work/private-game/static-recomp/ios-save-context/ghidra/verification.json' if args.save_context else
            'work/private-game/static-recomp/ios-load-context/ghidra/verification.json' if args.load_context else
            'work/private-game/static-recomp/ios-set-context/ghidra/verification.json' if args.set_context else
            'work/private-game/static-recomp/ios-select-thread/ghidra/verification.json' if args.select_thread else
            'work/private-game/static-recomp/ios-wakeup/ghidra/verification.json' if args.wakeup else
            'work/private-game/static-recomp/ios-reply-handler/ghidra/verification.json' if args.reply_handler else
            'work/private-game/static-recomp/ios-transport/ghidra/verification.json')
if args.ipc_interrupt:
    path = Path('work/private-game/static-recomp/ios-ipc-interrupt/ghidra/verification.json')
report = json.loads(path.read_text())
addresses = [int(line.split()[0], 16) for line in (path.parent / (name + '.asm')).read_text().splitlines()]
expected = set(range(0, 240, 4)) - {0x3C} if args.sleep else set(range(0, 248, 4)) - {0x34} if args.wakeup else set(range(0, size, 4))
assert len(addresses) == count and {address - addresses[0] for address in addresses} == expected
report['result'] = f'ORIGINAL_IOS_{"SLEEP" if args.sleep else "SAVE_CONTEXT" if args.save_context else "LOAD_CONTEXT" if args.load_context else "SET_CONTEXT" if args.set_context else "SELECT_THREAD" if args.select_thread else "WAKEUP" if args.wakeup else "REPLY_HANDLER" if args.reply_handler else "TRANSPORT"}_GHIDRA{count}_INSTRUCTIONS{size}_BYTES_PASS'
if args.wakeup:
    report['dtkSpanBytes'] = 248
    report['unreachableNopAddress'] = '0x8021b604'
if args.sleep:
    report['dtkSpanBytes'] = 240
    report['unreachableNopAddress'] = '0x8021b51c'
if args.ipc_interrupt:
    report['result'] = 'ORIGINAL_IPC_INTERRUPT_GHIDRA107_INSTRUCTIONS428_BYTES_PASS'
report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['limits'] = ['Static dtk SDK-labelled body boundaries/decompilation only; native object compilation checked separately.',
                    'No transport execution/IOS completion/cache/thread/IRQ or full boot acceptance.',
                    'Headless Ghidra; Ghidra MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')
