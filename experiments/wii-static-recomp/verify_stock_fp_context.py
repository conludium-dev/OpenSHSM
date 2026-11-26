"""Compare exact old/new HLE helpers with DOL-verified PSQ store/load layout."""
from pathlib import Path
import hashlib
import json
import subprocess
from stock_fp_context_patch import adapt_fp_context

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-quantization', root / 'window-fp-context'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
old = (base / 'ios.cpp').read_text()
new = (output / 'ios.cpp').read_text()
assert new == adapt_fp_context(old) and sha(output / 'ios.cpp') == build['sourceSha256']
header = output / 'context-helpers.h'
text = ''
for label, body in [('baseline', old), ('corrected', new)]:
    start = body.index('static void hle_save_context_to_guest(')
    end = body.index('int g_trace_after_dec', start)
    text += body[start:end].replace('hle_save_context_to_guest', label + '_save').replace('hle_load_context_from_guest', label + '_load')
header.write_text(text)
source = Path('experiments/wii-static-recomp/stock_fp_context_contract.cpp').resolve()
exe = output / 'context-contract'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++17', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    '-I', str(base / 'include'), '-I', str(output), str(source), '-o', str(exe)],
    capture_output=True, text=True, timeout=60)
(output / 'contract-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
(output / 'contract.json').write_text(json.dumps({'result': 'FP_CONTEXT_PAIRED_LAYOUT_COMPONENT_PASS',
    'sourceSha256': sha(source), 'helperHeaderSha256': sha(header), 'executableSha256': sha(exe),
    'cpuHeaderSha256': sha(base / 'include/runtime/cpu_context.h'), 'parentBuildSha256': sha(output / 'build.json'),
    'output': result.stdout.strip(), 'limits': ['Original64SDK PSQ words checked, PSQ byte-layout comparison, not physical Wii execution.',
        'Finite fixtures only; full FPSCR/exceptions/lazy FPU ownership/IRQ semantics unverified.',
        'Extracted exact HLE helpers tested with forbidden-MMIO stubs; not full runtime acceptance.']}, indent=2) + '\n')
print(result.stdout.strip())
