"""Inline the existing HID2 accessor body only in the decoder guard; keep dynamic checks/order."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
public = Path('experiments/wii-static-recomp').resolve()
output = root / 'window-hid2-inline'
output.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
parent_path = root / 'window-audio-callback/build.json'
parent = json.loads(parent_path.read_text())
for path, digest in {**parent['dependencies'], **parent['retainedInputs']}.items():
    assert sha(Path(path)) == digest
decoder_path = root / 'headless-psq-scale/build.json'
decoder = json.loads(decoder_path.read_text())
for path, digest in {**decoder['dependencies'], **decoder['retainedLinkInputs']}.items():
    assert sha(Path(path)) == digest
original = root / 'headless-psq-scale/output_37.cpp'
assert sha(original) == decoder['sourceSha256']
accessor = root / 'window-quantization/processor_adapter.cpp'
match = re.search(r'uint32_t experiment_read_hid2\(CPUContext& context\) \{.*?\n\}', accessor.read_text(), re.S)
assert match
accessor_body = match[0].replace('uint32_t experiment_read_hid2', 'inline uint32_t stock_inline_read_hid2', 1)
guard_original = root / 'headless-constant-fp/constant_fp_guard.h'
guard = guard_original.read_text()
marker = 'namespace nwii::runtime {\n'
assert guard.count(marker) == 1 and guard.count('experiment_read_hid2(ctx)') == 1
guard = guard.replace(marker, marker + accessor_body + '\n', 1).replace('experiment_read_hid2(ctx)', 'stock_inline_read_hid2(ctx)')
header = output / 'constant_fp_guard.h'
header.write_text(guard)
source, obj = output / 'output_37.cpp', output / 'output_37.cpp.o'
source.write_text(original.read_text())
arguments = json.loads((root / 'window-fp-guard/output_37.cpp.record.json').read_text())['arguments']
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', *arguments,
    '-I', str(original.parent), '-c', str(source), '-o', str(obj)], capture_output=True, text=True, timeout=180)
(output / 'compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr[-3000:]
command = list(parent['linkCommand'])
old = next(arg for arg in command if Path(arg).name == 'output_37.cpp.o')
assert old == str(original) + '.o'
command[command.index(old)] = str(obj)
exe = output / 'OpenSHSMStockHID2Inline'
command[command.index('-o') + 1] = str(exe)
subprocess.run(command, cwd=root / 'export/build', capture_output=True, check=True, timeout=180)
inputs = {}
for arg in command:
    if Path(arg).suffix in ('.o', '.a') and arg != str(obj):
        path = (Path(arg) if Path(arg).is_absolute() else root / 'export/build' / arg).resolve()
        inputs[str(path)] = sha(path)
(output / 'build.json').write_text(json.dumps({'result': 'HID2_INLINE_BUILT_EQUIVALENCE_PERFORMANCE_UNVERIFIED',
    'parentBuildSha256': sha(parent_path), 'decoderBuildSha256': sha(decoder_path),
    'sourceSha256': sha(source), 'objectSha256': sha(obj), 'executableSha256': sha(exe),
    'arguments': arguments, 'linkCommand': command, 'accessorBody': accessor_body,
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), original, accessor,
        guard_original, header, root / 'headless-psq-scale/psq_scale.h']}, 'retainedInputs': inputs,
    'limits': ['Decoder37 object only, exact existing accessor body inserted inline/no cached HID2/MSR/readiness.',
        'Dynamic FP/program/privilege checks and arithmetic/PSQ/MMU/guest code unchanged.',
        'All other guests/runtime/audio callback/PCboot/main retained; native differential/frame/performance pending.']}, indent=2) + '\n')
print('HID2_INLINE_BUILT_EQUIVALENCE_PERFORMANCE_UNVERIFIED')
