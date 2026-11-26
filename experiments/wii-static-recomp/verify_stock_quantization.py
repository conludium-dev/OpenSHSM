"""Isolated CPU/RAM component test; forbidden MMIO stubs are not runtime acceptance."""
from pathlib import Path
import hashlib
import json
import subprocess
import struct
from stock_quantization_patch import adapt_quantization

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
base = root / 'window-locked-cache/include/runtime/cpu_context.h'
output = root / 'quantization-contract'
output.mkdir(exist_ok=True)
source = Path('experiments/wii-static-recomp/stock_quantization_contract.cpp').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
dol_path = Path('work/private-game/disc/DATA/sys/main.dol')
assert sha(dol_path) == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
dol = dol_path.read_bytes()
layout = struct.unpack('>64I', dol[:256])
sites = []
for address, expected in [(0x8020ACC4, 0x38603D04), (0x8020ACC8, 0x64633D04), (0x8020ACCC, 0x7C76E3A6)]:
    section = next(i for i in range(18) if layout[18 + i] <= address < layout[18 + i] + layout[36 + i])
    actual = struct.unpack_from('>I', dol, layout[section] + address - layout[18 + section])[0]
    assert actual == expected
    sites.append({'address': hex(address), 'word': hex(actual)})
records = []
for variant in ('baseline', 'corrected'):
    include = output / variant
    header = include / 'runtime/cpu_context.h'
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text(base.read_text() if variant == 'baseline' else adapt_quantization(base.read_text()))
    exe = output / (variant + '-probe')
    result = subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/c++', '-std=c++17', '-O2',
        '-isysroot', '/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk',
        '-ffp-contract=off', '-I', str(include), str(source), '-o', str(exe)], capture_output=True, text=True, timeout=60)
    (output / (variant + '-compile.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    (output / (variant + '-run.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == (2 if variant == 'baseline' else 0), result.stdout + result.stderr
    records.append({'variant': variant, 'headerSha256': sha(header), 'executableSha256': sha(exe),
        'returncode': result.returncode, 'output': result.stdout.strip()})
report = {'result': 'SIGNED_GQR_COMPONENT_COMPARISON_PASS', 'baseHeaderSha256': sha(base),
    'originalDolSha256': sha(dol_path), 'gqr6SetupSites': sites,
    'sourceSha256': sha(source), 'records': records,
    'limits': ['Dolphin algorithm reference and isolated CPU/RAM test, not physical Wii execution.',
        'Corrected header has NOT been integrated in the full runtime.',
        'NaN integer stores refused; FPSCR/exceptions/float PSQ exactness unverified.',
        'No video/boot/menu/audio/controller acceptance.']}
(output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
