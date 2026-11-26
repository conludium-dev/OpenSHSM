"""Inspect the complete original IOS_Open body using the existing headless verifier."""
from pathlib import Path
import hashlib
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--allocator', action='store_true')
parser.add_argument('--free', action='store_true')
args = parser.parse_args()

builder = Path('experiments/wii-static-recomp/verify_frsp_roots_ghidra.py')
body = builder.read_text().replace("output = private / 'frsp-roots/ghidra'", "output = private / 'ios-open-wrapper/ghidra'")
old = "[('fn_801015CC', 'auto_03_80100D70_text.o', 54, 216),\n                                    ('fn_801123DC', 'auto_03_8010EE1C_text.o', 115, 460)]"
assert body.count(old) == 1
body = body.replace(old, ("[('iosCreateHeap', 'auto_03_802045CC_text.o', 76, 304), "
                         "('fn_802436A0', 'auto_03_802045CC_text.o', 127, 508)]") if args.allocator else
                         "[('IOS_Open', 'auto_03_802045CC_text.o', 72, 288)]")
if args.free:
    selected = ("[('iosCreateHeap', 'auto_03_802045CC_text.o', 76, 304), "
                "('fn_802436A0', 'auto_03_802045CC_text.o', 127, 508)]") if args.allocator else (
                "[('IOS_Open', 'auto_03_802045CC_text.o', 72, 288)]")
    assert body.count(selected) == 1
    body = body.replace(selected, "[('iosFree', 'auto_03_802045CC_text.o', 121, 484)]")
body = body.replace('shsm-frsp-roots-', 'shsm-ios-open-')
if args.allocator:
    body = body.replace("output = private / 'ios-open-wrapper/ghidra'", "output = private / 'ios-open-allocator/ghidra'")
if args.free:
    body = body.replace("output = private / 'ios-open-allocator/ghidra'" if args.allocator else
                        "output = private / 'ios-open-wrapper/ghidra'", "output = private / 'ios-open-free/ghidra'")
body = body.replace('PASS two scalar roots Ghidra169instructions/676bytes/decompilation; paired root/runtime behavior pending',
                    'PASS IOS_Open Ghidra72reachable instructions/288bytes; unreachable NOP excluded')
failure_log = Path('work/private-game/static-recomp/ios-open-wrapper/ghidra/IOS_Open.log')
if failure_log.exists() and 'Boundary mismatch: 72/288' in failure_log.read_text():
    (failure_log.parent / 'initial-contiguous-boundary.log').write_text(failure_log.read_text())
if args.allocator:
    body = body.replace('PASS IOS_Open Ghidra72reachable instructions/288bytes; unreachable NOP excluded',
                        'PASS original heap creation/allocator Ghidra boundaries')
if args.free:
    body = body.replace('PASS original heap creation/allocator Ghidra boundaries' if args.allocator else
                        'PASS IOS_Open Ghidra72reachable instructions/288bytes; unreachable NOP excluded',
                        'PASS iosFree Ghidra121reachable instructions/484bytes')
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = Path('work/private-game/static-recomp/ios-open-free/ghidra/verification.json' if args.free else
            'work/private-game/static-recomp/ios-open-allocator/ghidra/verification.json' if args.allocator else
            'work/private-game/static-recomp/ios-open-wrapper/ghidra/verification.json')
report = json.loads(path.read_text())
if args.free:
    addresses = [int(line.split()[0], 16) for line in (path.parent / 'iosFree.asm').read_text().splitlines()]
    assert len(addresses) == 121
    assert {address - addresses[0] for address in addresses} == set(range(0, 488, 4)) - {0xB4}
    report['result'] = 'ORIGINAL_IOS_FREE_GHIDRA121_REACHABLE_INSTRUCTIONS484_BYTES_PASS'
    report['dtkContiguousSpanBytes'] = 488
    report['unreachableNopOriginalAddress'] = '0x80243964'
elif args.allocator:
    for name, size in [('iosCreateHeap', 304), ('fn_802436A0', 508)]:
        addresses = [int(line.split()[0], 16) for line in (path.parent / (name + '.asm')).read_text().splitlines()]
        assert {address - addresses[0] for address in addresses} == set(range(0, size, 4))
    report['result'] = 'ORIGINAL_IOS_HEAP_ALLOCATOR_GHIDRA203_INSTRUCTIONS812_BYTES_PASS'
else:
    assembly = (path.parent / 'IOS_Open.asm').read_text()
    addresses = [int(line.split()[0], 16) for line in assembly.splitlines()]
    assert len(addresses) == 72
    start = addresses[0]
    assert {address - start for address in addresses} == set(range(0, 292, 4)) - {0xAC}
    report['result'] = 'ORIGINAL_IOS_OPEN_GHIDRA72_REACHABLE_INSTRUCTIONS288_BYTES_PASS'
    report['dtkContiguousSpanBytes'] = 292
    report['unreachableNopOriginalAddress'] = '0x802425fc'
report['baseRunnerSha256'] = hashlib.sha256(builder.read_bytes()).hexdigest()
report['limits'] = ['Original dtk-labelled bodies independently disassembled/decompiled; labels are SDK signature evidence.',
                    'Native differential test uses explicit service fixtures; no full IOS/boot behavior claim.',
                    'Headless local Ghidra; Ghidra MCP unavailable.']
path.write_text(json.dumps(report, indent=2) + '\n')
