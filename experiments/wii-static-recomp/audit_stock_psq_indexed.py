"""Verify all original bytes/lowerings, stronger actual helper contract, and later full boot evidence."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
from PIL import Image
from stock_psq_patch import lower_indexed

project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
output = root / 'window-psq'
build = root / 'export/build'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((output / 'build.json').read_text())
dol = (project / 'work/private-game/disc/DATA/sys/main.dol').read_bytes()
for module in manifest['modules']:
    original = root / 'export' / f"output_{module['index']}.cpp"
    source = output / original.name
    expected, sites = lower_indexed(original.read_text(), dol)
    assert source.read_text() == expected and sites == module['sites']
    assert sha(original) == module['baseSha256'] and sha(source) == module['sourceSha256']
    assert sha(output / f"output_{module['index']}.cpp.o") == module['objectSha256']
for name, digest in manifest['retainedGuestObjects'].items():
    assert sha(build / name) == digest
assert sha(output / 'stock_psq_indexed.h') == manifest['headerSha256']
assert sha(project / 'experiments/wii-static-recomp/stock_psq_indexed.h') == manifest['headerSha256']
flags = (build / 'CMakeFiles/OpenSHSMStockBaseline.dir/flags.make').read_text()
compiler = re.search(r'# compile CXX with (.+)', flags)[1]
arguments = []
for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
    arguments += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
recipe = project / 'experiments/wii-static-recomp/stock_psq_contract.cpp'
probe = output / 'psq-strong-contract'
subprocess.run([compiler, *arguments, '-I', str(output), str(recipe), '-o', str(probe)], check=True, timeout=60)
result = subprocess.run([str(probe)], capture_output=True, text=True, timeout=20)
assert result.returncode == 0, result.stdout + result.stderr
label = 'window-psq-headless-gx-windowed-indexed35'
run = json.loads((root / (label + '-result.json')).read_text())
log = root / (label + '.log')
assert sha(log) == run['logSha256']
assert run['executableSha256'] == manifest['executableSha256']
assert sha(output / 'OpenSHSMStockPSQIndexed') == manifest['executableSha256']
assert run['deadlineReached'] and run['terminalReturncode'] == 0
text = log.read_text()
assert 'UNIMPLEMENTED Opcode' not in text and 'Unverified indexed PSQ' not in text
assert '[Sample] pc=0x801ac63c' in text
assert '[STAT] 25s frames=1114 draws=2293' in text
bmp = root / 'window-psq-indexed35-efb_1500.bmp'
png = bmp.with_suffix('.png')
with Image.open(bmp) as a, Image.open(png) as b:
    assert a.size == b.size == (640, 480)
    assert a.convert('RGBA').tobytes() == b.convert('RGBA').tobytes()
(output / 'audit.json').write_text(json.dumps({
    'result': 'INDEXED_PSQ_FLOAT_PROFILE_CONTRACT_AND_TITLE_BOOT_PASS',
    'sites': sum(len(module['sites']) for module in manifest['modules']),
    'rebuiltModules': len(manifest['modules']), 'retainedModules': len(manifest['retainedGuestObjects']),
    'strongContractOutput': result.stdout, 'strongContractSha256': sha(recipe),
    'runLogSha256': sha(log), 'captureBmpSha256': sha(bmp), 'capturePngSha256': sha(png),
    'visualObservation': 'Original Silent Hill Shattered Memories title/copyright image, dark fade, separately inspected.',
    'limits': ['Primary Dolphin indexed EA/W/I/update semantics and own DOL bytes corroborate profile; no live Wii oracle.',
        '8192 RAM/address/helper cases use trap host stubs; not all207 original sites executed or full PSQ/FPU/DSI proof.',
        'Ghidra MCP unavailable; installed default PowerPC languages lack Gekko-specific acceptance for these opcodes.',
        'Next repeated801AC63C is original heap-list traversal, cause unverified; no menu/input/gameplay claim.']
}, indent=2) + '\n')
print(result.stdout.strip())
print('PASS207 byte-checked sites /12 rebuilt/63 retained; observed original dark title, next heap traversal unverified')
