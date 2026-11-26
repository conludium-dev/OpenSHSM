"""Create a private debug-map-free sampling candidate, preserving loaded section bytes."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2] / 'work/private-game/static-recomp/stock-baseline'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
build_path = root / 'window-post-present/build.json'
build = json.loads(build_path.read_text())
component_path = build_path.parent / 'component-verification.json'
component = json.loads(component_path.read_text())
assert component['buildSha256'] == sha(build_path)
assert component['result'] == 'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED'
original = Path(build['executablePath'])
assert sha(original) == build['executableSha256']
cache = Path(tempfile.mkdtemp(prefix='openshsm-sample-symbols-', dir='/private/tmp'))
exe = cache / 'OpenSHSMStockSampleSymbols'
command = ['/usr/bin/strip', '-S', '-o', str(exe), str(original)]
run = subprocess.run(command, capture_output=True, text=True, timeout=60)
assert run.returncode == 0, run.stderr

def sections(path):
    data = path.read_bytes()
    assert struct.unpack_from('<I', data)[0] == 0xFEEDFACF
    count, size = struct.unpack_from('<II', data, 16)
    position = 32
    result = {}
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', data, position)
        assert length >= 8 and position + length <= 32 + size <= len(data)
        if cmd == 0x19:
            nsects = struct.unpack_from('<I', data, position + 64)[0]
            assert 72 + nsects * 80 == length
            for index in range(nsects):
                offset = position + 72 + index * 80
                name = data[offset:offset + 16].split(b'\0')[0].decode()
                segment = data[offset + 16:offset + 32].split(b'\0')[0].decode()
                address, amount, file_offset = struct.unpack_from('<QQI', data, offset + 32)
                flags = struct.unpack_from('<I', data, offset + 64)[0]
                zero_fill = (flags & 0xFF) in (1, 0xC, 0x12)
                if not zero_fill:
                    assert file_offset + amount <= len(data)
                key = segment + ',' + name
                assert key not in result
                result[key] = {'address': address, 'size': amount, 'flags': flags,
                    'sha256': None if zero_fill else hashlib.sha256(data[file_offset:file_offset + amount]).hexdigest()}
        position += length
    assert position == 32 + size and '__TEXT,__text' in result
    return result

before, after = sections(original), sections(exe)
assert before == after
symbols = {}
for label, path in [('original', original), ('candidate', exe)]:
    rows = subprocess.check_output(['/usr/bin/nm', '-ap', str(path)], text=True)
    symbols[label] = {'osoEntries': sum(' OSO ' in row for row in rows.splitlines()),
        'decoderSymbol': '_func_80209D80' in rows, 'cpuThreadSymbol': 'cpu_thread_func' in rows}
assert symbols['original']['osoEntries'] > 0 and symbols['candidate']['osoEntries'] == 0
assert symbols['candidate']['decoderSymbol'] and symbols['candidate']['cpuThreadSymbol']
signature = subprocess.run(['/usr/bin/codesign', '--verify', str(exe)], capture_output=True, text=True, timeout=30)
assert signature.returncode == 0, signature.stderr
assert sha(original) == build['executableSha256']
report = {'result': 'DEBUG_MAP_REMOVED_LOADED_SECTIONS_IDENTICAL_SAMPLING_CANDIDATE',
    'dependencies': {str(path): sha(path) for path in [Path(__file__).resolve(), build_path, component_path, original]},
    'command': command, 'executablePath': str(exe), 'executableSha256': sha(exe),
    'sections': after, 'symbols': symbols, 'signatureVerified': True,
    'limits': ['All named loaded code/data/unwind/constant section bytes and addresses/sizes/flags equal; debug OSO map removed.',
        'Link-edit/load-command metadata differs; section equality is not a complete loader/runtime acceptance proof.',
        'Sampling tool timeout may have another cause; no demonstrated symbolication speedup, game launch or registration.',
        'Original verified executable unchanged, private diagnostic candidate only, not default/public release.']}
path = cache / 'verification.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(report['result'], path)
print(json.dumps(symbols, indent=2))
