"""Validate incremental lowering, DCE contract and accurate-cache boot endpoint."""
from pathlib import Path
import base64
import hashlib
import json
import re
import struct
import subprocess

experiment = Path('experiments/wii-static-recomp')
native = Path('work/private-game/static-recomp/mass-dcache')
output = Path('work/private-game/static-recomp/dolphin-dcache-probe')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
base = Path('work/private-game/static-recomp/mass-memory')
lowering = json.loads((native / 'lowering.json').read_text())
assert lowering['baseLoweringSha256'] == sha(base / 'lowering.json')
assert lowering['adapterSha256'] == sha(experiment / 'dcache_adapter.h')
assert lowering['scriptSha256'] == sha(experiment / 'build_dcache.py')
for record in lowering['records']:
    source = Path(record['directory']) / record['file']
    assert record['sourceSha256'] == sha(source) and record['objectSha256'] == sha(Path(str(source) + '.o'))
    before = (base / record['file']).read_text()
    assert source.read_text() == before.replace('nwii::runtime::experiment_write_hid0_icache(ctx,', 'nwii::runtime::experiment_write_hid0_dcache(ctx,')
assert lowering['changes'] == 7
boot = json.loads((native / 'boot.json').read_text())
assert boot['executableSha256'] == sha(native / 'openshsm-mass-boot')
assert boot['wrapperSha256'] == sha(experiment / 'dcache_boot.cpp') and boot['baseWrapperSha256'] == sha(experiment / 'mass_boot.cpp')
assert boot['loweringSha256'] == sha(native / 'lowering.json')
policy = Path('work/private-game/static-recomp/mass-icache/boot-quarantine.tsv')
assert boot['policySha256'] == sha(policy)
replay = subprocess.run([str(native / 'openshsm-mass-boot'), 'work/private-game/disc/DATA/sys/main.dol', str(policy)],
                        capture_output=True, text=True, timeout=30)
assert replay.returncode == 7 and replay.stdout == boot['stdout'], 'Current native boot differs from measured report'
generation = json.loads((output / 'generation.json').read_text())
capture_path = output / 'boot-true-dolphin.json'
capture = json.loads(capture_path.read_text(encoding='utf-8-sig'))
assert capture['accurateCache'] == 'True' and capture['records'] == 1
assert capture['harnessSha256'].lower() == generation['harnessSha256'] == sha(output / 'boot.dol')
assert capture['scriptSha256'].lower() == generation['wrapperSha256'] == sha(experiment / 'run_dcache_probe.ps1')
assert generation['baseRunnerSha256'] == sha(experiment / 'run_dolphin_probe.ps1')
assert generation['generatorSha256'] == sha(experiment / 'build_dcache_probe.py')
assert generation['helperSha256'] == sha(experiment / 'build_dolphin_probe.py')
assert generation['fixtureSha256'] == sha(Path('work/private-game/static-recomp/dolphin-probe/boot.dol'))
assert capture['emulatorSha256'].lower() == sha(Path('_scratch/tmp/dolphin-static-recomp-lab/Dolphin.exe'))
original_path = Path('work/private-game/disc/DATA/sys/main.dol')
original = original_path.read_bytes()
assert generation['originalSha256'] == sha(original_path)
assert hashlib.sha1(original).hexdigest() == '6a3964eaf1ebe8225283363e4161a793a03683d3'
header = struct.unpack('>64I', original[:256])
def offset(address):
    index = next(i for i in range(18) if header[18 + i] <= address < header[18 + i] + header[36 + i])
    return header[index] + address - header[18 + index]
image = (output / 'boot.dol').read_bytes()
allowed = set(range(offset(0x802106c0), offset(0x802106c0) + 4))
assert {i for i in range(256, len(original)) if original[i] != image[i]} <= allowed
assert base64.b64decode(capture['originalDceCode']) == original[offset(0x80212f80):offset(0x80212f80) + 20]
data = base64.b64decode(capture['data'])
assert len(data) == 800 and data[:16] == b'OSHSM_PPC_DLP001'
assert struct.unpack_from('>II', data, 16) == (0xc001cafe, 0)
stdout = boot['stdout']
assert 'BOOT_BOUNDARY pc=802106c0 lr=802134d8 msr=2030' in stdout
assert 'UNVERIFIED_PROCESSOR_REGISTER_1017' in stdout and 'BOOT_CACHE hid0=c000' in stdout
gpr = list(map(int, re.search(r'BOOT_REGISTERS((?: \d+){32})', stdout)[1].split()))
assert list(struct.unpack_from('>32I', data, 32)) == gpr
cr, lr, ctr, xer, hid2, hid0, msr = struct.unpack_from('>7I', data, 160)
assert (lr, ctr, xer, hid2, hid0, msr) == (0x802134d8, 0, 0, 0xa0000000, 0xc000, 0x2030)
state = [list(map(int, line.split()[1:])) for line in stdout.splitlines() if line.startswith('FP_STATE ')][-1]
assert state[0] == 0x802106c0
assert cr == sum(value << ((7 - index) * 4) for index, value in enumerate(state[2:10]))
assert list(struct.unpack_from('>32Q', data, 192)) == state[10:42]
assert list(struct.unpack_from('>32Q', data, 448)) == state[42:74]
assert (struct.unpack_from('>Q', data, 704)[0] & 0xffffffff) == state[1]
stack = [list(map(int, line.split()[2:])) for line in stdout.splitlines() if line.startswith('CPU_STACK ')][-1]
assert data[736:] == bytes(stack)
upstream = Path('_scratch/tmp/wii-static-recomp-tools/NWiiRecomp')
exe = native / 'dcache-contract'
result = subprocess.run(['clang++', '-std=c++20', '-O0', '-include', 'bit', '-I', str(upstream / 'nWiiRuntime/include'),
                         str(experiment / 'dcache_contract.cpp'), str(experiment / 'processor_adapter.cpp'), '-o', str(exe)],
                        capture_output=True, text=True, timeout=30)
assert result.returncode == 0, result.stderr
result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
assert result.returncode == 0 and 'DCE_CONTRACT 3accepts 8refusals rollback PASS' in result.stdout, result
report = {'result': 'DCE_ENABLE_BOOT_PREFIX_VERIFIED', 'endpoint': '0x802106C0 before L2CR read',
          'cpuVisibleGprCrLrCtrXerHid2Hid0MsrFprPs1FpscrStackMatch': True,
          'captureSha256': sha(capture_path), 'generationSha256': sha(output / 'generation.json'),
          'bootSha256': sha(native / 'boot.json'), 'contractSourceSha256': sha(experiment / 'dcache_contract.cpp'),
          'contractExeSha256': sha(exe), 'verifierSha256': sha(Path(__file__)),
          'limits': ['Private translated boot fixture in Dolphin accurate-cache interpreter, not physical Wii or unmodified retail startup.',
                     'Scoped DCE enable with initially empty cache; disable/populated-cache activation refuse. L2CR remains quarantined.',
                     'No DMA/locked-cache/full BAT/quantized paired/OS/IOS/GX/audio/menu/game acceptance.']}
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS scoped native DCE/original accurate-cache boot endpoint; next L2CR1017; 3accepts/8refusals')
