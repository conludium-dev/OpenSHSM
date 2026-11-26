"""Check current HID2 integration provenance; never equate component PASS with boot."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import subprocess
from carry_lowering import lower as lower_carry

parser = argparse.ArgumentParser()
parser.add_argument('--tag')
parser.add_argument('--carry', action='store_true')
args = parser.parse_args()
assert args.tag is None or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
root = Path('work/private-game/static-recomp/stock-baseline').resolve()
output = root / ('window-hid2-carry' if args.carry else 'window-hid2')
experiment = Path('experiments/wii-static-recomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
lowering = json.loads((output / 'lowering.json').read_text())
assert sha(output / 'lowering.json') == build['loweringSha256']
assert sha(root / 'window-optimized/build.json') == lowering['baseGenerationSha256']
for key, name in [('adapterHeaderSha256', 'processor_adapter.h'), ('adapterSourceSha256', 'processor_adapter.cpp'),
    ('loweringScriptSha256', 'lower_processor.py')]:
    assert sha(experiment / name) == lowering[key]
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
dol = dol_path.read_bytes()
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
header = struct.unpack('>64I', dol[:256])
assert len(lowering['changes']) == 14 and len(lowering['files']) == (67 if args.carry else 2)
carry_count = 0
if args.carry:
    assert sha(experiment / 'carry_lowering.py') == lowering['carryLoweringSha256']
    assert sha(experiment / 'carry_adapter.h') == lowering['carryBaseHeaderSha256']
    assert sha(output / 'carry_adapter.h') == lowering['carryHeaderSha256']
    assert (output / 'carry_adapter.h').read_text() == (experiment / 'carry_adapter.h').read_text().replace(
        '#include "l2_adapter.h"', '#include "runtime/cpu_context.h"')
for item in lowering['files']:
    assert sha(root / 'window-optimized' / item['file']) == item['baseSha256']
    assert sha(output / item['file']) == item['sourceSha256']
    assert sha(output / (item['file'] + '.o')) == item['objectSha256']
    expected = (root / 'window-optimized' / item['file']).read_text().splitlines(True)
    changes = [change for change in lowering['changes'] if change['file'] == item['file']]
    for change in changes:
        address = int(change['address'], 16)
        word = int(change['opcode'], 16)
        section = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
        assert struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0] == word
        assert word >> 26 == 31 and ((word >> 1) & 1023) in (339, 467)
        assert ((word >> 16) & 31) | (((word >> 11) & 31) << 5) == 920
        index = next(i for i, line in enumerate(expected) if f'// 0x{address:08X}: {word:08X}' in line
            and expected[i + 1].strip() == change['priorLowering'])
        assert expected[index + 1].strip() == change['priorLowering']
        expected[index + 1] = '    ' + change['adapterLowering'] + '\n'
    expected_text = ''.join(expected)
    if args.carry:
        expected_text, carry_changes = lower_carry(expected_text, dol, stock=True)
        assert [dict(change, file=item['file']) for change in carry_changes] == [change for change in lowering['carryChanges'] if change['file'] == item['file']]
        carry_count += len(carry_changes)
    assert expected_text == (output / item['file']).read_text()
assert not args.carry or carry_count == 2087
assert sha(root / 'export/nWiiRuntime/include/runtime/cpu_context.h') == build['baseHeaderSha256']
expected_entry = '#include "processor_adapter.h"\n' + (root / 'window-paced/main.cpp').read_text().replace(
    'std::make_unique<nwii::runtime::CPUContext>()', 'std::make_unique<nwii::runtime::ProcessorContext>()')
assert expected_entry == (output / 'main.cpp').read_text() == (output / 'contract-entry.cpp').read_text()
assert (output / 'processor_adapter.cpp').read_bytes() == (experiment / 'processor_adapter.cpp').read_bytes()
assert (output / 'processor-contract.cpp').read_bytes() == (experiment / 'stock_processor_contract.cpp').read_bytes()
expected_interpreter = (root / 'export/nWiiRuntime/src/hle/interpreter.cpp').read_text()
for before, after in (
    ('else if (spr == 27) ctx.gpr[rD] = ctx.srr1;',
     'else if (spr == 27) ctx.gpr[rD] = ctx.srr1;\n            else if (spr == 920) ctx.gpr[rD] = experiment_read_hid2(ctx);'),
    ('else if (spr == 27) ctx.srr1 = ctx.gpr[rD];',
     'else if (spr == 27) ctx.srr1 = ctx.gpr[rD];\n            else if (spr == 920) experiment_write_hid2(ctx, ctx.gpr[rD]);')
):
    assert expected_interpreter.count(before) == 1
    expected_interpreter = expected_interpreter.replace(before, after)
assert '#include "processor_adapter.h"\n' + expected_interpreter == (output / 'interpreter.cpp').read_text()
for name, item in build['sources'].items():
    assert sha(output / name) == item['sourceSha256']
    assert sha(output / (name + '.o')) == item['objectSha256']
assert len(build['retainedObjects']) == (9 if args.carry else 74)
assert all(sha(Path(name)) == digest for name, digest in build['retainedObjects'].items())
for member, digest in build['retainedRuntimeMembers'].items():
    for archive in (root / 'window-draw-done/libnwiiruntime.a', output / 'libnwiiruntime.a'):
        assert hashlib.sha256(subprocess.check_output(['/usr/bin/ar', '-p', str(archive), member])).hexdigest() == digest
assert sha(output / 'libnwiiruntime.a') == build['archiveSha256']
assert sha(output / ('OpenSHSMStockHID2Carry' if args.carry else 'OpenSHSMStockHID2')) == build['executableSha256']
test = subprocess.run([str(output / 'processor-contract')], capture_output=True, text=True, timeout=20)
assert test.returncode == 0 and test.stdout.strip() == build['contract']
report = {'result': 'HID2_COMPONENT_AND_PROVENANCE_PASS', 'buildSha256': sha(output / 'build.json'),
    'originalDolSha256': sha(dol_path), 'contractExecutableSha256': sha(output / 'processor-contract'),
    'contract': test.stdout.strip(), 'limits': build['limits']}
if args.tag:
    prefix = root / (('window-hid2-carry' if args.carry else 'window-hid2') + '-headless-windowed-' + args.tag)
    run_path = Path(str(prefix) + '-result.json')
    log_path = Path(str(prefix) + '.log')
    run = json.loads(run_path.read_text())
    assert run['executableSha256'] == build['executableSha256']
    assert run['logSha256'] == sha(log_path) and run['originalDolSha256'] == sha(dol_path)
    log = log_path.read_text(errors='replace')
    report['runtime'] = {'runSha256': sha(run_path), 'terminalReturncode': run['terminalReturncode'],
        'deadlineReached': run['deadlineReached'], 'gpuHangReported': 'GPU Hang' in log,
        'readyMessages': re.findall(r'\[CALL\] 0x8009b090[^\n]+', log),
        'decoderCalls': re.findall(r'\[CALL\] 0x80209d80[^\n]+', log)}
(output / ('audit-' + (args.tag or 'component') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], test.stdout.strip(), 'runtime=', report.get('runtime', 'not checked'))
