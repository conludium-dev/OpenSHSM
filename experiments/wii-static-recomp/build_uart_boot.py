"""Enable only the verified UART protocol in the existing dispatcher boot."""
from pathlib import Path
import hashlib
import json
import subprocess
import struct

experiment = Path('experiments/wii-static-recomp')
private = Path('work/private-game/static-recomp')
output = private / 'mass-uart-boot'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', str(experiment / 'verify_uart_native.py')], check=True)
canonical = experiment / 'mass_boot.cpp'
entry_source = canonical.read_text()
assert entry_source.count('        func_80006310(context);') == 1
entry_source = entry_source.replace('        func_80006310(context);', '        run_game(context);')
assert entry_source.count('if (++calls > 1000)') == 1
entry_source = entry_source.replace('if (++calls > 1000)', 'if (++calls > 20000)')
(output / 'mass_boot.cpp').write_text('extern "C" void run_game(nwii::runtime::CPUContext&);\n' + entry_source)
builder = experiment / 'build_exi_getid_boot.py'
body = builder.read_text().replace("output = private / 'mass-exi-getid-boot'", "output = private / 'mass-uart-boot'")
runtime = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp/nWiiRuntime')
module = private / 'mass-current'
metadata = json.loads((private / 'exi-getid-native/execution.json').read_text())
record = next(row for row in metadata['records'] if row['file'] == 'output_63.cpp')
source_input = Path(record['source'])
assert sha(source_input) == record['sourceSha256']
source_body = source_input.read_text()
dol = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
header = struct.unpack('>64I', dol[:256])
section = next(i for i in range(7) if header[18 + i] <= 0x80210620 < header[18 + i] + header[36 + i])
assert struct.unpack_from('>I', dol, header[section] + 0x80210620 - header[18 + section])[0] == 0xa083206c
before = '    // 0x80210620: A083206C\n    ctx.gpr[4] = nwii::runtime::bat_memory_read16(ctx, ctx.gpr[3] + 8300); // lhz\n'
after = '    // 0x80210620: A083206C\n    ctx.gpr[4] = nwii::runtime::experiment_uart_next_read16(ctx, ctx.gpr[3] + 8300, 0x80210620); // lhz\n'
assert source_body.count(before) == 2
source = output / 'output_63.cpp'
source.write_text(source_body.replace(before, after))
obj = output / 'output_63.cpp.o'
compiled = subprocess.run(['arch', '-arm64', 'clang++', '-std=c++20', '-O0', '-include', str(experiment / 'uart_next_observer.h'),
    '-I', str(runtime / 'include'), '-I', str(module), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'observer-build.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr[-3000:]
old_objects = "*[row['object'] for row in execution['records']]"
assert body.count(old_objects) == 1
body = body.replace(old_objects, "*[str(output / 'output_63.cpp.o') if row['file'] == 'output_63.cpp' else row['object'] for row in execution['records']]")
marker = "wrapper.write_text('#include \"exi_getid_frontend.h\"\\n' + body)"
assert body.count(marker) == 1
call = '    const int result = original_boot_main(argc, argv);'
replacement = '    nwii::runtime::hw::experimentExiTransfer.uartAllowed = true;\n' + call
body = body.replace(marker, 'body = body.replace(' + repr(call) + ', ' + repr(replacement) + ')\n' + marker)
exec(compile(body, str(builder), 'exec'), {'__file__': __file__})
path = output / 'boot.json'
report = json.loads(path.read_text())
report['result'] = 'VERIFIED_UART_DISPATCH_BOOT_NEXT_GUARD_RETAINED'
report['baseBuilderSha256'] = sha(builder)
report['canonicalEntrySha256'] = sha(canonical)
report['entrySourceSha256'] = sha(output / 'mass_boot.cpp')
report['generatedDispatcherSourceSha256'] = sha(private / 'mass-current/main_output.cpp')
report['uartProofSha256'] = sha(private / 'uart-native/comparison.json')
report['backendSha256'] = sha(experiment / 'exi_getid_backend.h')
report['functionCallBudget'] = 20000
report['observer'] = {'sites': 2, 'inputSource': str(source_input), 'inputSha256': sha(source_input), 'sourceSha256': sha(source),
    'objectSha256': sha(obj), 'headerSha256': sha(experiment / 'uart_next_observer.h'), 'before': before, 'after': after}
report['limits'] = ['Measured UART0/1/clock4 protocol, existing shared EXI state and dispatcher; no ROM/SRAM/other device requests enabled.',
                    'Next guest guard retained; no menu/first frame/automatic IRQ/full boot acceptance.']
path.write_text(json.dumps(report, indent=2) + '\n')
