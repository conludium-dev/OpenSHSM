"""Fail unless the separate experiment has current evidence for every milestone gate."""
from pathlib import Path
import hashlib
import json
import re
import struct

private = Path('work/private-game/static-recomp')
generated = private / 'nwii-current'
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(dol).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
execution = json.loads((private / 'execution-unicorn-vs-nwii.json').read_text())
windows = json.loads((private / 'execution-windows-vs-original.json').read_text())
runtime = json.loads((private / 'runtime-probe.json').read_text())
ghidra = json.loads((private / 'ghidra-verification.json').read_text())
current_cpp = hashlib.sha256((generated / 'selected.cpp').read_bytes()).hexdigest()
traces = re.findall(r'// 0x([0-9A-F]{8}): ([0-9A-F]{8})', (generated / 'selected.cpp').read_text())
assert len(traces) == 34 and len({address for address, _ in traces}) == 34
header = struct.unpack('>64I', dol[:256])
for address, opcode in traces:
    address = int(address, 16)
    index = next(index for index in range(18) if header[18 + index] <= address < header[18 + index] + header[36 + index])
    offset = header[index] + address - header[18 + index]
    assert struct.unpack_from('>I', dol, offset)[0] == int(opcode, 16)
for report in (execution, windows, runtime):
    assert report['result'] == 'PASS' and report['generatedSha256'] == current_cpp
assert execution['dolSha256'] == hashlib.sha256(dol).hexdigest()
assert windows['originalOracleSha256'] == hashlib.sha256((private / 'execution-unicorn-vs-nwii.json').read_bytes()).hexdigest()
assert runtime['productionSandboxSha256'] == hashlib.sha256(Path('outputs/shsm-research/native/sandbox.cpp').read_bytes()).hexdigest()
assert ghidra['result'] == 'PASS' and ghidra['boundaryBytes'] == 96 and ghidra['instructions'] == 24
assert ghidra['objectSha256'] == hashlib.sha256((private / 'dtk-output/obj/auto_03_800F2228_text.o').read_bytes()).hexdigest()
assert ghidra['decompiledSha256'] == hashlib.sha256((generated / 'ghidra-selected.c').read_bytes()).hexdigest()
assert runtime['wrapperSha256'] == hashlib.sha256(Path('experiments/wii-static-recomp/runtime_probe.cpp').read_bytes()).hexdigest()
assert 'language=PowerPC:BE:32:default' in (generated / 'ghidra-result.txt').read_text()
objdiff = json.loads((private / 'objdiff-reference.json').read_text())


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


matches = [row for row in objects(objdiff) if row.get('name') == 'fn_800F3E60' and 'match_percent' in row]
assert len(matches) == 2 and all(row['match_percent'] == 100 for row in matches)
catalogue = (generated / 'nwii-functions.tsv').read_text().splitlines()
selected = {int(row.split('\t')[0], 16): row.split('\t')[1:] for row in catalogue}
for start, end, count in [(0x800c770c, 0x800c7720, 5), (0x800c7720, 0x800c7734, 5), (0x800f3e60, 0x800f3ec0, 24)]:
    assert int(selected[start][0], 16) == end and int(selected[start][1]) == count
release_hashes = {
    'outputs/shsm-research/OpenSHSM-0.0.41.exe': 'b5b417f452860cd9a303e988c9f675af4c9af6f38012d6e107d77250d2ac2606',
    'outputs/shsm-native-research.zip': '7b11866f9d7dba4a10e722c3afce6010a6fb9ee20626a70e290b831a3c98789c',
    'outputs/OpenSHSM-0.0.41.zip': '7b11866f9d7dba4a10e722c3afce6010a6fb9ee20626a70e290b831a3c98789c'}
assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected for path, expected in release_hashes.items())
report = {'result': 'PASS', 'milestone': 'one bounded original SHSM function',
          'function': '0x800F3E60', 'bytes': 96, 'instructions': 24, 'helperFunctions': ['0x800C770C', '0x800C7720'],
          'automaticFunctionCandidates': len(catalogue), 'oracleCases': execution['cases'], 'windowsCases': windows['cases'],
          'runtimeSmokeCases': 4, 'objdiffSelectedFunctionPercent': 100, 'releaseUnchanged': True,
          'generatedSha256': current_cpp, 'dolSha256': execution['dolSha256'],
          'generatedOriginalOpcodesVerified': len(traces),
          'sourceClassification': {'originalBehavior': 'Own DOL instructions, guarded option16 mutation and original getter/setter calls.',
                                   'inferredBehavior': 'Function naming and broader role derived from existing UI callback research.',
                                   'pcAdaptation': 'Synthetic guest memory/stack, C ABI bridge, trace instrumentation and isolated runtime entrypoint.'},
          'limits': ['Not full game boot or physical Wii trace; independent PPC750CL instruction emulator with controlled state.',
                     'No paired-single, GX/audio/IOS/controller consumer or live-gameplay acceptance.',
                     'NWiiRecomp restricted license remains outside production release; Ghidra MCP not connected.']}
(private / 'milestone.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS:Milestone DOL→NWii→native→execution→original PPC oracle→dtk/objdiff/Ghidra→OpenSHSM runtime roundtrip')
