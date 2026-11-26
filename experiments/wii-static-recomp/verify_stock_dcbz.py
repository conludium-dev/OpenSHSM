"""Compile the exact emitted zero blocks against current CPU/MMU; not cache-timing oracle."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base, output = root / 'window-quantization', root / 'window-thp-dcbz'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
build = json.loads((output / 'build.json').read_text())
sites = build['zeroSites']
assert len(sites) == 12 and all(site['ra'] in (0, 4) and site['rb'] in (0, 4) for site in sites)
header = output / 'dcbz-sites.h'
text = 'const unsigned dcbz_ra[] = {' + ','.join(str(site['ra']) for site in sites) + '};\n'
text += 'void dcbz_site(nwii::runtime::CPUContext& ctx, unsigned site) {\n switch (site) {\n'
for index, site in enumerate(sites):
    assert site['body'] in (output / 'output_37.cpp').read_text()
    text += f'case {index}:\n' + site['body'] + 'break;\n'
header.write_text(text + '}\n}\n')
source = Path('experiments/wii-static-recomp/stock_dcbz_contract.cpp').resolve()
exe = output / 'dcbz-contract'
result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++17', '-O2',
    '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
    '-I', str(base / 'include'), '-I', str(output), str(source), '-o', str(exe)],
    capture_output=True, text=True, timeout=60)
(output / 'contract-compile.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
(output / 'contract.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
(output / 'contract.json').write_text(json.dumps({'result': 'THP_DCBZ_COMPONENT_PASS', 'output': result.stdout.strip(),
    'sourceSha256': sha(source), 'generatedHeaderSha256': sha(header), 'executableSha256': sha(exe),
    'dependencySourceSha256': sha(Path('experiments/wii-static-recomp/stock_quantization_contract.cpp')),
    'cpuHeaderSha256': sha(base / 'include/runtime/cpu_context.h'),
    'parentBuildSha256': sha(output / 'build.json'),
    'limits': ['Current direct-memory model; no exact Wii cache/DCE/DSI/dcbz_l/timing verification.',
        'Exact original instruction sites checked by builder; component reference is 32-byte aligned zero semantics.',
        'MMIO stubs throw if reached, not full-runtime acceptance.']}, indent=2) + '\n')
print(result.stdout.strip())
