"""Validate every original dispatcher route and report actual startup/capture evidence, including fatal stop."""
from pathlib import Path
import bisect
import hashlib
import json
import re
import struct
from PIL import Image
from stock_dispatch_patch import adapt_dispatch

root = Path('work/private-game/static-recomp/stock-baseline').resolve()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
original = root / 'export/main_output.cpp'
output = root / 'window-lookup'
manifest = json.loads((output / 'build.json').read_text())
expected, routes = adapt_dispatch(original.read_text())
assert (output / 'main_output.cpp').read_text() == expected
assert sha(original) == manifest['baseSourceSha256']
assert sha(output / 'main_output.cpp') == manifest['sourceSha256']
assert sha(output / 'OpenSHSMStockDispatchLookup') == manifest['executableSha256']
for name, digest in manifest['retainedObjects'].items():
    assert sha(root / 'export/build' / name) == digest
assert len(manifest['retainedObjects']) == 75
assert '#pragma clang optimize off' in expected and '#pragma GCC optimize ("O0")' in expected
assert expected.count('_setjmp(ctx.exception_jmp_buf)') == original.read_text().count('_setjmp(ctx.exception_jmp_buf)')
addresses = [int(address, 16) for address, _ in routes]
reference = dict((int(address, 16), name) for address, name in routes)
probes = set(addresses)
for address in addresses:
    probes.update(((address - 1) & 0xFFFFFFFF, (address + 1) & 0xFFFFFFFF))
for address in probes:
    index = bisect.bisect_left(addresses, address)
    actual = routes[index][1] if index < len(routes) and addresses[index] == address else None
    assert actual == reference.get(address)
label = 'window-lookup-trace-gx-windowed-lookup30'
run = json.loads((root / (label + '-result.json')).read_text())
log = root / (label + '.log')
assert run['executableSha256'] == manifest['executableSha256']
assert sha(log) == run['logSha256']
assert run['terminalReturncode'] == 1 and not run['deadlineReached']
text = log.read_text()
assert 'UNIMPLEMENTED Opcode 4 (ps_*) XO 7 XO_10 7 at 0x8034c2bc' in text
assert '[ GPU Hang detected ]' not in text
assert '[STAT] 5s frames=227 draws=465' in text
assert '[DI] Read: offset=0x216b60e0' in text
generated = (root / 'export/output_59.cpp').read_text()
assert '// 0x8034C2D4: 13E1000E' in generated
assert 'UNIMPLEMENTED Opcode 4 (ps_*)' in generated.split('loc_8034C2D4: ;', 1)[1].split('loc_8034C2D8:', 1)[0]
dol = (root.parent.parent / 'disc/DATA/sys/main.dol').read_bytes()
word = None
for index in range(7):
    start = struct.unpack_from('>I', dol, 0x48 + index * 4)[0]
    size = struct.unpack_from('>I', dol, 0x90 + index * 4)[0]
    if start <= 0x8034C2D4 < start + size:
        offset = struct.unpack_from('>I', dol, index * 4)[0]
        word = struct.unpack_from('>I', dol, offset + 0x8034C2D4 - start)[0]
assert word == 0x13E1000E
captures = {}
for frame in (300, 1200):
    bmp = root / f'window-lookup-lookup30-efb_{frame}.bmp'
    png = bmp.with_suffix('.png')
    with Image.open(bmp) as a, Image.open(png) as b:
        assert a.size == b.size == (640, 480)
        assert a.convert('RGBA').tobytes() == b.convert('RGBA').tobytes()
    captures[str(frame)] = {'bmpSha256': sha(bmp), 'pngSha256': sha(png)}
hot = root / 'window-hot-o2'
hot_manifest = json.loads((hot / 'build.json').read_text())
assert sha(root / 'export/output_47.cpp') == hot_manifest['sourceSha256']
assert '-O2' in hot_manifest['compilerOptions']
assert not any('fast-math' in option or 'NDEBUG' in option for option in hot_manifest['compilerOptions'])
with Image.open(root / 'window-hot-o2-optimized45-efb_1800.bmp') as a, Image.open(root / 'window-paced-loading45-efb_1800.bmp') as b:
    assert a.convert('RGBA').tobytes() == b.convert('RGBA').tobytes()
(output / 'dispatch-audit.json').write_text(json.dumps({
    'result': 'DISPATCH_MAPPING_AND_BOOT_PROGRESS_PASS_LATER_OPCODE_BLOCKED',
    'routes': len(routes), 'mappingProbes': len(probes), 'hleWrappers': 5,
    'logSha256': sha(log), 'captures': captures,
    'visualObservation': 'Frame300 original wrist-strap warning; frame1200 Nunchuk is required screen, separately inspected.',
    'nextInstruction': {'functionEntryReportedByRuntime': '8034C2BC', 'actualInstructionAddress': '8034C2D4', 'originalWord': '13E1000E'},
    'limits': ['Mapping checks are static contract evidence; whole-run observation does not prove all routes executed.',
        'Hot-batch O2 alone did not materially accelerate startup; its safety-screen pixels match Debug.',
        'Exit1 is fatal unsupported opcode, not deadline/normal completion/menu/gameplay/controller proof.',
        'No physical Wii or full PPC/runtime equivalence claim.']
}, indent=2) + '\n')
print('PASS exact', len(routes), 'routes /', len(probes), 'mapping probes; actual early safety + later Nunchuk screen')
print('STOP correctly recorded: unsupported opcode4/XO7 at8034C2BC, exit1; full goal incomplete')
