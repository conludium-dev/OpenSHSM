"""Expose the current MMU gap using original DCEnable and explicitly synthetic alias/cache-operation probes."""
from pathlib import Path
import base64
import hashlib
import json
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
output = Path('work/private-game/static-recomp/dolphin-coherence-probe')
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
generation = json.loads((output / 'generation.json').read_text())
original = Path('work/private-game/disc/DATA/sys/main.dol').read_bytes()
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
record = generation['records'][0]
image = (output / 'boot.dol').read_bytes()
assert image[256:len(original)] == original[256:] and not record['patches']
assert record['sha256'] == hashlib.sha256(image).hexdigest()
assert generation['scriptSha256'] == sha(experiment / 'build_dolphin_probe.py')
header = struct.unpack('>64I', original[:256])
section = next(index for index in range(18) if header[18 + index] <= 0x80212f80 < header[18 + index] + header[36 + index])
offset = header[section] + 0x80212f80 - header[18 + section]
function = original[offset:offset + 20]
assert struct.unpack('>5I', function) == (0x7c0004ac, 0x7c70faa6, 0x60634000, 0x7c70fba6, 0x4e800020)
expected = {'false': [0x55667788, 0x55667788, 0x55667788, 0x99aabbcc, 0x99aabbcc],
            'true': [0x55667788, 0x11223344, 0x55667788, 0x55667788, 0x99aabbcc]}
actual = {}
for mode in ['false', 'true']:
    capture = json.loads((output / ('boot-' + mode + '-dolphin.json')).read_text(encoding='utf-8-sig'))
    assert capture['harnessSha256'].lower() == record['sha256']
    assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
    assert capture['scriptSha256'].lower() == sha(experiment / 'run_dolphin_probe.ps1')
    assert 'Dolphin.Core.AccurateCPUCache=' + mode.title() in capture['arguments']
    assert base64.b64decode(capture['originalDceCode']) == function
    raw = base64.b64decode(capture['data'])
    assert len(raw) == 736 and raw[:16] == b'OSHSM_PPC_DLP001'
    assert struct.unpack_from('>I', raw, 16)[0] == 0xc001cafe
    registers = list(struct.unpack_from('>32I', raw, 32))
    assert registers[3] == 0x4000 and struct.unpack_from('>I', raw, 180)[0] == 0x4000
    assert struct.unpack_from('>I', raw, 184)[0] == 0x2030
    actual[mode] = registers[5:10]
    assert actual[mode] == expected[mode], (mode, actual[mode], expected[mode])
exe = output / 'native-mmu-probe'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'coherence_native.cpp'), '-o', str(exe)], capture_output=True, text=True, timeout=30)
(output / 'native-build.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
native = list(map(int, result.stdout.split()))
assert native == expected['false'] and native != expected['true']
report = {'result': 'KNOWN_CACHE_GAP_CONFIRMED', 'originalDcEnableExecuted': True,
          'nativeMatchesCoherentDolphinOnly': True, 'nativeFailsAccurateDolphinAtSamples': [1, 3],
          'sampleNames': ['cachedAfterCachedStore', 'uncachedBeforeDcbst', 'uncachedAfterDcbst',
                          'cachedAfterUncachedStoreBeforeDcbi', 'cachedAfterDcbi'],
          'dolphin': actual, 'nativeMmu': native, 'generationSha256': sha(output / 'generation.json'),
          'nativeSourceSha256': sha(experiment / 'coherence_native.cpp'), 'nativeExeSha256': sha(exe),
          'scriptSha256': sha(Path(__file__)),
          'captureSha256': {mode: sha(output / ('boot-' + mode + '-dolphin.json')) for mode in actual},
          'limits': ['Original five-instruction DCEnable executed in Dolphin; surrounding stores/alias reads/dcbst/dcbi/collector are synthetic measurement code.',
                     'Native probe exercises existing MMU only; no native DCEnable acceptance or original game behavior claim.',
                     'Dolphin accurate-cache model, not physical Wii timing or a full DMA/eviction/locked-cache test.',
                     'DCEnable remains refused in strict native bootstrap until a memory/cache consumer contract is implemented.'],
          'next': 'Integrate cached/uncached views and dirty writeback/invalidation into existing experimental memory accesses; verify against this accurate-cache oracle before accepting DCE.'}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('KNOWN GAP: native MMU matches cache-off model, differs from accurate cache at2samples; DCEnable not accepted')
